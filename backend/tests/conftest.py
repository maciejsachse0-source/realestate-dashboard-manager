"""Przygotowanie środowiska testowego. Wykonuje się przed importem czegokolwiek z najem.

Testy pracują na **osobnej bazie** `najem_testy`, nigdy na tej, w której leżą
prawdziwe umowy. Powody są dwa i oba są poważne:

1. Praca na produkcyjnych danych w środowisku deweloperskim to RODO plus jedna
   pomyłka w `DELETE` (plan budowy, sekcja 5.3).
2. Testy przestają zależeć od tego, co akurat jest w bazie. Asercja
   „lista jest pusta" nie może psuć się dlatego, że ktoś wprowadził lokal.

Baza testowa powstaje sama przy pierwszym uruchomieniu i dostaje komplet
migracji. Nie trzeba jej zakładać ręcznie.
"""

import os
from urllib.parse import urlparse, urlunparse

import pytest

#: Nazwa bazy testowej. Celowo inna niż produkcyjna i widoczna w `psql \l`.
NAZWA_BAZY_TESTOWEJ = "najem_testy"

#: Klucz na komunikat o niedostępnej bazie testowej.
BLAD_BAZY: pytest.StashKey[str] = pytest.StashKey()


def _zamien_nazwe_bazy(url: str, nowa_nazwa: str) -> str:
    czesci = urlparse(url)
    return urlunparse(czesci._replace(path=f"/{nowa_nazwa}"))


def _przelacz_na_baze_testowa() -> str:
    """Ustawia DATABASE_URL na bazę testową, zanim cokolwiek ją odczyta."""
    from najem.config import Ustawienia, ustawienia

    # Ustawienia() czyta .env i zmienne środowiskowe, więc bierzemy adres,
    # którego użyłby program, i podmieniamy w nim samą nazwę bazy.
    url_testowy = _zamien_nazwe_bazy(Ustawienia().baza_url, NAZWA_BAZY_TESTOWEJ)
    os.environ["DATABASE_URL"] = url_testowy
    # Konfiguracja jest zapamiętywana, więc bez wyczyszczenia pamięci podręcznej
    # reszta programu dalej widziałaby starą bazę.
    ustawienia.cache_clear()
    return url_testowy


def _zaloz_baze_jesli_brak(url: str) -> None:
    """Tworzy bazę testową, jeśli jeszcze nie istnieje.

    Łączymy się z bazą `postgres`, bo do `CREATE DATABASE` trzeba być
    podłączonym do czegoś innego niż baza tworzona.
    """
    import psycopg

    czesci = urlparse(url)
    nazwa = czesci.path.lstrip("/")
    url_serwisowy = urlunparse(czesci._replace(scheme="postgresql", path="/postgres"))

    with psycopg.connect(url_serwisowy, autocommit=True, connect_timeout=3) as polaczenie:
        istnieje = polaczenie.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (nazwa,)
        ).fetchone()
        if istnieje is None:
            # Nazwa jest stałą z tego pliku, nie danymi z zewnątrz.
            polaczenie.execute(f'CREATE DATABASE "{nazwa}"')


def _zaaplikuj_migracje() -> None:
    """Doprowadza bazę testową do najnowszej migracji.

    Dzięki temu zmiana schematu nie wymaga żadnego dodatkowego kroku w testach:
    następne uruchomienie samo ją nałoży.
    """
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    katalog = Path(__file__).resolve().parents[1]
    konfiguracja = Config(str(katalog / "alembic.ini"))
    konfiguracja.set_main_option("script_location", str(katalog / "alembic"))
    command.upgrade(konfiguracja, "head")


def pytest_configure(config: pytest.Config) -> None:
    """Hak pytesta wykonywany przed zebraniem testów, czyli przed ich importami."""
    url = _przelacz_na_baze_testowa()
    try:
        _zaloz_baze_jesli_brak(url)
        _zaaplikuj_migracje()
    except Exception as blad:
        # Brak bazy nie wywala przebiegu: testy warstwy domenowej nie potrzebują
        # jej wcale, a integracyjne same się pominą. Ale komunikat MUSI być
        # widoczny. Pierwsza wersja tego kodu połykała błąd po cichu i przez to
        # baza testowa nigdy nie powstała, a testy pracowały na prawdziwych
        # danych, nie mówiąc o tym ani słowa.
        config.stash[BLAD_BAZY] = str(blad).splitlines()[0]


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Wiersz nagłówka mówiący, na czym testy pracują."""
    blad = config.stash.get(BLAD_BAZY, None)
    if blad:
        return [
            f"UWAGA: baza testowa niedostępna ({blad}).",
            "Testy integracyjne zostaną pominięte. "
            "Uruchom: powershell -File narzedzia/lokalny-postgres.ps1 setup",
        ]
    return [f"baza testowa: {NAZWA_BAZY_TESTOWEJ}"]
