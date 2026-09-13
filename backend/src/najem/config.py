"""Jedyne miejsce w projekcie czytajace zmienne srodowiskowe."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

KATALOG_REPO = Path(__file__).resolve().parents[3]


def _plik_env() -> Path:
    """Skad czytamy .env.

    W repozytorium lezy on obok kodu i tak zostaje. W instalacji u uzytkownika
    nalezy do danych, a nie do programu: aktualizacja podmienia katalog
    z kodem, wiec konfiguracja trzymana w srodku ginelaby przy kazdym wydaniu.
    Sciezke podaje wtedy narzedzia/sciezki.ps1 przez NAJEM_PLIK_ENV.
    """
    wskazany = os.environ.get("NAJEM_PLIK_ENV")
    return Path(wskazany) if wskazany else KATALOG_REPO / ".env"


class Ustawienia(BaseSettings):
    """Konfiguracja aplikacji. Wszystko przez zmienne srodowiskowe, zero sekretow w repo."""

    model_config = SettingsConfigDict(
        env_file=_plik_env(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    srodowisko: str = Field(default="dev", alias="SRODOWISKO")
    baza_url: str = Field(
        default="postgresql+psycopg://najem:najem@127.0.0.1:5434/najem",
        alias="DATABASE_URL",
    )
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8010, alias="API_PORT")

    # Katalog na dokumenty uzytkownikow. Celowo poza obszarem serwowanym przez web
    # (plan, sekcja 1.2 punkt L).
    katalog_dokumentow: Path = Field(
        default=KATALOG_REPO / "dane" / "dokumenty", alias="KATALOG_DOKUMENTOW"
    )

    # Katalog z dokumentami uzytkownika na dysku, skanowany w poszukiwaniu umow.
    # Program niczego stad nie kopiuje ani nie przenosi: zaimportowany dokument
    # zostaje odnosnikiem do pliku lezacego w tym drzewie. Pusta wartosc znaczy
    # "nie skanujemy nic" i wtedy caly ekran skanu mowi, co ustawic.
    katalog_skanu: Path | None = Field(default=None, alias="KATALOG_SKANU")

    @field_validator("katalog_skanu", mode="before")
    @classmethod
    def _brak_katalogu_to_none(cls, wartosc: object) -> object:
        """Pusta wartosc w .env ma znaczyc "nie ustawiono", a nie "katalog biezacy".

        Instalator zapisuje `KATALOG_SKANU=` bez wartosci, bo katalog wskazuje
        sie dopiero w programie. Bez tego `Path("")` daje `Path(".")`, a to jest
        istniejacy katalog -- katalog roboczy serwera. Skan przechodzil wiec
        przez `is_dir()`, meldowal "dostepny" i pokazywal uzytkownikowi
        `alembic` i `src` jako jego budynki. Zamiast komunikatu "wskaz katalog"
        pierwszy ekran programu pokazywal wnetrze samego programu.

        Kropke traktujemy tak samo: nikt nie trzyma umow w katalogu roboczym
        serwera, wiec jest to slad po pustej wartosci, a nie decyzja.
        """
        if not isinstance(wartosc, str):
            return wartosc
        czysty = wartosc.strip().strip('"').strip("'").strip()
        return None if czysty in ("", ".") else czysty

    # Strefa prezentacji. W bazie i w logice zawsze UTC (plan, sekcja 1.1 punkt D).
    strefa_prezentacji: str = Field(default="Europe/Warsaw", alias="STREFA_PREZENTACJI")

    @property
    def czy_produkcja(self) -> bool:
        return self.srodowisko == "prod"


@lru_cache
def ustawienia() -> Ustawienia:
    return Ustawienia()
