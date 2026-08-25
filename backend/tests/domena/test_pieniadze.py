"""Kwoty, VAT i zaokraglanie.

To jest ten kod, w ktorym blad kosztuje zaufanie do calego systemu. Jedna
rozbieznosc groszowa na fakturze i pracownik wraca do Excela.
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from najem.domena.pieniadze import (
    BladKwoty,
    Kwota,
    zaokraglij,
)
from najem.domena.slowniki import RodzajKwoty

VAT23 = Decimal("23")


def netto(wartosc: str, vat: str = "23") -> Kwota:
    return Kwota(Decimal(wartosc), "PLN", RodzajKwoty.NETTO, Decimal(vat))


def brutto(wartosc: str, vat: str = "23") -> Kwota:
    return Kwota(Decimal(wartosc), "PLN", RodzajKwoty.BRUTTO, Decimal(vat))


class TestZaokraglanie:
    def test_polowka_idzie_w_gore_a_nie_do_parzystej(self) -> None:
        """Python domyslnie zaokragla bankowo: 2,345 dalo by 2,34.

        Umowy i faktury uzywaja ROUND_HALF_UP. Ta roznica to jeden grosz,
        ktory nie zgadza sie z tym, co policzyla ksiegowa.
        """
        assert zaokraglij(Decimal("2.345")) == Decimal("2.35")
        assert zaokraglij(Decimal("2.355")) == Decimal("2.36")
        assert zaokraglij(Decimal("0.005")) == Decimal("0.01")

    def test_wartosci_ujemne_zaokraglaja_sie_od_zera(self) -> None:
        assert zaokraglij(Decimal("-2.345")) == Decimal("-2.35")

    def test_zawsze_dwa_miejsca_po_przecinku(self) -> None:
        assert zaokraglij(Decimal("10")) == Decimal("10.00")
        assert str(zaokraglij(Decimal("10"))) == "10.00"


class TestTworzenieKwoty:
    def test_kwota_jest_kwantyzowana_przy_tworzeniu(self) -> None:
        assert netto("1234.567").wartosc == Decimal("1234.57")

    def test_kwota_netto_bez_stawki_vat_jest_bledem(self) -> None:
        """Kwoty netto bez VAT nie da sie zbrutowac, wiec nie jest kwota."""
        with pytest.raises(BladKwoty, match="VAT"):
            Kwota(Decimal("100"), "PLN", RodzajKwoty.NETTO, None)

    def test_kwota_brutto_bez_stawki_vat_jest_dozwolona(self) -> None:
        """Kaucja bywa kwota brutto, przy ktorej VAT w ogole nie wystepuje."""
        k = Kwota(Decimal("50000"), "PLN", RodzajKwoty.BRUTTO, None)
        assert k.wartosc == Decimal("50000.00")

    def test_waluta_musi_byc_kodem_trzyliterowym(self) -> None:
        with pytest.raises(BladKwoty, match=r"[Ww]aluta"):
            Kwota(Decimal("100"), "ZLOTY", RodzajKwoty.BRUTTO, None)

    def test_waluta_jest_normalizowana_do_wielkich_liter(self) -> None:
        assert Kwota(Decimal("100"), "pln", RodzajKwoty.BRUTTO, None).waluta == "PLN"

    def test_stawka_vat_poza_zakresem_jest_bledem(self) -> None:
        with pytest.raises(BladKwoty, match=r"[Ss]tawka"):
            Kwota(Decimal("100"), "PLN", RodzajKwoty.NETTO, Decimal("-1"))
        with pytest.raises(BladKwoty, match=r"[Ss]tawka"):
            Kwota(Decimal("100"), "PLN", RodzajKwoty.NETTO, Decimal("101"))

    def test_stawka_zero_jest_dozwolona(self) -> None:
        """Najem zwolniony z VAT. Zero to stawka, nie brak stawki."""
        k = netto("1000", vat="0")
        assert k.brutto().wartosc == Decimal("1000.00")

    def test_kwota_jest_niezmienna(self) -> None:
        k = netto("100")
        with pytest.raises(FrozenInstanceError):
            k.wartosc = Decimal("200")  # type: ignore[misc]


class TestPrzeliczanieVat:
    def test_netto_na_brutto(self) -> None:
        assert netto("12500.00").brutto().wartosc == Decimal("15375.00")

    def test_brutto_na_netto(self) -> None:
        assert brutto("15375.00").netto().wartosc == Decimal("12500.00")

    def test_przeliczenie_tam_i_z_powrotem_nie_gubi_groszy_na_okraglych_kwotach(self) -> None:
        assert netto("12500.00").brutto().netto().wartosc == Decimal("12500.00")

    def test_brutto_na_netto_gdy_dzielenie_nie_wychodzi_rowno(self) -> None:
        """100,00 brutto przy 23 procentach to 81,3008..., czyli 81,30 netto."""
        assert brutto("100.00").netto().wartosc == Decimal("81.30")

    def test_netto_na_netto_nic_nie_zmienia(self) -> None:
        k = netto("100.00")
        assert k.netto() is k or k.netto().wartosc == k.wartosc

    def test_kwota_samego_vat(self) -> None:
        assert netto("12500.00").kwota_vat() == Decimal("2875.00")
        assert brutto("15375.00").kwota_vat() == Decimal("2875.00")

    def test_vat_przy_stawce_zero_wynosi_zero(self) -> None:
        assert netto("1000.00", vat="0").kwota_vat() == Decimal("0.00")

    def test_brutto_bez_stawki_nie_da_sie_przeliczyc_na_netto(self) -> None:
        k = Kwota(Decimal("50000"), "PLN", RodzajKwoty.BRUTTO, None)
        with pytest.raises(BladKwoty, match="VAT"):
            k.netto()

    def test_stawka_niecalkowita(self) -> None:
        """Stawki bywaja inne niz 23. Model nie moze zakladac jednej."""
        assert netto("1000.00", vat="8").brutto().wartosc == Decimal("1080.00")
        assert netto("1000.00", vat="5").brutto().wartosc == Decimal("1050.00")


class TestDodawanie:
    def test_dodawanie_kwot_tej_samej_postaci(self) -> None:
        assert (netto("100.00") + netto("50.50")).wartosc == Decimal("150.50")

    def test_dodawanie_roznych_walut_jest_bledem(self) -> None:
        eur = Kwota(Decimal("100"), "EUR", RodzajKwoty.NETTO, VAT23)
        with pytest.raises(BladKwoty, match=r"[Ww]alut"):
            netto("100.00") + eur

    def test_dodawanie_netto_do_brutto_jest_bledem(self) -> None:
        """Suma netto i brutto nie znaczy nic. Lepiej blad niz liczba."""
        with pytest.raises(BladKwoty, match=r"netto|brutto"):
            netto("100.00") + brutto("100.00")

    def test_dodawanie_roznych_stawek_vat_jest_bledem(self) -> None:
        with pytest.raises(BladKwoty, match=r"[Ss]tawk"):
            netto("100.00", vat="23") + netto("100.00", vat="8")

    def test_odejmowanie(self) -> None:
        assert (netto("100.00") - netto("30.00")).wartosc == Decimal("70.00")

    def test_wynik_odejmowania_moze_byc_ujemny(self) -> None:
        """Korekta potrafi zejsc ponizej zera i to nie jest blad."""
        assert (netto("30.00") - netto("100.00")).wartosc == Decimal("-70.00")


class TestWaloryzacja:
    def test_podwyzka_o_wskaznik_procentowy(self) -> None:
        """Regula R2: nowy czynsz = stary razy (1 + wskaznik)."""
        assert netto("12500.00").powieksz_o_procent(Decimal("3.7")).wartosc == Decimal("12962.50")

    def test_waloryzacja_zaokragla_grosze_w_gore_przy_polowce(self) -> None:
        # 1234,56 razy 1,037 = 1280,23872
        assert netto("1234.56").powieksz_o_procent(Decimal("3.7")).wartosc == Decimal("1280.24")

    def test_wskaznik_zero_nie_zmienia_kwoty(self) -> None:
        assert netto("12500.00").powieksz_o_procent(Decimal("0")).wartosc == Decimal("12500.00")

    def test_wskaznik_ujemny_obniza_czynsz(self) -> None:
        """Deflacja jest rzadka, ale wskaznik GUS potrafi byc ujemny."""
        assert netto("1000.00").powieksz_o_procent(Decimal("-2")).wartosc == Decimal("980.00")

    def test_waloryzacja_zachowuje_walute_rodzaj_i_stawke(self) -> None:
        wynik = netto("1000.00", vat="8").powieksz_o_procent(Decimal("5"))
        assert wynik.waluta == "PLN"
        assert wynik.rodzaj is RodzajKwoty.NETTO
        assert wynik.stawka_vat == Decimal("8")

    def test_mnozenie_przez_wielokrotnosc(self) -> None:
        """Regula R5: wartosc weksla to czterokrotnosc czynszu."""
        assert netto("12500.00").pomnoz(Decimal("4")).wartosc == Decimal("50000.00")

    def test_mnozenie_zaokragla_raz_na_koncu(self) -> None:
        # 333,33 razy 3 = 999,99, a nie 1000,00
        assert netto("333.33").pomnoz(Decimal("3")).wartosc == Decimal("999.99")


class TestPorownywanie:
    def test_kwoty_rowne(self) -> None:
        assert netto("100.00") == netto("100.000")

    def test_kwoty_o_roznej_postaci_nie_sa_rowne(self) -> None:
        assert netto("100.00") != brutto("100.00")

    def test_porownanie_wielkosci(self) -> None:
        assert netto("100.00") > netto("99.99")
        assert netto("99.99") < netto("100.00")
        assert netto("100.00") <= netto("100.00")
        assert netto("100.00") >= netto("100.00")

    def test_porownanie_roznych_walut_jest_bledem(self) -> None:
        eur = Kwota(Decimal("100"), "EUR", RodzajKwoty.NETTO, VAT23)
        with pytest.raises(BladKwoty, match=r"[Ww]alut"):
            _ = netto("100.00") > eur


class TestPrezentacja:
    def test_tekstowa_postac_jest_czytelna(self) -> None:
        assert str(netto("1234.56")) == "1234.56 PLN netto (VAT 23%)"
        assert (
            str(Kwota(Decimal("50000"), "PLN", RodzajKwoty.BRUTTO, None)) == "50000.00 PLN brutto"
        )
