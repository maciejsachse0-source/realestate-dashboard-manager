"""Kalendarz swiat i dni roboczych.

Termin platnosci "do 10-go" wypadajacy w niedziele i termin "14 dni od
przekazania" to dwa miejsca, w ktorych system bez kalendarza klamie
kilka razy w roku.
"""

from datetime import date

import pytest

from najem.domena.kalendarz import (
    czy_dzien_roboczy,
    czy_swieto,
    dodaj_dni_robocze,
    dzien_miesiaca,
    nastepny_dzien_roboczy,
    przesun_na_dzien_roboczy,
    swieta_polskie,
    wielkanoc,
)


class TestWielkanoc:
    @pytest.mark.parametrize(
        ("rok", "oczekiwana"),
        [
            (2000, date(2000, 4, 23)),
            (2010, date(2010, 4, 4)),
            (2024, date(2024, 3, 31)),
            (2025, date(2025, 4, 20)),
            (2026, date(2026, 4, 5)),
            (2027, date(2027, 3, 28)),
            (2038, date(2038, 4, 25)),
        ],
    )
    def test_znane_daty(self, rok: int, oczekiwana: date) -> None:
        assert wielkanoc(rok) == oczekiwana

    def test_wielkanoc_zawsze_wypada_w_niedziele(self) -> None:
        for rok in range(2020, 2061):
            assert wielkanoc(rok).weekday() == 6, rok

    def test_wielkanoc_miesci_sie_w_dozwolonym_oknie(self) -> None:
        """Zawsze miedzy 22 marca a 25 kwietnia."""
        for rok in range(1900, 2101):
            data = wielkanoc(rok)
            assert date(rok, 3, 22) <= data <= date(rok, 4, 25), rok


class TestSwieta:
    def test_swieta_stale(self) -> None:
        swieta = swieta_polskie(2026)
        for miesiac, dzien in [
            (1, 1),  # Nowy Rok
            (5, 1),  # Swieto Pracy
            (5, 3),  # Swieto Konstytucji
            (8, 15),  # Wniebowziecie
            (11, 1),  # Wszystkich Swietych
            (11, 11),  # Niepodleglosc
            (12, 25),
            (12, 26),
        ]:
            assert date(2026, miesiac, dzien) in swieta

    def test_swieta_ruchome_2026(self) -> None:
        """Wielkanoc 2026 wypada 5 kwietnia."""
        swieta = swieta_polskie(2026)
        assert date(2026, 4, 5) in swieta  # Wielkanoc
        assert date(2026, 4, 6) in swieta  # Poniedzialek Wielkanocny
        assert date(2026, 5, 24) in swieta  # Zielone Swiatki, Wielkanoc plus 49
        assert date(2026, 6, 4) in swieta  # Boze Cialo, Wielkanoc plus 60

    def test_boze_cialo_zawsze_w_czwartek(self) -> None:
        for rok in range(2020, 2041):
            boze_cialo = wielkanoc(rok).toordinal() + 60
            assert date.fromordinal(boze_cialo).weekday() == 3, rok

    def test_trzech_kroli_dopiero_od_2011(self) -> None:
        """Dzien wolny przywrocono ustawa obowiazujaca od 2011 roku.

        Umowy z archiwum bywaja starsze, wiec termin z 6 stycznia 2010
        byl wtedy zwyklym dniem roboczym.
        """
        assert date(2011, 1, 6) in swieta_polskie(2011)
        assert date(2010, 1, 6) not in swieta_polskie(2010)

    def test_czy_swieto(self) -> None:
        assert czy_swieto(date(2026, 12, 25))
        assert not czy_swieto(date(2026, 12, 27))


