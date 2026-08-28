"""Jedyne miejsce w projekcie czytajace zmienne srodowiskowe."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

KATALOG_REPO = Path(__file__).resolve().parents[3]


class Ustawienia(BaseSettings):
    """Konfiguracja aplikacji. Wszystko przez zmienne srodowiskowe, zero sekretow w repo."""

    model_config = SettingsConfigDict(
        env_file=(KATALOG_REPO / ".env"),
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

    # Strefa prezentacji. W bazie i w logice zawsze UTC (plan, sekcja 1.1 punkt D).
    strefa_prezentacji: str = Field(default="Europe/Warsaw", alias="STREFA_PREZENTACJI")

    @property
    def czy_produkcja(self) -> bool:
        return self.srodowisko == "prod"


@lru_cache
def ustawienia() -> Ustawienia:
    return Ustawienia()
