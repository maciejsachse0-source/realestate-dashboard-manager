"""Lista lokali dla dashboardu i stan efektywny na dzien.

To jest najwazniejszy endpoint w calym API. Dashboard to w praktyce jedna
bardzo dobra tabela (koncepcja, sekcja 7.1), a ten endpoint ja zasila.

Kwoty ida w JSON jako tekst. JSON nie ma typu dziesietnego, a `float` po drodze
gubi grosze. Front i tak niczego na nich nie liczy, tylko formatuje.
"""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, selectinload

from najem.auth.zaleznosci import Podglad
from najem.baza import SesjaBazy
from najem.domena.parametry import WartoscParametru, stan_efektywny
from najem.domena.reguly.data_zakonczenia import data_zakonczenia
from najem.domena.reguly.kompletnosc import POLA_KRYTYCZNE, ocen_kompletnosc
from najem.domena.slowniki import (
    StatusLokalu,
    StatusOkresuNajmu,
    StatusZdarzenia,
    TypLokalu,
    TypWartosci,
)
from najem.modele import Budynek, Lokal, Najemca, OkresNajmu, Zdarzenie
from najem.repozytoria.stan_umowy import na_wartosc_domenowa, wypelnione_pola
from najem.schematy.kartoteka import LokalNaLiscie, StanNaDzien, WartoscStanu
from najem.schematy.wspolne import LIMIT_DOMYSLNY, LIMIT_MAKSYMALNY, Strona

router = APIRouter(tags=["dashboard"])

#: Po czym wolno sortowac liste. Biala lista, zeby nie wpuszczac dowolnego
#: tekstu do klauzuli ORDER BY.
SORTOWANIE: dict[str, InstrumentedAttribute[Any]] = {
    "oznaczenie": Lokal.oznaczenie,
    "budynek": Budynek.nazwa,
    "powierzchnia": Lokal.powierzchnia_ewidencyjna,
    "status": Lokal.status,
    "data_zakonczenia": OkresNajmu.data_zakonczenia_planowana,
}

#: Statusy okresu najmu, ktore uznajemy za "biezaca umowe lokalu".
STATUSY_BIEZACE = (
    StatusOkresuNajmu.PRZYGOTOWANIE,
    StatusOkresuNajmu.AKTYWNA,
    StatusOkresuNajmu.WYPOWIEDZIANA,
)


def _biezacy_okres(lokal: Lokal) -> OkresNajmu | None:
    """Umowa, ktora lokal ma teraz. Zakonczone ida do historii (decyzja D1)."""
    czynne = [
        o for o in lokal.okresy_najmu if o.usunieto_dnia is None and o.status in STATUSY_BIEZACE
    ]
    if not czynne:
        return None
    return max(czynne, key=lambda o: (o.data_zawarcia or date.min, o.id))


def _koniec_umowy(okres: OkresNajmu) -> tuple[date | None, str | None]:
    """Data zakonczenia albo powod, dla ktorego jej nie ma (regula R1)."""
    if okres.data_zakonczenia_faktyczna is not None:
        return okres.data_zakonczenia_faktyczna, None
    wynik = data_zakonczenia(
        bazuje_na=okres.bazuje_na_dacie,
        okres_miesiace=okres.okres_zawarcia_miesiace,
        data_zawarcia=okres.data_zawarcia,
        data_przekazania=okres.data_przekazania,
    )
    return wynik.wartosc, wynik.powod_braku


