"""Regula R1: data zakonczenia umowy.

Najwazniejszy przypadek to ten, w ktorym daty NIE da sie ustalic. Umowa bez
protokolu przekazania nie ma konca i system ma to powiedziec wprost.
"""

from datetime import date

import pytest

from najem.domena.reguly.data_zakonczenia import (
    data_wypowiedzenia,
    data_zakonczenia,
)
from najem.domena.reguly.wynik import Wynik, nieustalony, ustalony
from najem.domena.slowniki import BazaOkresuNajmu

PRZEKAZANIE = BazaOkresuNajmu.DATA_PRZEKAZANIA
ZAWARCIE = BazaOkresuNajmu.DATA_ZAWARCIA


class TestOdDatyPrzekazania:
    def test_typowa_umowa_dwuletnia(self) -> None:
        """24 miesiace od 1 lutego 2026 to koniec 31 stycznia 2028."""
        wynik = data_zakonczenia(
            bazuje_na=PRZEKAZANIE,
            okres_miesiace=24,
            data_przekazania=date(2026, 2, 1),
        )
        assert wynik.wartosc == date(2028, 1, 31)

    def test_brak_protokolu_daje_nieustalona_z_powodem(self) -> None:
        """To jest ten przypadek, dla ktorego regula R1 w ogole istnieje."""
        wynik = data_zakonczenia(
            bazuje_na=PRZEKAZANIE,
            okres_miesiace=24,
            data_zawarcia=date(2026, 1, 15),
            data_przekazania=None,
        )
        assert not wynik.ustalone
        assert wynik.powod_braku is not None
        assert "protokołu przekazania" in wynik.powod_braku

    def test_data_zawarcia_nie_zastepuje_daty_przekazania(self) -> None:
        """Kuszace, ale nieprawdziwe. Umowa moze byc podpisana miesiace wczesniej."""
        wynik = data_zakonczenia(
            bazuje_na=PRZEKAZANIE,
            okres_miesiace=12,
            data_zawarcia=date(2026, 1, 1),
            data_przekazania=None,
        )
        assert wynik.wartosc is None

    def test_konwencja_wylaczajaca_ostatni_dzien(self) -> None:
        """Wariant zgodny z art. 112 Kodeksu cywilnego."""
        wynik = data_zakonczenia(
            bazuje_na=PRZEKAZANIE,
            okres_miesiace=24,
            data_przekazania=date(2026, 2, 1),
            koniec_wlacznie=False,
        )
        assert wynik.wartosc == date(2028, 2, 1)


class TestOdDatyZawarcia:
    def test_umowa_liczona_od_podpisania(self) -> None:
        wynik = data_zakonczenia(
            bazuje_na=ZAWARCIE,
            okres_miesiace=12,
            data_zawarcia=date(2026, 3, 1),
        )
        assert wynik.wartosc == date(2027, 2, 28)

    def test_brak_daty_zawarcia(self) -> None:
        wynik = data_zakonczenia(bazuje_na=ZAWARCIE, okres_miesiace=12, data_zawarcia=None)
        assert not wynik.ustalone
        assert wynik.powod_braku is not None
        assert "zawarcia" in wynik.powod_braku


class TestPrzypadkiGraniczne:
    def test_brak_okresu_zawarcia(self) -> None:
        wynik = data_zakonczenia(
            bazuje_na=PRZEKAZANIE, okres_miesiace=None, data_przekazania=date(2026, 2, 1)
        )
        assert not wynik.ustalone

    def test_okres_niedodatni_jest_odrzucany(self) -> None:
        for okres in (0, -6):
            wynik = data_zakonczenia(
                bazuje_na=PRZEKAZANIE, okres_miesiace=okres, data_przekazania=date(2026, 2, 1)
            )
            assert not wynik.ustalone

    def test_przekazanie_31_stycznia_na_miesiac(self) -> None:
        """31.01 plus miesiac to 28.02, minus dzien to 27.02."""
        wynik = data_zakonczenia(
            bazuje_na=PRZEKAZANIE, okres_miesiace=1, data_przekazania=date(2026, 1, 31)
        )
        assert wynik.wartosc == date(2026, 2, 27)

    def test_rok_przestepny(self) -> None:
        wynik = data_zakonczenia(
            bazuje_na=PRZEKAZANIE, okres_miesiace=12, data_przekazania=date(2027, 3, 1)
        )
        assert wynik.wartosc == date(2028, 2, 29)

    def test_przejscie_przez_koniec_roku(self) -> None:
        wynik = data_zakonczenia(
            bazuje_na=PRZEKAZANIE, okres_miesiace=1, data_przekazania=date(2026, 12, 1)
        )
        assert wynik.wartosc == date(2026, 12, 31)

    def test_wynik_niesie_wyjasnienie(self) -> None:
        wynik = data_zakonczenia(
            bazuje_na=PRZEKAZANIE, okres_miesiace=24, data_przekazania=date(2026, 2, 1)
        )
        assert any("24" in linia for linia in wynik.wyjasnienie)


class TestTerminWypowiedzenia:
    def test_trzy_miesiace_przed_koncem(self) -> None:
        wynik = data_wypowiedzenia(
            data_zakonczenia_umowy=date(2028, 1, 31), okres_wypowiedzenia_miesiace=3
        )
        assert wynik.wartosc == date(2027, 10, 31)

    def test_bez_daty_konca_nie_ma_terminu_wypowiedzenia(self) -> None:
        """Brak protokolu przekazania kaskaduje: nie znamy konca, wiec nie znamy
        momentu, w ktorym trzeba podjac decyzje.
        """
        wynik = data_wypowiedzenia(data_zakonczenia_umowy=None, okres_wypowiedzenia_miesiace=3)
        assert not wynik.ustalone

    def test_bez_okresu_wypowiedzenia(self) -> None:
        wynik = data_wypowiedzenia(
            data_zakonczenia_umowy=date(2028, 1, 31), okres_wypowiedzenia_miesiace=None
        )
        assert not wynik.ustalone

    def test_okres_niedodatni(self) -> None:
        wynik = data_wypowiedzenia(
            data_zakonczenia_umowy=date(2028, 1, 31), okres_wypowiedzenia_miesiace=0
        )
        assert not wynik.ustalone


class TestTypWyniku:
    def test_wynik_nie_moze_miec_wartosci_i_powodu_naraz(self) -> None:
        with pytest.raises(ValueError, match="albo wartość, albo powód"):
            Wynik(wartosc=date(2026, 1, 1), powod_braku="cokolwiek")

    def test_wynik_nie_moze_byc_pusty(self) -> None:
        with pytest.raises(ValueError, match="albo wartość, albo powód"):
            Wynik()

    def test_wymagaj_zwraca_wartosc(self) -> None:
        assert ustalony(date(2026, 1, 1)).wymagaj() == date(2026, 1, 1)

    def test_wymagaj_rzuca_z_powodem(self) -> None:
        wynik: Wynik[date] = nieustalony("Brak protokołu.")
        with pytest.raises(ValueError, match="Brak protokołu"):
            wynik.wymagaj()
