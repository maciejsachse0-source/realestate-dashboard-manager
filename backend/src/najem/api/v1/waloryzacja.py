"""Waloryzacja roczna (koncepcja, sekcja 7.6).

Wskaźnik wprowadza się raz, efekt jest na wszystkich umowach. Ekran ma dwa
kroki: podgląd propozycji i zbiorcze zatwierdzenie. Podgląd niczego nie zapisuje,
więc wycofanie się przed zatwierdzeniem jest darmowe.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError

from najem.auth.zaleznosci import Podglad, Zarzadca
from najem.baza import SesjaBazy
from najem.domena.slowniki import OperacjaAudytu, RodzajWskaznika
from najem.modele import WskaznikWaloryzacji
from najem.schematy.wspolne import LIMIT_DOMYSLNY, LIMIT_MAKSYMALNY, Strona
from najem.uslugi.audyt import zapisz_zmiane
from najem.uslugi.waloryzacja import (
    BladWaloryzacji,
    PozycjaWaloryzacji,
    SumaWaluty,
    przygotuj_przebieg,
    wskazniki_na_rok,
    zatwierdz,
    zmiany_zapisane,
)

router = APIRouter(prefix="/waloryzacja", tags=["waloryzacja"])

Limit = Annotated[int, Query(ge=1, le=LIMIT_MAKSYMALNY)]
Offset = Annotated[int, Query(ge=0)]


class WskaznikWejscie(BaseModel):
    rok: int = Field(ge=2000, le=2200)
    rodzaj: RodzajWskaznika
    wartosc_procent: Decimal = Field(ge=-50, le=100)
    data_publikacji: date | None = None
    uwagi: str | None = None


class WskaznikWyjscie(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rok: int
    rodzaj: RodzajWskaznika
    wartosc_procent: Decimal
    data_publikacji: date | None
    uwagi: str | None
    wersja: int


class PozycjaWyjscie(BaseModel):
    """Jedna umowa w przebiegu. Kwoty jako tekst, żeby nie zgubić groszy."""

    okres_najmu_id: int
    lokal_id: int
    oznaczenie_lokalu: str
    najemca: str

    kwota_stara: str | None = None
    kwota_nowa: str | None = None
    roznica: str | None = None
    waluta: str | None = None
    rodzaj_kwoty: str | None = None
    wskaznik_procent: str | None = None
    obowiazuje_od: date | None = None
    powod_wylaczenia: str | None = None


class SumaWyjscie(BaseModel):
    """Suma w jednej walucie. Kwot w różnych walutach nie dodajemy do siebie."""

    waluta: str
    umow: int
    przed: str
    po: str
    roznica: str


class PrzebiegWyjscie(BaseModel):
    rok: int
    wskazniki: dict[str, str] = Field(description="Wskaźniki wprowadzone na ten rok")
    objete: list[PozycjaWyjscie]
    wylaczone: list[PozycjaWyjscie]
    sumy: list[SumaWyjscie]


class PodsumowanieWejscie(BaseModel):
    rok: int = Field(ge=2000, le=2200)
    okresy_najmu: list[int] = Field(description="Które propozycje są zaznaczone")


class ZatwierdzenieWejscie(BaseModel):
    rok: int = Field(ge=2000, le=2200)
    okresy_najmu: list[int] = Field(min_length=1, description="Które umowy zatwierdzamy")


class ZatwierdzenieWyjscie(BaseModel):
    rok: int
    umow_zwaloryzowanych: int
    zdarzen_o_wekslach: int


def _adres(request: Request) -> str | None:
    return request.client.host if request.client else None


# ---------------------------------------------------------------- wskazniki


@router.get("/wskazniki", response_model=Strona[WskaznikWyjscie], summary="Wprowadzone wskaźniki")
def lista_wskaznikow(
    baza: SesjaBazy,
    _: Podglad,
    limit: Limit = LIMIT_DOMYSLNY,
    offset: Offset = 0,
    rok: Annotated[int | None, Query(ge=2000, le=2200)] = None,
) -> Strona[WskaznikWyjscie]:
    warunki: list[ColumnElement[bool]] = []
    if rok is not None:
        warunki.append(WskaznikWaloryzacji.rok == rok)

    wszystkich = (
        baza.scalar(select(func.count()).select_from(WskaznikWaloryzacji).where(*warunki)) or 0
    )
    pozycje = baza.scalars(
        select(WskaznikWaloryzacji)
        .where(*warunki)
        .order_by(WskaznikWaloryzacji.rok.desc(), WskaznikWaloryzacji.rodzaj)
        .limit(limit)
        .offset(offset)
    ).all()

    return Strona(
        pozycje=[WskaznikWyjscie.model_validate(w) for w in pozycje],
        wszystkich=wszystkich,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/wskazniki",
    response_model=WskaznikWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Wprowadza wskaźnik na dany rok",
)
def dodaj_wskaznik(
    dane: WskaznikWejscie, baza: SesjaBazy, kto: Zarzadca, request: Request
) -> WskaznikWyjscie:
    """Wskaźnik wprowadza się raz. Powtórne wprowadzenie tego samego rodzaju
    na ten sam rok jest błędem, a nie cichą podmianą — GUS nie publikuje
    wskaźnika dwa razy.
    """
    istniejacy = baza.scalars(
        select(WskaznikWaloryzacji).where(
            WskaznikWaloryzacji.rok == dane.rok,
            WskaznikWaloryzacji.rodzaj == dane.rodzaj,
        )
    ).one_or_none()
    if istniejacy is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Wskaźnik {dane.rodzaj.value} na rok {dane.rok} jest już wprowadzony "
            f"({istniejacy.wartosc_procent}%).",
        )

    wskaznik = WskaznikWaloryzacji(**dane.model_dump(), wprowadzil_uzytkownik_id=kto.uzytkownik.id)
    baza.add(wskaznik)
    try:
        baza.flush()
    except IntegrityError as blad:
        # Sprawdzenie SELECT-em wyzej nie jest atomowe. Dwa rownolegle zadania
        # zatrzyma dopiero unikalny indeks i to jest ten sam konflikt,
        # a nie blad serwera.
        baza.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Wskaźnik {dane.rodzaj.value} na rok {dane.rok} jest już wprowadzony.",
        ) from blad
    zapisz_zmiane(
        baza,
        wskaznik,
        operacja=OperacjaAudytu.UTWORZENIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    # Sesja ma expire_on_commit=False, więc bez odświeżenia oddalibyśmy to,
    # co przyszło w żądaniu, a nie to, co jest w bazie. Kolumna ma NUMERIC(5,2),
    # więc "3.7" zapisuje się jako 3.70 i tak samo musi wracać — inaczej POST
    # i GET pokazują tę samą wartość inaczej.
    baza.refresh(wskaznik)
    return WskaznikWyjscie.model_validate(wskaznik)


# ----------------------------------------------------------------- przebieg


def _na_wyjscie(pozycja: PozycjaWaloryzacji) -> PozycjaWyjscie:
    if pozycja.propozycja is None:
        return PozycjaWyjscie(
            okres_najmu_id=pozycja.okres_najmu_id,
            lokal_id=pozycja.lokal_id,
            oznaczenie_lokalu=pozycja.oznaczenie_lokalu,
            najemca=pozycja.najemca,
            powod_wylaczenia=pozycja.powod_wylaczenia,
        )

    p = pozycja.propozycja
    return PozycjaWyjscie(
        okres_najmu_id=pozycja.okres_najmu_id,
        lokal_id=pozycja.lokal_id,
        oznaczenie_lokalu=pozycja.oznaczenie_lokalu,
        najemca=pozycja.najemca,
        kwota_stara=str(p.kwota_stara.wartosc),
        kwota_nowa=str(p.kwota_nowa.wartosc),
        roznica=str(p.roznica.wartosc),
        waluta=p.kwota_nowa.waluta,
        rodzaj_kwoty=p.kwota_nowa.rodzaj.value,
        wskaznik_procent=str(p.wskaznik_procent),
        obowiazuje_od=p.obowiazuje_od,
    )


@router.get(
    "/przebieg",
    response_model=PrzebiegWyjscie,
    summary="Krok 1: propozycje na dany rok (nic nie zapisuje)",
)
def przebieg(
    baza: SesjaBazy,
    _: Podglad,
    rok: Annotated[int, Query(ge=2000, le=2200)],
) -> PrzebiegWyjscie:
    """Przebieg **nie jest stronicowany** i to jest decyzja, nie przeoczenie.

    Waloryzacja jest operacją na całym portfelu naraz: użytkownik zaznacza
    i zatwierdza wszystko jednym ruchem. Strona po pięćdziesiąt umów zamieniłaby
    jeden rytuał raz do roku w dwadzieścia osobnych zatwierdzeń, a przy okazji
    ukryła część wyłączeń.
    """
    wynik = przygotuj_przebieg(baza, rok)
    return PrzebiegWyjscie(
        rok=rok,
        wskazniki={r.value: str(w) for r, w in wskazniki_na_rok(baza, rok).items()},
        objete=[_na_wyjscie(p) for p in wynik.objete],
        wylaczone=[_na_wyjscie(p) for p in wynik.wylaczone],
        sumy=[_suma_na_wyjscie(s) for s in wynik.podsumowanie()],
    )


def _suma_na_wyjscie(suma: SumaWaluty) -> SumaWyjscie:
    return SumaWyjscie(
        waluta=suma.waluta,
        umow=suma.umow,
        przed=str(suma.przed),
        po=str(suma.po),
        roznica=str(suma.roznica),
    )


@router.post(
    "/podsumowanie",
    response_model=list[SumaWyjscie],
    summary="Suma zaznaczonych propozycji (podgląd przed zatwierdzeniem)",
)
def podsumowanie(dane: PodsumowanieWejscie, baza: SesjaBazy, _: Podglad) -> list[SumaWyjscie]:
    """Sumę liczy serwer, bo tylko on ma Decimal. Przeglądarka umie tylko float,
    a float na pieniądzach to zasada, której w tym projekcie nie łamiemy.
    """
    wynik = przygotuj_przebieg(baza, dane.rok)
    return [_suma_na_wyjscie(s) for s in wynik.podsumowanie(set(dane.okresy_najmu))]


@router.post(
    "/zatwierdz",
    response_model=ZatwierdzenieWyjscie,
    summary="Krok 2: zapisuje wybrane propozycje w jednej transakcji",
)
def zatwierdz_przebieg(
    dane: ZatwierdzenieWejscie, baza: SesjaBazy, kto: Zarzadca, request: Request
) -> ZatwierdzenieWyjscie:
    try:
        wynik = zatwierdz(
            baza,
            dane.rok,
            set(dane.okresy_najmu),
            uzytkownik_id=kto.uzytkownik.id,
            adres_ip=_adres(request),
        )
    except BladWaloryzacji as blad:
        baza.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(blad)) from blad

    baza.commit()
    return ZatwierdzenieWyjscie(
        rok=wynik.rok,
        umow_zwaloryzowanych=wynik.umow_zwaloryzowanych,
        zdarzen_o_wekslach=wynik.zdarzen_o_wekslach,
    )


#: Nagłówki arkusza zmian. Kolejność wyznacza formaty i szerokości poniżej.
NAGLOWKI = (
    "Budynek i lokal",
    "Najemca",
    "Czynsz przed",
    "Czynsz po",
    "Różnica",
    "Waluta",
    "Netto/brutto",
    "Wskaźnik %",
    "Obowiązuje od",
)

SZEROKOSCI = (18, 34, 14, 14, 12, 8, 13, 11, 14)

#: Format księgowy: separator tysięcy i zawsze dwa miejsca po przecinku.
#: Bez tego Excel pokazuje 9851,5 zamiast 9 851,50, a to ma iść do pism.
FORMAT_KWOTY = "# ##0.00"

#: Procent nie jest kwotą, więc nie dostaje separatora tysięcy.
FORMAT_PROCENTU = "0.00"


def _sformatuj(arkusz: Worksheet) -> None:
    """Nadaje arkuszowi format, w którym da się go od razu wydrukować."""
    for numer, szerokosc in enumerate(SZEROKOSCI, start=1):
        arkusz.column_dimensions[get_column_letter(numer)].width = szerokosc

    for komorka in arkusz[1]:
        komorka.font = Font(bold=True)
    arkusz.freeze_panes = "A2"

    for wiersz in arkusz.iter_rows(min_row=2):
        for numer in (3, 4, 5):  # czynsz przed, czynsz po, różnica
            wiersz[numer - 1].number_format = FORMAT_KWOTY
        wiersz[7].number_format = FORMAT_PROCENTU  # wskaźnik
        wiersz[8].number_format = "DD.MM.YYYY"  # obowiązuje od


def _wypelnij(arkusz: Worksheet, pozycje: Iterable[PozycjaWaloryzacji]) -> None:
    """Wpisuje pozycje do arkusza i nadaje mu format.

    Kwoty idą jako `Decimal`. openpyxl zapisuje je bez pośrednictwa `float`,
    a zamiana na `float` po drodze łamie zasadę twardą projektu i akurat tutaj
    dotyczy liczb, które trafiają do pism.
    """
    arkusz.append(list(NAGLOWKI))
    for pozycja in pozycje:
        p = pozycja.propozycja
        assert p is not None
        arkusz.append(
            [
                pozycja.oznaczenie_lokalu,
                pozycja.najemca,
                p.kwota_stara.wartosc,
                p.kwota_nowa.wartosc,
                p.roznica.wartosc,
                p.kwota_nowa.waluta,
                p.kwota_nowa.rodzaj.value,
                p.wskaznik_procent,
                p.obowiazuje_od,
            ]
        )
    _sformatuj(arkusz)


@router.get(
    "/eksport",
    summary="Lista zmian do XLSX (do powiadomień dla najemców)",
    response_class=Response,
)
def eksport(
    baza: SesjaBazy,
    _: Podglad,
    rok: Annotated[int, Query(ge=2000, le=2200)],
) -> Response:
    """Arkusz z listą zmian. Służy do przygotowania pism do najemców,
    więc niesie nazwę najemcy, lokal i obie kwoty.

    Pierwszy arkusz zawiera **wyłącznie zmiany zatwierdzone** — decyzja D4
    mówi, że wartość niezatwierdzona nie wchodzi do raportów, a z tego arkusza
    ktoś robi korespondencję seryjną. Propozycje są w osobnym arkuszu, żeby
    pomyłka wymagała przejścia na inną zakładkę, a nie przeoczenia jednej
    kolumny.
    """
    skoroszyt = Workbook()
    zatwierdzone = skoroszyt.active
    assert zatwierdzone is not None
    zatwierdzone.title = f"Waloryzacja {rok}"
    _wypelnij(zatwierdzone, zmiany_zapisane(baza, rok))

    wynik = przygotuj_przebieg(baza, rok)
    if wynik.objete:
        propozycje = skoroszyt.create_sheet("Propozycje niezatwierdzone")
        _wypelnij(propozycje, wynik.objete)

    if wynik.wylaczone:
        wylaczone = skoroszyt.create_sheet("Wyłączone")
        wylaczone.append(["Budynek i lokal", "Najemca", "Powód wyłączenia"])
        for pozycja in wynik.wylaczone:
            wylaczone.append(
                [pozycja.oznaczenie_lokalu, pozycja.najemca, pozycja.powod_wylaczenia or ""]
            )
        for numer, szerokosc in enumerate((18, 34, 70), start=1):
            wylaczone.column_dimensions[get_column_letter(numer)].width = szerokosc
        for komorka in wylaczone[1]:
            komorka.font = Font(bold=True)
        wylaczone.freeze_panes = "A2"

    bufor = BytesIO()
    skoroszyt.save(bufor)

    return Response(
        content=bufor.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="waloryzacja-{rok}.xlsx"'},
    )