@router.get(
    "/lokale",
    response_model=Strona[LokalNaLiscie],
    summary="Lista lokali z filtrowaniem, sortowaniem i wyszukiwaniem",
)
def lista_lokali(
    baza: SesjaBazy,
    _: Podglad,
    limit: Annotated[int, Query(ge=1, le=LIMIT_MAKSYMALNY)] = LIMIT_DOMYSLNY,
    offset: Annotated[int, Query(ge=0)] = 0,
    budynek_id: int | None = None,
    status_lokalu: StatusLokalu | None = None,
    typ: TypLokalu | None = None,
    status_umowy: StatusOkresuNajmu | None = None,
    koniec_od: Annotated[date | None, Query(description="Umowy kończące się od tej daty")] = None,
    koniec_do: Annotated[date | None, Query(description="Umowy kończące się do tej daty")] = None,
    waloryzacja: Annotated[bool | None, Query(description="Tylko umowy z waloryzacją")] = None,
    niekompletne: Annotated[
        bool | None, Query(description="Tylko lokale z niekompletnym profilem")
    ] = None,
    szukaj: Annotated[str | None, Query(max_length=200)] = None,
    sortuj: Annotated[str, Query(description="Kolumna sortowania")] = "oznaczenie",
    malejaco: bool = False,
    na_dzien: date | None = None,
) -> Strona[LokalNaLiscie]:
    if sortuj not in SORTOWANIE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Nieznana kolumna sortowania: {sortuj}. Dostępne: {', '.join(sorted(SORTOWANIE))}.",
        )

    dzien = na_dzien or date.today()

    warunki: list[ColumnElement[bool]] = [Lokal.usunieto_dnia.is_(None)]
    if budynek_id is not None:
        warunki.append(Lokal.budynek_id == budynek_id)
    if status_lokalu is not None:
        warunki.append(Lokal.status == status_lokalu)
    if typ is not None:
        warunki.append(Lokal.typ == typ)
    if szukaj:
        wzorzec = f"%{szukaj.strip()}%"
        warunki.append(
            or_(
                Lokal.oznaczenie.ilike(wzorzec),
                Budynek.nazwa.ilike(wzorzec),
                Najemca.nazwa_pelna.ilike(wzorzec),
            )
        )

    # Filtry dotyczace umowy wymagają dołączenia okresu najmu. Robimy to zawsze,
    # bo wyszukiwarka i tak przeszukuje nazwę najemcy.
    zapytanie: Select[tuple[Lokal]] = (
        select(Lokal)
        .join(Budynek, Budynek.id == Lokal.budynek_id)
        .outerjoin(
            OkresNajmu,
            (OkresNajmu.lokal_id == Lokal.id)
            & OkresNajmu.usunieto_dnia.is_(None)
            & OkresNajmu.status.in_(STATUSY_BIEZACE),
        )
        .outerjoin(Najemca, Najemca.id == OkresNajmu.najemca_id)
    )

    if status_umowy is not None:
        warunki.append(OkresNajmu.status == status_umowy)
    if koniec_od is not None:
        warunki.append(OkresNajmu.data_zakonczenia_planowana >= koniec_od)
    if koniec_do is not None:
        warunki.append(OkresNajmu.data_zakonczenia_planowana <= koniec_do)
    if waloryzacja is not None:
        warunki.append(OkresNajmu.waloryzacja_podlega.is_(waloryzacja))

    zapytanie = zapytanie.where(*warunki)

    kolumna = SORTOWANIE[sortuj]
    zapytanie = zapytanie.order_by(kolumna.desc() if malejaco else kolumna.asc(), Lokal.id)

    wszystkich = (
        baza.scalar(
            select(func.count())
            .select_from(Lokal)
            .join(Budynek, Budynek.id == Lokal.budynek_id)
            .outerjoin(
                OkresNajmu,
                (OkresNajmu.lokal_id == Lokal.id)
                & OkresNajmu.usunieto_dnia.is_(None)
                & OkresNajmu.status.in_(STATUSY_BIEZACE),
            )
            .outerjoin(Najemca, Najemca.id == OkresNajmu.najemca_id)
            .where(*warunki)
        )
        or 0
    )

    lokale = (
        baza.scalars(
            zapytanie.options(
                selectinload(Lokal.budynek),
                selectinload(Lokal.okresy_najmu).selectinload(OkresNajmu.parametry),
                selectinload(Lokal.okresy_najmu).selectinload(OkresNajmu.najemca),
                selectinload(Lokal.okresy_najmu).selectinload(OkresNajmu.zabezpieczenia),
                selectinload(Lokal.okresy_najmu).selectinload(OkresNajmu.skladniki_oplat),
            )
            .limit(limit)
            .offset(offset)
        )
        .unique()
        .all()
    )

    liczniki = _liczniki_zdarzen(baza, [lokal.id for lokal in lokale])

    wiersze = [_wiersz(lokal, dzien, liczniki.get(lokal.id, 0)) for lokal in lokale]

    if niekompletne is not None:
        # Filtr po kompletnosci dziala na wyliczonym wierszu, bo kompletnosc
        # wynika ze stanu efektywnego, a nie z pojedynczej kolumny.
        wiersze = [w for w in wiersze if (w.kompletnosc_procent != 100) is niekompletne]

    return Strona(pozycje=wiersze, wszystkich=wszystkich, limit=limit, offset=offset)


def _liczniki_zdarzen(baza: SesjaBazy, lokale_id: list[int]) -> dict[int, int]:
    if not lokale_id:
        return {}
    wiersze = baza.execute(
        select(Zdarzenie.lokal_id, func.count())
        .where(
            Zdarzenie.lokal_id.in_(lokale_id),
            Zdarzenie.status == StatusZdarzenia.OTWARTE,
            Zdarzenie.usunieto_dnia.is_(None),
        )
        .group_by(Zdarzenie.lokal_id)
    ).all()
    return {lokal_id: ile for lokal_id, ile in wiersze if lokal_id is not None}


