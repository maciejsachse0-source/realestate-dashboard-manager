"""Klient HTTP pracujacy na tej samej transakcji, co test.

Endpointy wolaja `commit()`, wiec bez podmiany sesji kazdy test zostawialby
dane w bazie. Sesja testowa dziala na zagniezdzonym punkcie zapisu, wiec
`commit()` zwalnia punkt, a wycofanie na koncu testu i tak sprzata wszystko.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from najem.auth.haslo import zahaszuj
from najem.auth.sesje import NAZWA_CIASTECZKA, zaloguj
from najem.baza import sesja as zaleznosc_sesji
from najem.baza import silnik
from najem.domena.slowniki import RolaUzytkownika
from najem.main import app
from najem.modele import Budynek, Lokal, Najemca, Uzytkownik

HASLO = "TestoweHaslo123"


@pytest.fixture(scope="session")
def polaczenie_api() -> Iterator[Connection]:
    try:
        pol = silnik.connect()
    except OperationalError as blad:
        pytest.skip(
            f"Baza nie odpowiada, pomijam testy API. Szczegóły: {str(blad).splitlines()[0]}"
        )
    wersja = pol.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
    pol.rollback()
    if wersja is None:
        pol.close()
        pytest.skip("Brak tabel. Uruchom: uv run alembic upgrade head")
    yield pol
    pol.close()


@pytest.fixture
def baza(polaczenie_api: Connection) -> Iterator[Session]:
    transakcja = polaczenie_api.begin()
    s = Session(bind=polaczenie_api, join_transaction_mode="create_savepoint")
    try:
        yield s
    finally:
        s.close()
        transakcja.rollback()


@pytest.fixture
def klient(baza: Session) -> Iterator[TestClient]:
    """Klient bez zalogowanego uzytkownika."""
    app.dependency_overrides[zaleznosc_sesji] = lambda: baza
    # TestClient bez kontekstu `with` nie uruchamia cyklu zycia aplikacji.
    # Nie chcemy przy kazdym tescie startowac harmonogramu ani zakladac
    # konta poczatkowego - to zachowanie ma wlasne testy.
    yield TestClient(app)
    app.dependency_overrides.clear()


def _uzytkownik(baza: Session, rola: RolaUzytkownika) -> Uzytkownik:
    u = Uzytkownik(
        login=f"test_{rola.value}",
        imie_nazwisko=f"Testowy {rola.value}",
        rola=rola,
        hash_hasla=zahaszuj(HASLO),
        wymaga_zmiany_hasla=False,
    )
    baza.add(u)
    baza.flush()
    return u


def zaloguj_jako(klient: TestClient, baza: Session, rola: RolaUzytkownika) -> Uzytkownik:
    """Zaklada konto o podanej roli i ustawia ciasteczko sesyjne w kliencie."""
    uzytkownik = _uzytkownik(baza, rola)
    _, token = zaloguj(baza, login=uzytkownik.login, haslo=HASLO, teraz=datetime.now(UTC))
    klient.cookies.set(NAZWA_CIASTECZKA, token)
    return uzytkownik


@pytest.fixture
def klient_podglad(klient: TestClient, baza: Session) -> TestClient:
    zaloguj_jako(klient, baza, RolaUzytkownika.PODGLAD)
    return klient


@pytest.fixture
def klient_zarzadca(klient: TestClient, baza: Session) -> TestClient:
    zaloguj_jako(klient, baza, RolaUzytkownika.ZARZADCA)
    return klient


@pytest.fixture
def klient_admin(klient: TestClient, baza: Session) -> TestClient:
    zaloguj_jako(klient, baza, RolaUzytkownika.ADMINISTRATOR)
    return klient


@pytest.fixture
def budynek_api(baza: Session) -> Budynek:
    b = Budynek(nazwa="18A", adres="ul. Przykładowa 18A")
    baza.add(b)
    baza.flush()
    return b


@pytest.fixture
def lokal_api(baza: Session, budynek_api: Budynek) -> Lokal:
    from decimal import Decimal

    from najem.domena.slowniki import TypLokalu

    lok = Lokal(
        budynek_id=budynek_api.id,
        oznaczenie="18A/12",
        typ=TypLokalu.HANDLOWY,
        powierzchnia_ewidencyjna=Decimal("128.50"),
    )
    baza.add(lok)
    baza.flush()
    return lok


@pytest.fixture
def najemca_api(baza: Session) -> Najemca:
    n = Najemca(nazwa_pelna="Przykładowa Spółka z o.o.", nip="1234563218")
    baza.add(n)
    baza.flush()
    return n
