"""Liczby i kwoty wyjęte z polskiego tekstu umowy.

Nacisk na trzy rzeczy, które kosztują pieniądze, gdy się je pomyli:
grosze, separatory tysięcy i kropkę w roli separatora dziesiętnego.
"""

from decimal import Decimal

import pytest

from najem.domena.ekstrakcja.liczby import (
    KwotaSurowa,
    czytaj_liczbe,
    separator_niejednoznaczny,
    znajdz_dni_platnosci,
    znajdz_krotnosci,
    znajdz_kwoty,
    znajdz_liczby,
    znajdz_procenty,
)


class TestCzytanieLiczby:
    @pytest.mark.parametrize(
        ("zapis", "oczekiwana"),
        [
            ("6960", "6960"),
            ("6960,00", "6960.00"),
            ("6 960,00", "6960.00"),
            ("6 960,00", "6960.00"),  # spacja niełamiąca, wstawia ją Word
            ("6 960,00", "6960.00"),  # wąska niełamiąca, bywa w PDF-ach
            ("1 234 567,89", "1234567.89"),
            ("124,50", "124.50"),
            ("0,01", "0.01"),
            ("10.5", "10.5"),  # jedna cyfra po kropce, więc kropka dziesiętna
            ("1.234,56", "1234.56"),  # przecinek rozstrzyga: kropka tysięczna
            ("1.234.567", "1234567"),  # dwie kropki, obie tysięczne
        ],
    )
    def test_rozpoznaje_polskie_zapisy(self, zapis: str, oczekiwana: str) -> None:
        assert czytaj_liczbe(zapis) == Decimal(oczekiwana)

    def test_grosze_nie_gina(self) -> None:
        """Klasyczna ofiara float: 0,1 + 0,2. Decimal trzyma to dokładnie."""
        dziesiec_groszy = czytaj_liczbe("0,10")
        dwadziescia_groszy = czytaj_liczbe("0,20")
        assert dziesiec_groszy is not None and dwadziescia_groszy is not None
        assert dziesiec_groszy + dwadziescia_groszy == Decimal("0.30")

    def test_zwraca_decimal_nie_float(self) -> None:
        assert isinstance(czytaj_liczbe("124,50"), Decimal)

    @pytest.mark.parametrize("zapis", ["", "   ", "abc", "zł", "--"])
    def test_brak_liczby_to_none_a_nie_zero(self, zapis: str) -> None:
        """Decyzja D5: brak danych jest informacją. Zero byłoby kłamstwem."""
        assert czytaj_liczbe(zapis) is None


class TestNiejednoznacznaKropka:
    """„6.960" to po polsku 6960, po angielsku 6,96. Trzy rzędy wielkości."""

    def test_polski_odczyt_wygrywa(self) -> None:
        assert czytaj_liczbe("6.960") == Decimal("6960")

    def test_ale_zapis_jest_oznaczony_jako_niepewny(self) -> None:
        assert separator_niejednoznaczny("6.960") is True

    @pytest.mark.parametrize(
        "zapis",
        [
            "6.960,00",  # przecinek rozstrzyga
            "10.5",  # jedna cyfra po kropce
            "10.50",  # dwie cyfry po kropce
            "1.234.567",  # dwie kropki
            "6 960",  # spacja, nie kropka
            "6960",  # bez separatora
        ],
    )
    def test_pozostale_zapisy_sa_jednoznaczne(self, zapis: str) -> None:
        assert separator_niejednoznaczny(zapis) is False


class TestKwoty:
    def test_czynsz_ze_zdania_umowy(self) -> None:
        tekst = "Czynsz najmu wynosi 6 960,00 zł netto miesięcznie."
        (trafienie,) = znajdz_kwoty(tekst)
        assert trafienie.wartosc == KwotaSurowa(Decimal("6960.00"), "PLN")
        assert tekst[trafienie.od : trafienie.do] == "6 960,00 zł"

    def test_offsety_wskazuja_na_fragment_do_podswietlenia(self) -> None:
        tekst = "Kaucja w wysokości 20 880,00 zł zostanie wpłacona."
        (trafienie,) = znajdz_kwoty(tekst)
        assert tekst[trafienie.od : trafienie.do] == trafienie.tekst

    @pytest.mark.parametrize(
        ("zapis", "kod"),
        [
            ("1 000,00 zł", "PLN"),
            ("1 000,00 zl", "PLN"),
            ("1 000,00 PLN", "PLN"),
            ("1 000,00 złotych", "PLN"),
            ("1 000,00 EUR", "EUR"),
            ("1 000,00 €", "EUR"),
            ("1 000,00 euro", "EUR"),
        ],
    )
    def test_rozpoznaje_zapisy_waluty(self, zapis: str, kod: str) -> None:
        (trafienie,) = znajdz_kwoty(f"Kwota {zapis} płatna z góry.")
        assert trafienie.wartosc.waluta == kod

    def test_waluta_jest_wynikiem_a_nie_zalozeniem(self) -> None:
        """Punkt B z postep.md: czy istnieją umowy w EUR. Ekstrakcja to pokaże."""
        tekst = "Czynsz wynosi 1 500,00 EUR miesięcznie."
        (trafienie,) = znajdz_kwoty(tekst)
        assert trafienie.wartosc.waluta == "EUR"

    def test_kilka_kwot_w_kolejnosci_wystapienia(self) -> None:
        tekst = "Czynsz 6 960,00 zł, eksploatacja 1 245,00 zł, parking 300,00 zł."
        trafienia = znajdz_kwoty(tekst)
        assert [t.wartosc.wartosc for t in trafienia] == [
            Decimal("6960.00"),
            Decimal("1245.00"),
            Decimal("300.00"),
        ]
        assert [t.od for t in trafienia] == sorted(t.od for t in trafienia)

    def test_liczba_bez_waluty_nie_jest_kwota(self) -> None:
        assert znajdz_kwoty("Powierzchnia wynosi 124,50 m2.") == []

    def test_nie_lapie_waluty_wewnatrz_slowa(self) -> None:
        """„100 zlecenie" nie jest kwotą w złotych."""
        assert znajdz_kwoty("Wykonano 100 zleceń serwisowych.") == []

    def test_zapis_ktorego_nie_da_sie_odczytac_jest_pomijany(self) -> None:
        """„1.234.56" nie jest liczbą ani po polsku, ani po angielsku.
        Zgadywanie, czy autorowi chodziło o 1234,56 czy o 1.234,56,
        byłoby zamianą braku danych w fakt (decyzja D5)."""
        assert czytaj_liczbe("1.234.56") is None
        assert znajdz_kwoty("kwota 1.234.56 zł do zapłaty") == []