def _wiersz(lokal: Lokal, dzien: date, zdarzen: int) -> LokalNaLiscie:
    wiersz = LokalNaLiscie(
        lokal_id=lokal.id,
        budynek_id=lokal.budynek_id,
        budynek_nazwa=lokal.budynek.nazwa,
        oznaczenie=lokal.oznaczenie,
        typ=lokal.typ,
        status_lokalu=lokal.status,
        powierzchnia_ewidencyjna=lokal.powierzchnia_ewidencyjna,
        zdarzen_otwartych=zdarzen,
    )

    okres = _biezacy_okres(lokal)
    if okres is None:
        return wiersz

    koniec, powod = _koniec_umowy(okres)
    wartosci = [
        w
        for w in (na_wartosc_domenowa(p) for p in okres.parametry if p.usunieto_dnia is None)
        if w is not None
    ]
    stan = stan_efektywny(wartosci, dzien)
    czynsz = stan.get("czynsz_podstawowy")
    ocena = ocen_kompletnosc(wypelnione_pola(okres, dzien, koniec), POLA_KRYTYCZNE)

    wiersz.okres_najmu_id = okres.id
    wiersz.najemca_id = okres.najemca_id
    wiersz.najemca_nazwa = okres.najemca.nazwa_pelna
    wiersz.status_umowy = okres.status
    wiersz.data_przekazania = okres.data_przekazania
    wiersz.data_zakonczenia = koniec
    wiersz.powod_braku_daty_zakonczenia = powod
    wiersz.waloryzacja_podlega = okres.waloryzacja_podlega
    wiersz.kompletnosc_procent = ocena.procent
    wiersz.brakujace_pola = sorted(ocena.brakujace)

    if czynsz is not None and czynsz.kwota is not None:
        wiersz.czynsz = str(czynsz.kwota.wartosc)
        wiersz.czynsz_waluta = czynsz.kwota.waluta
        wiersz.czynsz_rodzaj = czynsz.kwota.rodzaj.value

    return wiersz


@router.get(
    "/lokale/{lokal_id}/stan",
    response_model=StanNaDzien,
    summary="Stan efektywny lokalu na wskazany dzień",
)
def stan_lokalu(
    lokal_id: int,
    baza: SesjaBazy,
    _: Podglad,
    na_dzien: Annotated[
        date | None, Query(description="Domyślnie dzisiaj. Pozwala cofnąć się w czasie.")
    ] = None,
) -> StanNaDzien:
    """Odpowiedz na pytanie 'jaka byla stawka w maju 2025' (decyzja D2)."""
    lokal = baza.get(Lokal, lokal_id)
    if lokal is None or lokal.usunieto_dnia is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Lokal o numerze {lokal_id} nie istnieje.")

    dzien = na_dzien or date.today()
    okres = _biezacy_okres(lokal)

    if okres is None:
        return StanNaDzien(
            lokal_id=lokal_id,
            okres_najmu_id=None,
            na_dzien=dzien,
            parametry={},
            brakujace_pola=sorted(POLA_KRYTYCZNE),
            kompletnosc_procent=0,
            data_zakonczenia=None,
            powod_braku_daty_zakonczenia="Lokal nie ma bieżącej umowy najmu.",
        )

    koniec, powod = _koniec_umowy(okres)
    zywe = [p for p in okres.parametry if p.usunieto_dnia is None]
    wartosci = [w for w in (na_wartosc_domenowa(p) for p in zywe) if w is not None]
    stan = stan_efektywny(wartosci, dzien)
    ocena = ocen_kompletnosc(wypelnione_pola(okres, dzien, koniec), POLA_KRYTYCZNE)

    # Slad do dokumentu bierzemy z wiersza bazy, bo struktura domenowa
    # nie niesie numeru strony ani paragrafu.
    po_id = {p.id: p for p in zywe}

    parametry: dict[str, WartoscStanu] = {}
    for klucz, wartosc in stan.items():
        wiersz = po_id.get(wartosc.identyfikator or -1)
        parametry[klucz] = WartoscStanu(
            klucz=klucz,
            typ=wartosc.typ.value,
            wartosc=_tekst_wartosci(wartosc.typ, wartosc),
            waluta=wartosc.kwota.waluta if wartosc.kwota else None,
            rodzaj_kwoty=wartosc.kwota.rodzaj.value if wartosc.kwota else None,
            stawka_vat=wartosc.kwota.stawka_vat if wartosc.kwota else None,
            obowiazuje_od=wartosc.obowiazuje_od,
            obowiazuje_do=wartosc.obowiazuje_do,
            status_weryfikacji=wartosc.status.value,
            dokument_zrodlowy_id=wartosc.dokument_zrodlowy_id,
            zrodlo_strona=wiersz.zrodlo_strona if wiersz else None,
            zrodlo_paragraf=wiersz.zrodlo_paragraf if wiersz else None,
        )

    return StanNaDzien(
        lokal_id=lokal_id,
        okres_najmu_id=okres.id,
        na_dzien=dzien,
        parametry=parametry,
        brakujace_pola=sorted(ocena.brakujace),
        kompletnosc_procent=ocena.procent,
        data_zakonczenia=koniec,
        powod_braku_daty_zakonczenia=powod,
    )


def _tekst_wartosci(typ: TypWartosci, wartosc: WartoscParametru) -> str:
    """Wartosc jako tekst. Kwoty i liczby ida jako tekst, zeby nie zgubic groszy."""
    match typ:
        case TypWartosci.KWOTA:
            return str(wartosc.kwota.wartosc) if wartosc.kwota else ""
        case TypWartosci.LICZBA:
            return str(wartosc.liczba)
        case TypWartosci.DATA:
            return wartosc.data.isoformat() if wartosc.data else ""
        case TypWartosci.FLAGA:
            return "tak" if wartosc.flaga else "nie"
        case TypWartosci.TEKST:
            return str(wartosc.tekst)
