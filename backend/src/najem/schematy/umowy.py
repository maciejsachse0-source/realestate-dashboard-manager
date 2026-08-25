"""Schematy okresow najmu, parametrow i pozostalych elementow umowy."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from najem.domena.slowniki import (
    BazaOkresuNajmu,
    KtoObciazany,
    OkresRozliczeniowy,
    RodzajKwoty,
    RodzajWskaznika,
    RodzajZabezpieczenia,
    StatusOkresuNajmu,
    StatusPrzegladu,
    StatusWeryfikacji,
    StatusZabezpieczenia,
    TypWartosci,
)


class Odczyt(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------- okres najmu


class OkresNajmuWejscie(BaseModel):
    lokal_id: int
    najemca_id: int
    data_zawarcia: date | None = None
    data_przekazania: date | None = None
    bazuje_na_dacie: BazaOkresuNajmu = BazaOkresuNajmu.DATA_PRZEKAZANIA
    okres_zawarcia_miesiace: int | None = Field(default=None, gt=0, le=1200)
    okres_wypowiedzenia_miesiace: int | None = Field(default=None, gt=0, le=120)
    data_zakonczenia_faktyczna: date | None = None

    waloryzacja_podlega: bool = False
    waloryzacja_miesiac: int | None = Field(default=None, ge=1, le=12)
    waloryzacja_rodzaj_wskaznika: RodzajWskaznika | None = None
    waloryzacja_stala_stawka: Decimal | None = Field(default=None, ge=0, le=100)
    waloryzacja_pierwsza_data: date | None = None
    uwagi: str | None = None

    @model_validator(mode="after")
    def waloryzacja_jest_kompletna(self) -> "OkresNajmuWejscie":
        """Umowa objeta waloryzacja musi mowic, kiedy i czym sie waloryzuje.

        Bez tego regula R2 pominie ja przy przebiegu rocznym, a nikt nie zauwazy,
        bo umowa bedzie wygladac na objeta waloryzacja.
        """
        if self.waloryzacja_podlega and self.waloryzacja_miesiac is None:
            raise ValueError(
                "Umowa podlegająca waloryzacji musi mieć określony miesiąc waloryzacji."
            )
        return self


class OkresNajmuZmiana(OkresNajmuWejscie):
    wersja: int = Field(ge=1)
    status: StatusOkresuNajmu | None = Field(
        default=None, description="Nowy status. Przejście jest sprawdzane regułami."
    )


class OkresNajmuWyjscie(Odczyt):
    id: int
    lokal_id: int
    najemca_id: int
    data_zawarcia: date | None
    data_przekazania: date | None
    bazuje_na_dacie: BazaOkresuNajmu
    okres_zawarcia_miesiace: int | None
    okres_wypowiedzenia_miesiace: int | None
    data_zakonczenia_planowana: date | None
    data_zakonczenia_faktyczna: date | None
    status: StatusOkresuNajmu
    waloryzacja_podlega: bool
    waloryzacja_miesiac: int | None
    waloryzacja_rodzaj_wskaznika: RodzajWskaznika | None
    waloryzacja_stala_stawka: Decimal | None
    waloryzacja_pierwsza_data: date | None
    uwagi: str | None
    wersja: int


# ---------------------------------------------------------------- parametr


class ParametrWejscie(BaseModel):
    """Nowa wartosc parametru. Domyslnie zaproponowana, nie zatwierdzona (D4)."""

    klucz: str = Field(min_length=1, max_length=80)
    typ_wartosci: TypWartosci
    obowiazuje_od: date
    obowiazuje_do: date | None = None

    wartosc_kwota: Decimal | None = None
    wartosc_waluta: str | None = Field(default=None, min_length=3, max_length=3)
    wartosc_rodzaj_kwoty: RodzajKwoty | None = None
    wartosc_stawka_vat: Decimal | None = Field(default=None, ge=0, le=100)
    wartosc_liczba: Decimal | None = None
    wartosc_data: date | None = None
    wartosc_flaga: bool | None = None
    wartosc_tekst: str | None = None

    dokument_zrodlowy_id: int | None = None
    zrodlo_strona: int | None = Field(default=None, ge=1)
    zrodlo_paragraf: str | None = Field(default=None, max_length=80)
    uwagi: str | None = None

    @model_validator(mode="after")
    def wartosc_zgodna_z_typem(self) -> "ParametrWejscie":
        wypelnione = {
            TypWartosci.KWOTA: self.wartosc_kwota is not None,
            TypWartosci.LICZBA: self.wartosc_liczba is not None,
            TypWartosci.DATA: self.wartosc_data is not None,
            TypWartosci.FLAGA: self.wartosc_flaga is not None,
            TypWartosci.TEKST: self.wartosc_tekst is not None,
        }
        if not wypelnione[self.typ_wartosci]:
            raise ValueError(
                f"Parametr typu {self.typ_wartosci.value} wymaga wypełnienia "
                f"pola wartosc_{self.typ_wartosci.value}."
            )
        nadmiarowe = [
            t.value for t, jest in wypelnione.items() if jest and t is not self.typ_wartosci
        ]
        if nadmiarowe:
            raise ValueError(
                f"Parametr typu {self.typ_wartosci.value} nie może mieć wypełnionych "
                f"także pól: {', '.join(sorted(nadmiarowe))}."
            )
        if self.typ_wartosci is TypWartosci.KWOTA:
            if self.wartosc_waluta is None or self.wartosc_rodzaj_kwoty is None:
                raise ValueError("Kwota musi mieć podaną walutę oraz informację netto/brutto.")
            if self.wartosc_rodzaj_kwoty is RodzajKwoty.NETTO and self.wartosc_stawka_vat is None:
                raise ValueError("Kwota netto wymaga stawki VAT.")
        if self.obowiazuje_do is not None and self.obowiazuje_do < self.obowiazuje_od:
            raise ValueError("Okres obowiązywania nie może kończyć się przed swoim początkiem.")
        return self


class ParametrWyjscie(Odczyt):
    id: int
    okres_najmu_id: int
    klucz: str
    typ_wartosci: TypWartosci
    wartosc_kwota: Decimal | None
    wartosc_waluta: str | None
    wartosc_rodzaj_kwoty: RodzajKwoty | None
    wartosc_stawka_vat: Decimal | None
    wartosc_liczba: Decimal | None
    wartosc_data: date | None
    wartosc_flaga: bool | None
    wartosc_tekst: str | None
    obowiazuje_od: date
    obowiazuje_do: date | None
    dokument_zrodlowy_id: int | None
    zrodlo_strona: int | None
    zrodlo_paragraf: str | None
    status_weryfikacji: StatusWeryfikacji
    zatwierdzil_uzytkownik_id: int | None
    zatwierdzono_dnia: datetime | None
    uwagi: str | None
    wersja: int


class DecyzjaWeryfikacji(BaseModel):
    """Zatwierdzenie, poprawienie albo odrzucenie propozycji (decyzja D4)."""

    status: StatusWeryfikacji
    uwagi: str | None = Field(default=None, max_length=2000)


# ------------------------------------------------------------ skladnik oplaty


class SkladnikWejscie(BaseModel):
    nazwa: str = Field(min_length=1, max_length=120)
    klucz_parametru: str = Field(min_length=1, max_length=80)
    sposob_wyliczenia: str | None = None
    dzien_platnosci_miesiaca: int | None = Field(default=None, ge=1, le=31)
    okres_rozliczeniowy: OkresRozliczeniowy = OkresRozliczeniowy.MIESIECZNY
    czy_waloryzowany: bool = False
    uwagi: str | None = None


class SkladnikWyjscie(Odczyt):
    id: int
    okres_najmu_id: int
    nazwa: str
    klucz_parametru: str
    sposob_wyliczenia: str | None
    dzien_platnosci_miesiaca: int | None
    dzien_platnosci_roboczy: date | None = Field(
        default=None,
        description="Najbliższy termin przesunięty na dzień roboczy (reguła R3)",
    )
    okres_rozliczeniowy: OkresRozliczeniowy
    czy_waloryzowany: bool
    uwagi: str | None
    wersja: int


# ------------------------------------------------------------- zabezpieczenie


class ZabezpieczenieWejscie(BaseModel):
    rodzaj: RodzajZabezpieczenia
    status: StatusZabezpieczenia = StatusZabezpieczenia.WYMAGANE
    wymagana_wartosc: Decimal | None = Field(default=None, ge=0)
    wymagana_waluta: str | None = Field(default=None, min_length=3, max_length=3)
    wymagana_rodzaj_kwoty: RodzajKwoty | None = None
    wymagana_stawka_vat: Decimal | None = Field(default=None, ge=0, le=100)
    sposob_wyliczenia: str | None = None
    data_wymagalnosci: date | None = None
    data_dostarczenia: date | None = None
    data_waznosci: date | None = None
    data_zwrotu: date | None = None
    miejsce_przechowywania: str | None = Field(default=None, max_length=200)
    dokument_id: int | None = None
    uwagi: str | None = None

    @model_validator(mode="after")
    def kwota_jest_pelna(self) -> "ZabezpieczenieWejscie":
        if self.wymagana_wartosc is None:
            return self
        if self.wymagana_waluta is None or self.wymagana_rodzaj_kwoty is None:
            raise ValueError("Wymagana wartość musi mieć walutę oraz informację netto/brutto.")
        if self.wymagana_rodzaj_kwoty is RodzajKwoty.NETTO and self.wymagana_stawka_vat is None:
            raise ValueError("Wartość netto wymaga stawki VAT.")
        return self


class ZabezpieczenieWyjscie(Odczyt):
    id: int
    okres_najmu_id: int
    rodzaj: RodzajZabezpieczenia
    status: StatusZabezpieczenia
    wymagana_wartosc: Decimal | None
    wymagana_waluta: str | None
    wymagana_rodzaj_kwoty: RodzajKwoty | None
    wymagana_stawka_vat: Decimal | None
    sposob_wyliczenia: str | None
    data_wymagalnosci: date | None
    data_dostarczenia: date | None
    data_waznosci: date | None
    data_zwrotu: date | None
    miejsce_przechowywania: str | None
    dokument_id: int | None
    uwagi: str | None
    wersja: int


# ------------------------------------------------------------------ przeglad


class PrzegladWejscie(BaseModel):
    lokal_id: int
    okres_najmu_id: int | None = None
    element: str = Field(min_length=1, max_length=120)
    kto_obciazany: KtoObciazany
    czestotliwosc_miesiace: int | None = Field(default=None, gt=0, le=600)
    ostatni_przeglad_data: date | None = None
    protokol_dokument_id: int | None = None
    uwagi: str | None = None


class PrzegladWyjscie(Odczyt):
    id: int
    lokal_id: int
    okres_najmu_id: int | None
    element: str
    kto_obciazany: KtoObciazany
    czestotliwosc_miesiace: int | None
    ostatni_przeglad_data: date | None
    nastepny_przeglad_data: date | None
    status: StatusPrzegladu
    protokol_dokument_id: int | None
    uwagi: str | None
    wersja: int