class TestDniRobocze:
    def test_zwykly_wtorek_jest_dniem_roboczym(self) -> None:
        assert czy_dzien_roboczy(date(2026, 8, 25))

    def test_sobota_i_niedziela_nie_sa_dniami_roboczymi(self) -> None:
        assert not czy_dzien_roboczy(date(2026, 8, 22))  # sobota
        assert not czy_dzien_roboczy(date(2026, 8, 23))  # niedziela

    def test_swieto_w_dzien_powszedni_nie_jest_dniem_roboczym(self) -> None:
        assert not czy_dzien_roboczy(date(2026, 12, 25))  # piatek, Boze Narodzenie

    def test_przesuniecie_zostawia_dzien_roboczy_bez_zmian(self) -> None:
        """Termin, ktory wypada w dzien roboczy, nie przesuwa sie nigdzie."""
        assert przesun_na_dzien_roboczy(date(2026, 8, 25)) == date(2026, 8, 25)

    def test_termin_w_niedziele_przesuwa_sie_na_poniedzialek(self) -> None:
        assert przesun_na_dzien_roboczy(date(2026, 8, 23)) == date(2026, 8, 24)

    def test_termin_w_sobote_przesuwa_sie_na_poniedzialek(self) -> None:
        assert przesun_na_dzien_roboczy(date(2026, 8, 22)) == date(2026, 8, 24)

    def test_termin_w_swieto_ruchome_przeskakuje_caly_blok(self) -> None:
        """Wielkanoc 2026: niedziela 5 kwietnia i poniedzialek 6 kwietnia.

        Termin z 5 kwietnia ma wyladowac we wtorek 7 kwietnia.
        """
        assert przesun_na_dzien_roboczy(date(2026, 4, 5)) == date(2026, 4, 7)

    def test_przesuniecie_przez_koniec_roku(self) -> None:
        """1 stycznia 2027 to piatek i swieto, wiec termin idzie na poniedzialek."""
        assert przesun_na_dzien_roboczy(date(2027, 1, 1)) == date(2027, 1, 4)

    def test_nastepny_dzien_roboczy_zawsze_idzie_do_przodu(self) -> None:
        """Rozne od przesuniecia: nawet dzien roboczy przechodzi na kolejny."""
        assert nastepny_dzien_roboczy(date(2026, 8, 25)) == date(2026, 8, 26)
        assert nastepny_dzien_roboczy(date(2026, 8, 21)) == date(2026, 8, 24)


class TestDodawanieDniRoboczych:
    def test_dodanie_zera_zostawia_date(self) -> None:
        assert dodaj_dni_robocze(date(2026, 8, 25), 0) == date(2026, 8, 25)

    def test_dodanie_dni_pomija_weekend(self) -> None:
        # Piatek 21.08.2026 plus 1 dzien roboczy to poniedzialek 24.08
        assert dodaj_dni_robocze(date(2026, 8, 21), 1) == date(2026, 8, 24)

    def test_dodanie_dni_pomija_swieta(self) -> None:
        # Czwartek 24.12.2026 plus 1: 25 i 26 to swieta, 27 to niedziela
        assert dodaj_dni_robocze(date(2026, 12, 24), 1) == date(2026, 12, 28)

    def test_liczba_ujemna_cofa(self) -> None:
        assert dodaj_dni_robocze(date(2026, 8, 24), -1) == date(2026, 8, 21)


class TestDzienMiesiaca:
    def test_typowy_dzien(self) -> None:
        """Termin platnosci do 10-go w marcu 2026."""
        assert dzien_miesiaca(2026, 3, 10) == date(2026, 3, 10)

    def test_dzien_31_w_miesiacu_30_dniowym_to_ostatni_dzien(self) -> None:
        """Umowa mowi 'do 31-go', a kwiecien ma 30 dni. Termin to 30 kwietnia."""
        assert dzien_miesiaca(2026, 4, 31) == date(2026, 4, 30)

    def test_luty_w_roku_zwyklym(self) -> None:
        assert dzien_miesiaca(2026, 2, 30) == date(2026, 2, 28)

    def test_luty_w_roku_przestepnym(self) -> None:
        assert dzien_miesiaca(2028, 2, 30) == date(2028, 2, 29)

    def test_dzien_poza_zakresem_jest_bledem(self) -> None:
        with pytest.raises(ValueError, match="Dzień miesiąca"):
            dzien_miesiaca(2026, 3, 0)
        with pytest.raises(ValueError, match="Dzień miesiąca"):
            dzien_miesiaca(2026, 3, 32)
