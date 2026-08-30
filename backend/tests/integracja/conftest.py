"""Wspolne przygotowanie testow integracyjnych.

Kazdy test dostaje wlasna transakcje, ktora jest wycofywana po jego zakonczeniu.
Dzieki temu testy nie zostawiaja po sobie danych i moga isc w dowolnej kolejnosci.
"""

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from najem.baza import silnik
from najem.domena.slowniki import TypLokalu
from najem.modele import Budynek, Lokal, Najemca


@pytest.fixture(scope="session")
def polaczenie() -> Iterator[Connection]:
    """Jedno polaczenie na caly przebieg. Pomija testy, gdy baza nie stoi."""
    try:
        pol = silnik.connect()
    except OperationalError as blad:
        pytest.skip(
            "Baza nie odpowiada, pomijam testy integracyjne. "
            "Uruchom: powershell -File narzedzia/lokalny-postgres.ps1 start\n"
            f"Szczegoly: {str(blad).splitlines()[0]}"
        )

    # Migracje musza byc zaaplikowane. Test na pustej bazie mowilby, ze wszystko
    # jest zle, zamiast powiedziec, ze zapomniano o "alembic upgrade head".
    wersja = pol.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
    # SQLAlchemy 2.0 otwiera transakcje sam przy pierwszym zapytaniu. Bez tego
    # wycofania kazdy test dostawalby "connection has already initialized
    # a Transaction" przy wlasnym begin().
    pol.rollback()
    if wersja is None:
        pol.close()
        pytest.skip("Brak tabel. Uruchom: uv run alembic upgrade head")

    yield pol
    pol.close()


@pytest.fixture
def sesja(polaczenie: Connection) -> Iterator[Session]:
    """Sesja w transakcji wycofywanej po tescie."""
    transakcja = polaczenie.begin()
    s = Session(bind=polaczenie, join_transaction_mode="create_savepoint")
    try:
        yield s
    finally:
        s.close()
        transakcja.rollback()


@pytest.fixture
def budynek(sesja: Session) -> Budynek:
    b = Budynek(nazwa="18A", adres="ul. Przykladowa 18A")
    sesja.add(b)
    sesja.flush()
    return b


@pytest.fixture
def lokal(sesja: Session, budynek: Budynek) -> Lokal:
    lok = Lokal(
        budynek_id=budynek.id,
        oznaczenie="18A/12",
        typ=TypLokalu.HANDLOWY,
        powierzchnia_ewidencyjna=Decimal("128.50"),
    )
    sesja.add(lok)
    sesja.flush()
    return lok


@pytest.fixture
def najemca(sesja: Session) -> Najemca:
    n = Najemca(nazwa_pelna="Przykladowa Spolka z o.o.", nip="1234563218")
    sesja.add(n)
    sesja.flush()
    return n


@pytest.fixture
def dzis() -> date:
    """Data odniesienia w testach. Stala, zeby testy byly deterministyczne."""
    return date(2026, 8, 25)