class TestProcenty:
    @pytest.mark.parametrize(
        ("tekst", "oczekiwany"),
        [
            ("wskaźnik 3,7%", "3.7"),
            ("wskaźnik 3,7 %", "3.7"),
            ("stawka 23%", "23"),
            ("o 10 procent", "10"),
        ],
    )
    def test_rozpoznaje_procenty(self, tekst: str, oczekiwany: str) -> None:
        (trafienie,) = znajdz_procenty(tekst)
        assert trafienie.wartosc == Decimal(oczekiwany)

    def test_wskaznik_ujemny_zapisany_slownie_nie_jest_zgadywany(self) -> None:
        """Deflacja bywa zapisana jako „spadek o 0,5%". Znak wynika ze zdania,
        więc liczba zostaje dodatnia, a interpretację robi wzorzec."""
        (trafienie,) = znajdz_procenty("spadek o 0,5%")
        assert trafienie.wartosc == Decimal("0.5")


class TestKrotnosci:
    def test_czterokrotnosc_czynszu(self) -> None:
        """Reguła R5: wartość weksla jako wielokrotność czynszu."""
        tekst = "Weksel na czterokrotność miesięcznego czynszu."
        (trafienie,) = znajdz_krotnosci(tekst)
        assert trafienie.wartosc == 4
        assert tekst[trafienie.od : trafienie.do] == "czterokrotność"

    @pytest.mark.parametrize(
        ("slowo", "mnoznik"),
        [("dwukrotność", 2), ("trzykrotność", 3), ("sześciokrotność", 6)],
    )
    def test_pozostale_liczebniki(self, slowo: str, mnoznik: int) -> None:
        (trafienie,) = znajdz_krotnosci(f"Kaucja w wysokości {slowo} czynszu.")
        assert trafienie.wartosc == mnoznik

    def test_wielka_litera_na_poczatku_zdania(self) -> None:
        (trafienie,) = znajdz_krotnosci("Czterokrotność czynszu stanowi zabezpieczenie.")
        assert trafienie.wartosc == 4

    def test_brak_liczebnika_to_pusta_lista(self) -> None:
        assert znajdz_krotnosci("Weksel in blanco bez wskazania wartości.") == []


class TestDniPlatnosci:
    @pytest.mark.parametrize(
        ("tekst", "dzien"),
        [
            ("płatny do 10-go dnia miesiąca", 10),
            ("płatny do 10 dnia miesiąca", 10),
            ("płatny do 10. dnia miesiąca", 10),
            ("płatny do 28-tego dnia miesiąca", 28),
            ("do dziesiątego dnia każdego miesiąca", 10),
            ("do ostatniego dnia miesiąca", 31),
        ],
    )
    def test_rozpoznaje_dzien(self, tekst: str, dzien: int) -> None:
        trafienia = znajdz_dni_platnosci(tekst)
        assert [t.wartosc for t in trafienia] == [dzien]

    def test_dwudziestego_piatego_nie_jest_dwudziestego(self) -> None:
        """Dłuższy zapis musi wygrać, inaczej 25 zamieni się w 20."""
        trafienia = znajdz_dni_platnosci("do dwudziestego piątego dnia miesiąca")
        assert [t.wartosc for t in trafienia] == [25]

    def test_rozne_terminy_dla_roznych_skladnikow(self) -> None:
        """Reguła R3: czynsz do 10-go, eksploatacja do 14-go. Prawie nigdy
        nie są takie same, więc oba muszą zostać znalezione."""
        tekst = "Czynsz do 10-go dnia, opłata eksploatacyjna do 14-go dnia."
        assert [t.wartosc for t in znajdz_dni_platnosci(tekst)] == [10, 14]

    def test_liczba_dni_to_nie_dzien_miesiaca(self) -> None:
        """„w terminie 45 dni" to okres, nie dzień miesiąca."""
        assert znajdz_dni_platnosci("w terminie 45 dni od przekazania") == []


class TestZnajdzLiczby:
    def test_powierzchnia_z_groszami_metra(self) -> None:
        tekst = "Lokal o powierzchni 124,50 m2."
        trafienia = znajdz_liczby(tekst)
        assert [t.wartosc for t in trafienia] == [Decimal("124.50"), Decimal("2")]

    def test_pusty_tekst(self) -> None:
        assert znajdz_liczby("") == []
