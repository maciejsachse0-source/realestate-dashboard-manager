"""Endpoint administracyjny generatora zdarzen.

Przydatny w testach, przy diagnozowaniu i przy pierwszym uruchomieniu systemu,
gdy nikt nie chce czekac do 6:00 rano.

Uwierzytelnianie i role wchodza w etapie E4. Do tego czasu endpoint jest otwarty,
ale aplikacja slucha wylacznie na petli zwrotnej.
"""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, case, func, or_, select

from najem.baza import SesjaBazy
from najem.domena.kalendarz import dni_do
from najem.domena.slowniki import (
    OperacjaAudytu,
    StatusZdarzenia,
    TypZdarzenia,
    WagaZdarzenia,
)
from najem.domena.stany import PRZEJSCIA_ZDARZENIA, sprawdz_przejscie
from najem.modele import Lokal, Zdarzenie
from najem.schematy.kartoteka import (
    ObslugaZdarzenia,
    OdroczenieZdarzenia,
    ZdarzenieWyjscie,
)
from najem.schematy.wspolne import LIMIT_DOMYSLNY, LIMIT_MAKSYMALNY, Strona
from najem.uslugi.audyt import zapisz_zmiane
from najem.uslugi.generator_zdarzen import uruchom_generator
from najem.zadania.harmonogram import dzis_lokalnie


def na_wyjscie(zdarzenie: Zdarzenie) -> ZdarzenieWyjscie:
    """Zdarzenie z policzona liczba dni do terminu.

    Liczymy tutaj, a nie w przegladarce, bo wyliczenia naleza do API
    (CLAUDE.md, zasady architektury). Dzien odniesienia bierzemy w strefie
    prezentacji: o drugiej w nocy UTC pokazuje jeszcze dzien poprzedni,
    a "zostaly 3 dni" musi znaczyc trzy polskie dni.
    """
    wyjscie = ZdarzenieWyjscie.model_validate(zdarzenie)
    wyjscie.dni_do_terminu = dni_do(zdarzenie.data_zdarzenia, dzis_lokalnie())
    return wyjscie


#: Krytyczne na gorze, potem ostrzezenia, na koncu informacje.
KOLEJNOSC_WAGI = case(
    (Zdarzenie.waga == WagaZdarzenia.KRYTYCZNE, 0),
    (Zdarzenie.waga == WagaZdarzenia.OSTRZEZENIE, 1),
    else_=2,
)

router = APIRouter(prefix="/zdarzenia", tags=["zdarzenia"])


class WynikPrzebiegu(BaseModel):
    data_odniesienia: date
    umow_sprawdzonych: int = Field(description="Ile okresów najmu przeszło przez generator")
    zdarzen_wyliczonych: int = Field(description="Ile zdarzeń powinno istnieć na ten dzień")
    zdarzen_dodanych: int = Field(description="Ile faktycznie dopisano")
    zdarzen_pominietych: int = Field(description="Ile już było w bazie")


@router.post(
    "/generuj",
    response_model=WynikPrzebiegu,
    summary="Uruchamia generator zdarzeń ręcznie",
)
def generuj(
    sesja: SesjaBazy,
    na_dzien: Annotated[
        date | None,
        Query(description="Data odniesienia. Domyślnie dzisiaj w strefie prezentacji."),
    ] = None,
) -> WynikPrzebiegu:
    wynik = uruchom_generator(sesja, na_dzien or dzis_lokalnie())
    sesja.commit()
    return WynikPrzebiegu(
        data_odniesienia=wynik.data_odniesienia,
        umow_sprawdzonych=wynik.umow_sprawdzonych,
        zdarzen_wyliczonych=wynik.zdarzen_wyliczonych,
        zdarzen_dodanych=wynik.zdarzen_dodanych,
        zdarzen_pominietych=wynik.zdarzen_pominietych,
    )


