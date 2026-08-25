"""Okresy najmu, parametry, składniki opłat, zabezpieczenia i przeglądy.

Reguły domenowe są wywoływane tutaj, ale nie są tutaj zaimplementowane.
API tłumaczy HTTP na wywołania reguł i z powrotem — nic więcej.
"""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from najem.auth.zaleznosci import Operator, Podglad, Zarzadca
from najem.baza import SesjaBazy
from najem.domena.kalendarz import dzien_miesiaca, przesun_na_dzien_roboczy
from najem.domena.reguly.data_zakonczenia import data_zakonczenia
from najem.domena.reguly.przeglady import nastepny_przeglad, status_przegladu
from najem.domena.slowniki import OperacjaAudytu, StatusWeryfikacji
from najem.domena.stany import (
    PRZEJSCIA_OKRESU_NAJMU,
    PRZEJSCIA_ZABEZPIECZENIA,
    sprawdz_przejscie,
)
from najem.modele import (
    Lokal,
    Najemca,
    ObowiazekPrzegladu,
    OkresNajmu,
    ParametrWartosc,
    SkladnikOplaty,
    Zabezpieczenie,
)
from najem.schematy.umowy import (
    DecyzjaWeryfikacji,
    OkresNajmuWejscie,
    OkresNajmuWyjscie,
    OkresNajmuZmiana,
    ParametrWejscie,
    ParametrWyjscie,
    PrzegladWejscie,
    PrzegladWyjscie,
    SkladnikWejscie,
    SkladnikWyjscie,
    ZabezpieczenieWejscie,
    ZabezpieczenieWyjscie,
    ZabezpieczenieZmiana,
)
from najem.uslugi.audyt import zapisz_zmiane

router = APIRouter(tags=["umowy"])


def _adres(request: Request) -> str | None:
    return request.client.host if request.client else None


def _przelicz_koniec(okres: OkresNajmu) -> None:
    """Data zakonczenia jest wyliczana z reguly R1, nie wpisywana recznie.

    Wolane po kazdej zmianie danych, ktore na nia wplywaja. Brak wyniku zapisuje
    NULL i to jest poprawny stan, a nie blad (decyzja D5).
    """
    wynik = data_zakonczenia(
        bazuje_na=okres.bazuje_na_dacie,
        okres_miesiace=okres.okres_zawarcia_miesiace,
        data_zawarcia=okres.data_zawarcia,
        data_przekazania=okres.data_przekazania,
    )
    okres.data_zakonczenia_planowana = wynik.wartosc


def _przelicz_przeglad(przeglad: ObowiazekPrzegladu, dzis: date) -> None:
    """Regula R7: termin kolejnego przegladu i jego status."""
    wynik = nastepny_przeglad(
        ostatni_przeglad=przeglad.ostatni_przeglad_data,
        czestotliwosc_miesiace=przeglad.czestotliwosc_miesiace,
    )
    przeglad.nastepny_przeglad_data = wynik.wartosc
    przeglad.status = status_przegladu(nastepny_termin=wynik.wartosc, dzis=dzis)


def _okres(baza: SesjaBazy, okres_id: int) -> OkresNajmu:
    okres = baza.get(OkresNajmu, okres_id)
    if okres is None or okres.usunieto_dnia is not None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Okres najmu o numerze {okres_id} nie istnieje."
        )
    return okres


# ------------------------------------------------------------- okresy najmu


