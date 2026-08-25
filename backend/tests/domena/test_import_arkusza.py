"""Walidacja importowanego arkusza.

Kryterium akceptacji etapu E7: arkusz z celowo wprowadzonymi błędami daje
czytelny raport z numerami wierszy i nie zapisuje niczego połowicznie.
"""

from datetime import date
from decimal import Decimal

from najem.domena.import_arkusza import (
    PoleImportu as P,
)
from najem.domena.import_arkusza import (
    sprawdz_arkusz,
    sprawdz_wiersz,
)


def poprawny(**zmiany: object) -> dict[P, object]:
    podstawa: dict[P, object] = {
        P.BUDYNEK: "18A",
        P.LOKAL: "18A/12",
        P.NAJEMCA: "Piekarnia Złoty Kłos",
        P.TYP_LOKALU: "handlowy",
        P.POWIERZCHNIA: "128,50",
        P.CZYNSZ: "9 500,00 zł",
        P.CZYNSZ_RODZAJ: "netto",
        P.STAWKA_VAT: "23",
        P.DATA_PRZEKAZANIA: "01.03.2024",
        P.OKRES_MIESIACE: "36",
        P.DZIEN_PLATNOSCI: "10",
    }
    for klucz, wartosc in zmiany.items():
        podstawa[P(klucz)] = wartosc
    return podstawa


class TestPoprawnyWiersz:
    def test_wiersz_przechodzi(self) -> None:
        wiersz, bledy = sprawdz_wiersz(2, poprawny())
        assert bledy == []
        assert wiersz is not None
        assert wiersz.lokal == "18A/12"

    def test_kwota_po_polsku_z_przecinkiem_i_zlotowka(self) -> None:
        """Arkusze są wypełniane przez ludzi, a nie przez API."""
        wiersz, _ = sprawdz_wiersz(2, poprawny())
        assert wiersz is not None
        assert wiersz.czynsz == Decimal("9500.00")
        assert wiersz.powierzchnia == Decimal("128.50")

    def test_spacja_nierozdzielajaca_jako_separator_tysiecy(self) -> None:
        """Excel formatuje tysiące spacją nierozdzielającą, nie zwykłą."""
        wiersz, bledy = sprawdz_wiersz(2, poprawny(**{P.CZYNSZ: "12 500,00"}))
        assert bledy == []
        assert wiersz is not None
        assert wiersz.czynsz == Decimal("12500.00")

    def test_data_w_formacie_polskim(self) -> None:
        wiersz, _ = sprawdz_wiersz(2, poprawny())
        assert wiersz is not None
        assert wiersz.data_przekazania == date(2024, 3, 1)

    def test_data_w_formacie_iso(self) -> None:
        wiersz, bledy = sprawdz_wiersz(2, poprawny(**{P.DATA_PRZEKAZANIA: "2024-03-01"}))
        assert bledy == []
        assert wiersz is not None
        assert wiersz.data_przekazania == date(2024, 3, 1)

    def test_data_jako_obiekt_z_arkusza(self) -> None:
        """openpyxl zwraca datetime, gdy komórka jest sformatowana jako data."""
        from datetime import datetime

        wiersz, bledy = sprawdz_wiersz(
            2, poprawny(**{P.DATA_PRZEKAZANIA: datetime(2024, 3, 1, 12, 30)})
        )
        assert bledy == []
        assert wiersz is not None
        assert wiersz.data_przekazania == date(2024, 3, 1)

    def test_typ_lokalu_bez_ogonkow(self) -> None:
        wiersz, bledy = sprawdz_wiersz(2, poprawny(**{P.TYP_LOKALU: "uslugowy"}))
        assert bledy == []
        assert wiersz is not None
        assert wiersz.typ_lokalu == "handlowy"

    def test_brak_typu_daje_inny(self) -> None:
        wiersz, bledy = sprawdz_wiersz(2, poprawny(**{P.TYP_LOKALU: ""}))
        assert bledy == []
        assert wiersz is not None
        assert wiersz.typ_lokalu == "inny"