@router.get("", response_model=Strona[ZdarzenieWyjscie], summary="Kokpit terminów")
def lista_zdarzen(
    sesja: SesjaBazy,
    limit: Annotated[int, Query(ge=1, le=LIMIT_MAKSYMALNY)] = LIMIT_DOMYSLNY,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_zdarzenia: StatusZdarzenia | None = StatusZdarzenia.OTWARTE,
    waga: WagaZdarzenia | None = None,
    typ: TypZdarzenia | None = None,
    lokal_id: int | None = None,
    budynek_id: int | None = None,
    do_dnia: Annotated[date | None, Query(description="Tylko zdarzenia do tej daty")] = None,
) -> Strona[ZdarzenieWyjscie]:
    """Zdarzenia pogrupowane wedlug pilnosci (koncepcja, sekcja 7.3).

    Sortowanie: najpierw krytyczne, potem najstarsze. Zdarzenie odroczone
    z terminem w przyszlosci jest ukryte do czasu, gdy termin nadejdzie -
    inaczej odroczenie niczego nie zalatwia.
    """
    warunki: list[ColumnElement[bool]] = [Zdarzenie.usunieto_dnia.is_(None)]
    if status_zdarzenia is not None:
        warunki.append(Zdarzenie.status == status_zdarzenia)
    if waga is not None:
        warunki.append(Zdarzenie.waga == waga)
    if typ is not None:
        warunki.append(Zdarzenie.typ == typ)
    if lokal_id is not None:
        warunki.append(Zdarzenie.lokal_id == lokal_id)
    if do_dnia is not None:
        warunki.append(Zdarzenie.data_zdarzenia <= do_dnia)

    zapytanie = select(Zdarzenie)
    liczba = select(func.count()).select_from(Zdarzenie)
    if budynek_id is not None:
        zapytanie = zapytanie.join(Lokal, Lokal.id == Zdarzenie.lokal_id)
        liczba = liczba.join(Lokal, Lokal.id == Zdarzenie.lokal_id)
        warunki.append(Lokal.budynek_id == budynek_id)

    # Odroczone czekaja do swojego terminu.
    warunki.append(
        or_(
            Zdarzenie.status != StatusZdarzenia.ODROCZONE,
            Zdarzenie.odroczone_do <= date.today(),
        )
    )

    wszystkich = sesja.scalar(liczba.where(*warunki)) or 0
    pozycje = sesja.scalars(
        zapytanie.where(*warunki)
        .order_by(KOLEJNOSC_WAGI, Zdarzenie.data_zdarzenia, Zdarzenie.id)
        .limit(limit)
        .offset(offset)
    ).all()

    return Strona(
        pozycje=[na_wyjscie(z) for z in pozycje],
        wszystkich=wszystkich,
        limit=limit,
        offset=offset,
    )


def _zdarzenie(sesja: SesjaBazy, zdarzenie_id: int) -> Zdarzenie:
    zdarzenie = sesja.get(Zdarzenie, zdarzenie_id)
    if zdarzenie is None or zdarzenie.usunieto_dnia is not None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Zdarzenie o numerze {zdarzenie_id} nie istnieje."
        )
    return zdarzenie


@router.post(
    "/{zdarzenie_id}/obsluzone",
    response_model=ZdarzenieWyjscie,
    summary="Oznacza zdarzenie jako obsłużone",
)
def oznacz_obsluzone(
    zdarzenie_id: int, dane: ObslugaZdarzenia, sesja: SesjaBazy
) -> ZdarzenieWyjscie:
    zdarzenie = _zdarzenie(sesja, zdarzenie_id)
    sprawdz_przejscie(PRZEJSCIA_ZDARZENIA, zdarzenie.status, StatusZdarzenia.OBSLUZONE)

    zdarzenie.status = StatusZdarzenia.OBSLUZONE
    zdarzenie.obsluzone_dnia = datetime.now(UTC)
    zdarzenie.odroczone_do = None
    if dane.notatka is not None:
        zdarzenie.notatka = dane.notatka

    zapisz_zmiane(sesja, zdarzenie, operacja=OperacjaAudytu.ZMIANA)
    sesja.commit()
    return na_wyjscie(zdarzenie)


@router.post(
    "/{zdarzenie_id}/odroczenie",
    response_model=ZdarzenieWyjscie,
    summary="Odracza zdarzenie z notatką",
)
def odrocz(zdarzenie_id: int, dane: OdroczenieZdarzenia, sesja: SesjaBazy) -> ZdarzenieWyjscie:
    zdarzenie = _zdarzenie(sesja, zdarzenie_id)
    sprawdz_przejscie(PRZEJSCIA_ZDARZENIA, zdarzenie.status, StatusZdarzenia.ODROCZONE)

    if dane.odroczone_do <= date.today():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Termin odroczenia musi być w przyszłości. Inaczej odroczenie niczego nie zmienia.",
        )

    zdarzenie.status = StatusZdarzenia.ODROCZONE
    zdarzenie.odroczone_do = dane.odroczone_do
    if dane.notatka is not None:
        zdarzenie.notatka = dane.notatka

    zapisz_zmiane(sesja, zdarzenie, operacja=OperacjaAudytu.ZMIANA)
    sesja.commit()
    return na_wyjscie(zdarzenie)
