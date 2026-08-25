"""Kwoty, VAT i zaokraglanie. Jedyne miejsce w projekcie liczace na pieniadzach.

Trzy zasady, ktore tu obowiazuja bez wyjatku:

1. Nigdy float. Decimal albo nic.
2. Zaokraglanie tylko przez `zaokraglij`, zawsze ROUND_HALF_UP.
   Python domyslnie zaokragla bankowo, wiec 2,345 dalby 2,34 zamiast 2,35.
3. Kwota zawsze wie, czy jest netto czy brutto, w jakiej walucie i przy jakiej
   stawce VAT. Kwota bez tych informacji nie jest kwota, tylko liczba.
"""

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Self

from najem.domena.slowniki import RodzajKwoty

#: Dokladnosc pieniedzy: dwa miejsca po przecinku.
GROSZ = Decimal("0.01")

#: Dokladnosc obliczen posrednich. Zaokraglamy raz, na koncu.
DOKLADNOSC_POSREDNIA = Decimal("0.000001")

STO = Decimal("100")


class BladKwoty(Exception):
    """Operacja na kwotach, ktora nie ma sensu ekonomicznego."""


def zaokraglij(wartosc: Decimal) -> Decimal:
    """Zaokraglenie do grosza w gore przy polowce, tak jak liczy ksiegowosc.

    ROUND_HALF_UP, nie domyslne dla Pythona ROUND_HALF_EVEN. Dla wartosci
    ujemnych oznacza to zaokraglenie od zera: -2,345 daje -2,35.
    """
    return wartosc.quantize(GROSZ, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, order=False)
class Kwota:
    """Kwota pieniezna wraz z cala informacja potrzebna, zeby ja zinterpretowac.

    Niezmienna z premedytacja: kazda operacja zwraca nowa kwote, wiec nie da sie
    przypadkiem zmienic wartosci, ktora ktos juz gdzies wyswietlil.
    """

    wartosc: Decimal
    waluta: str
    rodzaj: RodzajKwoty
    #: Stawka w procentach, np. Decimal("23"). Wymagana dla kwot netto.
    #: Dla kwot brutto opcjonalna, bo kaucja czy weksel VAT-u nie maja.
    stawka_vat: Decimal | None = None

    def __post_init__(self) -> None:
        waluta = self.waluta.strip().upper()
        if len(waluta) != 3 or not waluta.isalpha():
            raise BladKwoty(
                f"Waluta musi być trzyliterowym kodem ISO 4217, otrzymano {self.waluta!r}."
            )
        object.__setattr__(self, "waluta", waluta)
        object.__setattr__(self, "wartosc", zaokraglij(self.wartosc))

        if self.stawka_vat is not None and not (Decimal(0) <= self.stawka_vat <= STO):
            raise BladKwoty(
                f"Stawka VAT musi mieścić się między 0 a 100 procent, otrzymano {self.stawka_vat}."
            )
        if self.rodzaj is RodzajKwoty.NETTO and self.stawka_vat is None:
            raise BladKwoty(
                "Kwota netto wymaga stawki VAT. Bez niej nie da się jej przeliczyć na brutto."
            )

    # ------------------------------------------------------------ przeliczenia

    def _mnoznik_vat(self) -> Decimal:
        if self.stawka_vat is None:
            raise BladKwoty(
                "Brak stawki VAT, więc tej kwoty nie da się przeliczyć między netto a brutto."
            )
        return Decimal(1) + self.stawka_vat / STO

    def brutto(self) -> Self:
        """Ta sama kwota wyrazona jako brutto."""
        if self.rodzaj is RodzajKwoty.BRUTTO:
            return self
        return replace(self, wartosc=self.wartosc * self._mnoznik_vat(), rodzaj=RodzajKwoty.BRUTTO)

    def netto(self) -> Self:
        """Ta sama kwota wyrazona jako netto."""
        if self.rodzaj is RodzajKwoty.NETTO:
            return self
        return replace(self, wartosc=self.wartosc / self._mnoznik_vat(), rodzaj=RodzajKwoty.NETTO)

    def kwota_vat(self) -> Decimal:
        """Sam podatek. Liczony jako roznica brutto i netto, zeby obie strony
        rownania zgadzaly sie po zaokragleniu.
        """
        return zaokraglij(self.brutto().wartosc - self.netto().wartosc)

    # -------------------------------------------------------------- arytmetyka

    def _sprawdz_zgodnosc(self, inna: "Kwota") -> None:
        if self.waluta != inna.waluta:
            raise BladKwoty(
                f"Nie można łączyć kwot w różnych walutach: {self.waluta} i {inna.waluta}."
            )
        if self.rodzaj is not inna.rodzaj:
            raise BladKwoty(
                f"Nie można łączyć kwoty {self.rodzaj} z kwotą {inna.rodzaj}. "
                "Sprowadź obie do tej samej postaci."
            )
        if self.stawka_vat != inna.stawka_vat:
            raise BladKwoty(
                f"Różne stawki VAT: {self.stawka_vat} i {inna.stawka_vat}. "
                "Suma takich kwot nie ma jednej stawki, więc nie jest kwotą."
            )

    def __add__(self, inna: "Kwota") -> Self:
        self._sprawdz_zgodnosc(inna)
        return replace(self, wartosc=self.wartosc + inna.wartosc)

    def __sub__(self, inna: "Kwota") -> Self:
        self._sprawdz_zgodnosc(inna)
        return replace(self, wartosc=self.wartosc - inna.wartosc)

    def pomnoz(self, mnoznik: Decimal) -> Self:
        """Kwota razy liczba. Regula R5: wartosc weksla to wielokrotnosc czynszu."""
        return replace(self, wartosc=self.wartosc * mnoznik)

    def powieksz_o_procent(self, procent: Decimal) -> Self:
        """Waloryzacja z reguly R2: nowa kwota to stara razy (1 plus wskaznik).

        Wskaznik podajemy w procentach, np. Decimal("3.7") dla 3,7 procent.
        Ujemny wskaznik obniza kwote, bo wskaznik GUS potrafi byc ujemny.
        """
        return self.pomnoz(Decimal(1) + procent / STO)

    # ------------------------------------------------------------ porownywanie

    def __lt__(self, inna: "Kwota") -> bool:
        self._sprawdz_zgodnosc(inna)
        return self.wartosc < inna.wartosc

    def __le__(self, inna: "Kwota") -> bool:
        self._sprawdz_zgodnosc(inna)
        return self.wartosc <= inna.wartosc

    def __gt__(self, inna: "Kwota") -> bool:
        self._sprawdz_zgodnosc(inna)
        return self.wartosc > inna.wartosc

    def __ge__(self, inna: "Kwota") -> bool:
        self._sprawdz_zgodnosc(inna)
        return self.wartosc >= inna.wartosc

    # ------------------------------------------------------------- prezentacja

    def __str__(self) -> str:
        """Postac techniczna, do logow i komunikatow bledow.

        Formatowanie dla uzytkownika robi frontend przez funkcje format.ts.
        """
        opis = f"{self.wartosc} {self.waluta} {self.rodzaj.value}"
        if self.stawka_vat is not None:
            opis += f" (VAT {self.stawka_vat.normalize()}%)"
        return opis