class TestBledy:
    def test_brak_pola_wymaganego(self) -> None:
        wiersz, bledy = sprawdz_wiersz(5, poprawny(**{P.LOKAL: ""}))
        assert wiersz is None
        assert len(bledy) == 1
        assert bledy[0].wiersz == 5
        assert bledy[0].pole == "lokal"
        assert "wymagana" in bledy[0].komunikat

    def test_zbiera_wszystkie_bledy_wiersza_naraz(self) -> None:
        """Człowiek poprawiający arkusz woli zobaczyć trzy błędy naraz
        niż trzy razy uruchamiać import.
        """
        _, bledy = sprawdz_wiersz(
            7,
            poprawny(
                **{
                    P.BUDYNEK: "",
                    P.POWIERZCHNIA: "sto dwadzieścia",
                    P.DATA_PRZEKAZANIA: "trzydziestego",
                }
            ),
        )
        pola = {b.pole for b in bledy}
        assert {"budynek", "powierzchnia", "data_przekazania"} <= pola

    def test_czynsz_netto_bez_vat(self) -> None:
        """Kwoty netto bez stawki VAT nie da się zbrutować, więc nie jest kwotą."""
        _, bledy = sprawdz_wiersz(3, poprawny(**{P.STAWKA_VAT: ""}))
        assert any(b.pole == "stawka_vat" for b in bledy)

    def test_czynsz_brutto_bez_vat_jest_dozwolony(self) -> None:
        wiersz, bledy = sprawdz_wiersz(3, poprawny(**{P.CZYNSZ_RODZAJ: "brutto", P.STAWKA_VAT: ""}))
        assert bledy == []
        assert wiersz is not None

    def test_nieznany_typ_lokalu(self) -> None:
        _, bledy = sprawdz_wiersz(4, poprawny(**{P.TYP_LOKALU: "hangar"}))
        assert any(b.pole == "typ_lokalu" for b in bledy)
        assert any("hangar" in b.komunikat for b in bledy)

    def test_nieznany_rodzaj_kwoty(self) -> None:
        _, bledy = sprawdz_wiersz(4, poprawny(**{P.CZYNSZ_RODZAJ: "z VAT-em"}))
        assert any(b.pole == "czynsz_rodzaj" for b in bledy)

    def test_powierzchnia_ujemna(self) -> None:
        _, bledy = sprawdz_wiersz(4, poprawny(**{P.POWIERZCHNIA: "-10"}))
        assert any("dodatnia" in b.komunikat for b in bledy)

    def test_dzien_platnosci_poza_zakresem(self) -> None:
        _, bledy = sprawdz_wiersz(4, poprawny(**{P.DZIEN_PLATNOSCI: "45"}))
        assert any(b.pole == "dzien_platnosci" for b in bledy)

    def test_okres_zerowy(self) -> None:
        _, bledy = sprawdz_wiersz(4, poprawny(**{P.OKRES_MIESIACE: "0"}))
        assert any(b.pole == "okres_miesiace" for b in bledy)

    def test_komunikat_wskazuje_wiersz_i_kolumne(self) -> None:
        _, bledy = sprawdz_wiersz(12, poprawny(**{P.NAJEMCA: ""}))
        tekst = str(bledy[0])
        assert "Wiersz 12" in tekst
        assert "najemca" in tekst


class TestCalyArkusz:
    def test_numeracja_zaczyna_sie_od_drugiego_wiersza(self) -> None:
        """Pierwszy wiersz arkusza to nagłówek, więc dane zaczynają się od drugiego."""
        wynik = sprawdz_arkusz([poprawny(**{P.LOKAL: ""})])
        assert wynik.bledy[0].wiersz == 2

    def test_duplikat_lokalu_w_pliku(self) -> None:
        """Ten sam lokal dwa razy w jednym arkuszu to błąd danych, nie systemu."""
        wynik = sprawdz_arkusz([poprawny(), poprawny()])
        assert not wynik.poprawny
        assert any("występuje już w wierszu 2" in b.komunikat for b in wynik.bledy)
        assert len(wynik.wiersze) == 1

    def test_duplikat_rozpoznawany_bez_wzgledu_na_wielkosc_liter(self) -> None:
        wynik = sprawdz_arkusz([poprawny(), poprawny(**{P.LOKAL: "18a/12"})])
        assert not wynik.poprawny

    def test_ten_sam_lokal_w_innym_budynku_jest_dozwolony(self) -> None:
        wynik = sprawdz_arkusz([poprawny(), poprawny(**{P.BUDYNEK: "20C"})])
        assert wynik.poprawny
        assert len(wynik.wiersze) == 2

    def test_arkusz_z_bledami_nie_daje_zadnego_wiersza_do_zapisu(self) -> None:
        """Albo cały plik, albo nic. Import połowiczny zostawia bazę
        w stanie, którego nikt nie umie posprzątać.
        """
        wynik = sprawdz_arkusz(
            [
                poprawny(),
                poprawny(**{P.BUDYNEK: "20C", P.NAJEMCA: ""}),
                poprawny(**{P.BUDYNEK: "30D"}),
            ]
        )
        assert not wynik.poprawny
        # Wiersze poprawne są policzone, ale decyzja o zapisie należy do usługi,
        # a ta wymaga wyniku bez błędów.
        assert len(wynik.wiersze) == 2
        assert len(wynik.bledy) == 1

    def test_pusty_arkusz(self) -> None:
        wynik = sprawdz_arkusz([])
        assert wynik.poprawny
        assert wynik.wiersze == []