@router.post(
    "/okresy-najmu",
    response_model=OkresNajmuWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Zakłada okres najmu",
)
def dodaj_okres(
    dane: OkresNajmuWejscie, baza: SesjaBazy, kto: Zarzadca, request: Request
) -> OkresNajmuWyjscie:
    if baza.get(Lokal, dane.lokal_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wskazany lokal nie istnieje.")
    if baza.get(Najemca, dane.najemca_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wskazany najemca nie istnieje.")

    okres = OkresNajmu(**dane.model_dump())
    _przelicz_koniec(okres)
    baza.add(okres)
    baza.flush()
    zapisz_zmiane(
        baza,
        okres,
        operacja=OperacjaAudytu.UTWORZENIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return OkresNajmuWyjscie.model_validate(okres)


@router.get(
    "/okresy-najmu/{okres_id}", response_model=OkresNajmuWyjscie, summary="Szczegóły okresu najmu"
)
def pobierz_okres(okres_id: int, baza: SesjaBazy, _: Podglad) -> OkresNajmuWyjscie:
    return OkresNajmuWyjscie.model_validate(_okres(baza, okres_id))


@router.put(
    "/okresy-najmu/{okres_id}", response_model=OkresNajmuWyjscie, summary="Zmienia okres najmu"
)
def zmien_okres(
    okres_id: int, dane: OkresNajmuZmiana, baza: SesjaBazy, kto: Zarzadca, request: Request
) -> OkresNajmuWyjscie:
    okres = _okres(baza, okres_id)
    if okres.wersja != dane.wersja:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"Okres najmu został w międzyczasie zmieniony (twoja wersja: {dane.wersja}, "
                f"aktualna: {okres.wersja}). Odśwież widok i wprowadź zmiany ponownie."
            ),
            headers={"X-Wersja-Biezaca": str(okres.wersja)},
        )

    if dane.status is not None and dane.status is not okres.status:
        # Maszyna stanow z domeny. Bez niej w bazie znajda sie umowy
        # jednoczesnie zakonczone i aktywne (plan budowy, punkt F).
        sprawdz_przejscie(PRZEJSCIA_OKRESU_NAJMU, okres.status, dane.status)
        okres.status = dane.status

    for pole, wartosc in dane.model_dump(exclude={"wersja", "status"}).items():
        setattr(okres, pole, wartosc)
    _przelicz_koniec(okres)

    zapisz_zmiane(
        baza,
        okres,
        operacja=OperacjaAudytu.ZMIANA,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return OkresNajmuWyjscie.model_validate(okres)


# ------------------------------------------------------------------ parametry


@router.get(
    "/okresy-najmu/{okres_id}/parametry",
    response_model=list[ParametrWyjscie],
    summary="Historia wartości parametrów",
)
def lista_parametrow(
    okres_id: int,
    baza: SesjaBazy,
    _: Podglad,
    klucz: Annotated[str | None, Query(max_length=80)] = None,
) -> list[ParametrWyjscie]:
    """Cala os czasu, takze wartosci niezatwierdzone.

    Zakladka historii ma pokazywac propozycje czekajace na decyzje,
    wyroznione wizualnie. Ukrycie ich ukryloby prace do zrobienia.
    """
    _okres(baza, okres_id)
    warunki = [
        ParametrWartosc.okres_najmu_id == okres_id,
        ParametrWartosc.usunieto_dnia.is_(None),
    ]
    if klucz:
        warunki.append(ParametrWartosc.klucz == klucz)

    wiersze = baza.scalars(
        select(ParametrWartosc)
        .where(*warunki)
        .order_by(ParametrWartosc.klucz, ParametrWartosc.obowiazuje_od, ParametrWartosc.id)
    ).all()
    return [ParametrWyjscie.model_validate(w) for w in wiersze]


@router.post(
    "/okresy-najmu/{okres_id}/parametry",
    response_model=ParametrWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaje wartość parametru",
)
def dodaj_parametr(
    okres_id: int,
    dane: ParametrWejscie,
    baza: SesjaBazy,
    kto: Operator,
    request: Request,
) -> ParametrWyjscie:
    """Nowa wartosc wchodzi jako ZAPROPONOWANA, takze przy recznym wprowadzeniu.

    Decyzja D4 nie robi wyjatku dla czlowieka wpisujacego wartosc z klawiatury:
    zatwierdzenie jest osobnym, swiadomym krokiem.
    """
    _okres(baza, okres_id)
    parametr = ParametrWartosc(
        okres_najmu_id=okres_id,
        status_weryfikacji=StatusWeryfikacji.ZAPROPONOWANA,
        **dane.model_dump(),
    )
    baza.add(parametr)
    baza.flush()
    zapisz_zmiane(
        baza,
        parametr,
        operacja=OperacjaAudytu.UTWORZENIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return ParametrWyjscie.model_validate(parametr)


@router.post(
    "/parametry/{parametr_id}/decyzja",
    response_model=ParametrWyjscie,
    summary="Zatwierdza, poprawia albo odrzuca wartość",
)
def decyzja_o_parametrze(
    parametr_id: int,
    dane: DecyzjaWeryfikacji,
    baza: SesjaBazy,
    kto: Zarzadca,
    request: Request,
) -> ParametrWyjscie:
    """Ślad decyzji człowieka: kto i kiedy (decyzja D4)."""
    parametr = baza.get(ParametrWartosc, parametr_id)
    if parametr is None or parametr.usunieto_dnia is not None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Parametr o numerze {parametr_id} nie istnieje."
        )

    parametr.status_weryfikacji = dane.status
    if dane.uwagi is not None:
        parametr.uwagi = dane.uwagi

    if dane.status in {StatusWeryfikacji.ZATWIERDZONA, StatusWeryfikacji.POPRAWIONA}:
        parametr.zatwierdzil_uzytkownik_id = kto.uzytkownik.id
        parametr.zatwierdzono_dnia = datetime.now(UTC)
    else:
        # Cofniecie zatwierdzenia czysci slad w calosci. Polowiczny slad
        # (kto bez kiedy) jest odrzucany przez ograniczenie w bazie.
        parametr.zatwierdzil_uzytkownik_id = None
        parametr.zatwierdzono_dnia = None

    zapisz_zmiane(
        baza,
        parametr,
        operacja=OperacjaAudytu.ZMIANA,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return ParametrWyjscie.model_validate(parametr)


# ------------------------------------------------------------ skladniki oplat


@router.get(
    "/okresy-najmu/{okres_id}/skladniki",
    response_model=list[SkladnikWyjscie],
    summary="Składniki opłat wraz z terminami płatności",
)
def lista_skladnikow(
    okres_id: int,
    baza: SesjaBazy,
    _: Podglad,
    na_dzien: date | None = None,
) -> list[SkladnikWyjscie]:
    _okres(baza, okres_id)
    dzien = na_dzien or date.today()

    wiersze = baza.scalars(
        select(SkladnikOplaty)
        .where(
            SkladnikOplaty.okres_najmu_id == okres_id,
            SkladnikOplaty.usunieto_dnia.is_(None),
        )
        .order_by(SkladnikOplaty.nazwa)
    ).all()

    wynik: list[SkladnikWyjscie] = []
    for wiersz in wiersze:
        pozycja = SkladnikWyjscie.model_validate(wiersz)
        if wiersz.dzien_platnosci_miesiaca is not None:
            # Regula R3: pokazujemy faktyczny dzien roboczy obok umownego.
            umowny = dzien_miesiaca(dzien.year, dzien.month, wiersz.dzien_platnosci_miesiaca)
            pozycja.dzien_platnosci_roboczy = przesun_na_dzien_roboczy(umowny)
        wynik.append(pozycja)
    return wynik


@router.post(
    "/okresy-najmu/{okres_id}/skladniki",
    response_model=SkladnikWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaje składnik opłaty",
)
def dodaj_skladnik(
    okres_id: int,
    dane: SkladnikWejscie,
    baza: SesjaBazy,
    kto: Zarzadca,
    request: Request,
) -> SkladnikWyjscie:
    _okres(baza, okres_id)
    skladnik = SkladnikOplaty(okres_najmu_id=okres_id, **dane.model_dump())
    baza.add(skladnik)
    baza.flush()
    zapisz_zmiane(
        baza,
        skladnik,
        operacja=OperacjaAudytu.UTWORZENIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return SkladnikWyjscie.model_validate(skladnik)


# -------------------------------------------------------------- zabezpieczenia


@router.get(
    "/okresy-najmu/{okres_id}/zabezpieczenia",
    response_model=list[ZabezpieczenieWyjscie],
    summary="Zabezpieczenia umowy",
)
def lista_zabezpieczen(okres_id: int, baza: SesjaBazy, _: Podglad) -> list[ZabezpieczenieWyjscie]:
    _okres(baza, okres_id)
    wiersze = baza.scalars(
        select(Zabezpieczenie)
        .where(
            Zabezpieczenie.okres_najmu_id == okres_id,
            Zabezpieczenie.usunieto_dnia.is_(None),
        )
        .order_by(Zabezpieczenie.rodzaj)
    ).all()
    return [ZabezpieczenieWyjscie.model_validate(w) for w in wiersze]


@router.post(
    "/okresy-najmu/{okres_id}/zabezpieczenia",
    response_model=ZabezpieczenieWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaje zabezpieczenie",
)
def dodaj_zabezpieczenie(
    okres_id: int,
    dane: ZabezpieczenieWejscie,
    baza: SesjaBazy,
    kto: Zarzadca,
    request: Request,
) -> ZabezpieczenieWyjscie:
    _okres(baza, okres_id)
    zabezpieczenie = Zabezpieczenie(okres_najmu_id=okres_id, **dane.model_dump())
    baza.add(zabezpieczenie)
    baza.flush()
    zapisz_zmiane(
        baza,
        zabezpieczenie,
        operacja=OperacjaAudytu.UTWORZENIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return ZabezpieczenieWyjscie.model_validate(zabezpieczenie)


# ------------------------------------------------------------------ przeglady


@router.get(
    "/lokale/{lokal_id}/przeglady",
    response_model=list[PrzegladWyjscie],
    summary="Obowiązki przeglądów dla lokalu",
)
def lista_przegladow(lokal_id: int, baza: SesjaBazy, _: Podglad) -> list[PrzegladWyjscie]:
    wiersze = baza.scalars(
        select(ObowiazekPrzegladu)
        .where(
            ObowiazekPrzegladu.lokal_id == lokal_id,
            ObowiazekPrzegladu.usunieto_dnia.is_(None),
        )
        .order_by(ObowiazekPrzegladu.element)
    ).all()
    return [PrzegladWyjscie.model_validate(w) for w in wiersze]


@router.post(
    "/przeglady",
    response_model=PrzegladWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaje obowiązek przeglądu",
)
def dodaj_przeglad(
    dane: PrzegladWejscie, baza: SesjaBazy, kto: Zarzadca, request: Request
) -> PrzegladWyjscie:
    if baza.get(Lokal, dane.lokal_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wskazany lokal nie istnieje.")

    przeglad = ObowiazekPrzegladu(**dane.model_dump())
    _przelicz_przeglad(przeglad, date.today())
    baza.add(przeglad)
    baza.flush()
    zapisz_zmiane(
        baza,
        przeglad,
        operacja=OperacjaAudytu.UTWORZENIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return PrzegladWyjscie.model_validate(przeglad)


@router.post(
    "/przeglady/{przeglad_id}/protokol",
    response_model=PrzegladWyjscie,
    summary="Rejestruje protokół z przeglądu",
)
def zarejestruj_protokol(
    przeglad_id: int,
    baza: SesjaBazy,
    kto: Operator,
    request: Request,
    data_protokolu: Annotated[date, Query(description="Data z protokołu przeglądu")],
    dokument_id: int | None = None,
) -> PrzegladWyjscie:
    """Wgranie protokolu przesuwa termin do przodu. To jedyna taka sciezka (R7)."""
    przeglad = baza.get(ObowiazekPrzegladu, przeglad_id)
    if przeglad is None or przeglad.usunieto_dnia is not None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Przegląd o numerze {przeglad_id} nie istnieje."
        )

    przeglad.ostatni_przeglad_data = data_protokolu
    if dokument_id is not None:
        przeglad.protokol_dokument_id = dokument_id
    _przelicz_przeglad(przeglad, date.today())

    zapisz_zmiane(
        baza,
        przeglad,
        operacja=OperacjaAudytu.ZMIANA,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return PrzegladWyjscie.model_validate(przeglad)


@router.put(
    "/zabezpieczenia/{zabezpieczenie_id}",
    response_model=ZabezpieczenieWyjscie,
    summary="Zmienia zabezpieczenie",
)
def zmien_zabezpieczenie(
    zabezpieczenie_id: int,
    dane: ZabezpieczenieZmiana,
    baza: SesjaBazy,
    kto: Zarzadca,
    request: Request,
) -> ZabezpieczenieWyjscie:
    """Odnotowanie wplaty kaucji albo dostarczenia polisy to codzienna praca,
    a nie wyjatkowa operacja. Przejscie statusu sprawdza maszyna stanow z R4.
    """
    zabezpieczenie = baza.get(Zabezpieczenie, zabezpieczenie_id)
    if zabezpieczenie is None or zabezpieczenie.usunieto_dnia is not None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Zabezpieczenie o numerze {zabezpieczenie_id} nie istnieje.",
        )
    if zabezpieczenie.wersja != dane.wersja:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"Zabezpieczenie zostało w międzyczasie zmienione "
                f"(twoja wersja: {dane.wersja}, aktualna: {zabezpieczenie.wersja}). "
                "Odśwież widok i wprowadź zmiany ponownie."
            ),
            headers={"X-Wersja-Biezaca": str(zabezpieczenie.wersja)},
        )

    if dane.status is not zabezpieczenie.status:
        sprawdz_przejscie(PRZEJSCIA_ZABEZPIECZENIA, zabezpieczenie.status, dane.status)

    for pole, wartosc in dane.model_dump(exclude={"wersja"}).items():
        setattr(zabezpieczenie, pole, wartosc)

    zapisz_zmiane(
        baza,
        zabezpieczenie,
        operacja=OperacjaAudytu.ZMIANA,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return ZabezpieczenieWyjscie.model_validate(zabezpieczenie)
