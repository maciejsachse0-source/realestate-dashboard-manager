"""Schematy wejscia i wyjscia dla kartoteki: budynki, lokale, najemcy."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from najem.domena.slowniki import (
    RolaUzytkownika,
    StatusLokalu,
    StatusOkresuNajmu,
    TypLokalu,
)


class Odczyt(BaseModel):
    """Wspolna baza dla schematow wyjsciowych czytanych z modeli ORM."""

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------- budynek


class BudynekWejscie(BaseModel):
    nazwa: str = Field(min_length=1, max_length=80)
    adres: str | None = Field(default=None, max_length=2000)
    aktywny: bool = True
    uwagi: str | None = None


class BudynekZmiana(BudynekWejscie):
    """Zmiana istniejacego rekordu niesie wersje, ktora klient widzial.

    Bez tego optimistic locking nie dziala przez HTTP: serwer wczytuje rekord
    swiezo, nadpisuje go i nigdy nie zauwaza, ze ktos zmienil go w miedzyczasie.
    """

    wersja: int = Field(ge=1, description="Wersja rekordu, na której pracował klient")


class BudynekWyjscie(Odczyt):
    id: int
    nazwa: str
    adres: str | None
    aktywny: bool
    uwagi: str | None
    wersja: int


# ------------------------------------------------------------------- lokal


class LokalWejscie(BaseModel):
    budynek_id: int
    oznaczenie: str = Field(min_length=1, max_length=60)
    typ: TypLokalu
    status: StatusLokalu = StatusLokalu.WOLNY
    kondygnacja: str | None = Field(default=None, max_length=30)
    powierzchnia_ewidencyjna: Decimal | None = Field(default=None, ge=0)
    uwagi: str | None = None

    @field_validator("oznaczenie")
    @classmethod
    def bez_zbednych_spacji(cls, wartosc: str) -> str:
        return wartosc.strip()


class LokalZmiana(LokalWejscie):
    wersja: int = Field(ge=1, description="Wersja rekordu, na której pracował klient")


class LokalWyjscie(Odczyt):
    id: int
    budynek_id: int
    oznaczenie: str
    typ: TypLokalu
    status: StatusLokalu
    kondygnacja: str | None
    powierzchnia_ewidencyjna: Decimal | None
    uwagi: str | None
    wersja: int


class LokalNaLiscie(BaseModel):
    """Wiersz dashboardu. Sklada dane z lokalu, umowy i stanu efektywnego.

    Kwoty ida jako tekst, a nie jako liczba zmiennoprzecinkowa: JSON nie ma
    typu dziesietnego, a `float` po drodze gubi grosze.
    """

    lokal_id: int
    budynek_id: int
    budynek_nazwa: str
    oznaczenie: str
    typ: TypLokalu
    status_lokalu: StatusLokalu
    powierzchnia_ewidencyjna: Decimal | None

    okres_najmu_id: int | None = None
    najemca_id: int | None = None
    najemca_nazwa: str | None = None
    status_umowy: StatusOkresuNajmu | None = None
    data_przekazania: date | None = None
    data_zakonczenia: date | None = None
    powod_braku_daty_zakonczenia: str | None = None

    czynsz: str | None = None
    czynsz_waluta: str | None = None
    czynsz_rodzaj: str | None = None
    waloryzacja_podlega: bool | None = None

    kompletnosc_procent: int | None = None
    brakujace_pola: list[str] = Field(default_factory=list)
    zdarzen_otwartych: int = 0


# ----------------------------------------------------------------- najemca


class NajemcaWejscie(BaseModel):
    nazwa_pelna: str = Field(min_length=1, max_length=300)
    nip: str | None = Field(default=None, max_length=10)
    regon: str | None = Field(default=None, max_length=14)
    krs: str | None = Field(default=None, max_length=10)
    adres_siedziby: str | None = None
    adres_korespondencyjny: str | None = None
    email: str | None = Field(default=None, max_length=254)
    telefon: str | None = Field(default=None, max_length=32)
    osoba_fizyczna: bool = False
    notatki: str | None = None

    @field_validator("nip", "regon", "krs")
    @classmethod
    def same_cyfry(cls, wartosc: str | None) -> str | None:
        if wartosc is None:
            return None
        oczyszczony = "".join(znak for znak in wartosc if znak.isdigit())
        return oczyszczony or None


class NajemcaZmiana(NajemcaWejscie):
    wersja: int = Field(ge=1, description="Wersja rekordu, na której pracował klient")


class NajemcaWyjscie(Odczyt):
    id: int
    nazwa_pelna: str
    nip: str | None
    regon: str | None
    krs: str | None
    adres_siedziby: str | None
    adres_korespondencyjny: str | None
    email: str | None
    telefon: str | None
    osoba_fizyczna: bool
    notatki: str | None
    wersja: int


class UzytkownikNaLiscie(Odczyt):
    """Minimum potrzebne do wyboru osoby na liście. Nic ponad to."""

    id: int
    imie_nazwisko: str
    rola: RolaUzytkownika


# ------------------------------------------------------------ stan na dzien


class WartoscStanu(BaseModel):
    """Jedna pozycja stanu efektywnego wraz ze sladem do zrodla.

    Kazda wartosc pochodzaca z dokumentu jest klikalna i prowadzi do niego
    (koncepcja, sekcja 7.2). Stad `dokument_zrodlowy_id` i lokalizacja.
    """

    klucz: str
    typ: str
    wartosc: str
    waluta: str | None = None
    rodzaj_kwoty: str | None = None
    stawka_vat: Decimal | None = None
    obowiazuje_od: date
    obowiazuje_do: date | None
    status_weryfikacji: str
    dokument_zrodlowy_id: int | None = None
    zrodlo_strona: int | None = None
    zrodlo_paragraf: str | None = None


class StanNaDzien(BaseModel):
    lokal_id: int
    okres_najmu_id: int | None
    na_dzien: date
    parametry: dict[str, WartoscStanu]
    brakujace_pola: list[str]
    kompletnosc_procent: int
    data_zakonczenia: date | None
    powod_braku_daty_zakonczenia: str | None


class ZdarzenieWyjscie(Odczyt):
    id: int
    typ: str
    encja_typ: str
    encja_id: int
    lokal_id: int | None
    data_zdarzenia: date
    waga: str
    status: str
    tresc: str
    przypisany_uzytkownik_id: int | None
    odroczone_do: date | None
    obsluzone_dnia: datetime | None
    notatka: str | None
    wersja: int


class ObslugaZdarzenia(BaseModel):
    notatka: str | None = Field(default=None, max_length=2000)


class OdroczenieZdarzenia(BaseModel):
    odroczone_do: date
    notatka: str | None = Field(default=None, max_length=2000)


class PrzypisanieZdarzenia(BaseModel):
    uzytkownik_id: int | None
