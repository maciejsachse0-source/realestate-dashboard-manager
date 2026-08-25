"""Reguly R4, R6: kaucja i polisa. Oraz R7: przeglady. Oraz R9: kompletnosc."""

from datetime import date
from decimal import Decimal

import pytest

from najem.domena.pieniadze import Kwota
from najem.domena.reguly.kompletnosc import POLA_KRYTYCZNE, ocen_kompletnosc
from najem.domena.reguly.przeglady import (
    nastepny_przeglad,
    przeglad_po_protokole,
    status_przegladu,
)
from najem.domena.reguly.zabezpieczenia import (
    czy_polisa_ponizej_wymaganej,
    czy_polisa_wkrotce_wygasa,
    czy_polisa_wygasla,
    czy_zalega,
    termin_relatywny,
    termin_zwrotu_kaucji,
)
from najem.domena.slowniki import RodzajKwoty, StatusPrzegladu, StatusZabezpieczenia

DZIS = date(2026, 8, 25)


def pln(wartosc: str) -> Kwota:
    return Kwota(Decimal(wartosc), "PLN", RodzajKwoty.BRUTTO, None)


class TestTerminRelatywny:
    def test_czternascie_dni_od_przekazania(self) -> None:
        """Typowy zapis z reguly R6."""
        wynik = termin_relatywny(punkt_odniesienia=date(2026, 2, 2), dni=14)
        assert wynik.wartosc == date(2026, 2, 16)

    def test_termin_wypadajacy_w_weekend_przesuwa_sie(self) -> None:
        # 2026-02-01 plus 14 dni to niedziela 15 lutego
        wynik = termin_relatywny(punkt_odniesienia=date(2026, 2, 1), dni=14)
        assert wynik.wartosc == date(2026, 2, 16)
        assert any("dzień wolny" in linia for linia in wynik.wyjasnienie)

    def test_dni_licza_sie_kalendarzowo_a_nie_roboczo(self) -> None:
        """Umowy mowia "14 dni", a nie "14 dni roboczych". Dopiero wynik
        przesuwamy na dzien roboczy. Odwrotna kolejnosc dawalaby inne daty.
        """
        wynik = termin_relatywny(punkt_odniesienia=date(2026, 8, 25), dni=7)
        assert wynik.wartosc == date(2026, 9, 1)

    def test_zero_dni_to_ten_sam_dzien(self) -> None:
        wynik = termin_relatywny(punkt_odniesienia=date(2026, 8, 25), dni=0)
        assert wynik.wartosc == date(2026, 8, 25)

    def test_bez_punktu_odniesienia_nie_ma_terminu(self) -> None:
        """Brak protokolu przekazania kaskaduje na termin polisy."""
        wynik = termin_relatywny(punkt_odniesienia=None, dni=14)
        assert not wynik.ustalone

    def test_bez_liczby_dni_nie_ma_terminu(self) -> None:
        assert not termin_relatywny(punkt_odniesienia=date(2026, 2, 1), dni=None).ustalone

    def test_ujemna_liczba_dni(self) -> None:
        assert not termin_relatywny(punkt_odniesienia=date(2026, 2, 1), dni=-5).ustalone

    def test_bez_przesuwania_na_dzien_roboczy(self) -> None:
        wynik = termin_relatywny(
            punkt_odniesienia=date(2026, 2, 1), dni=14, przesun_na_roboczy=False
        )
        assert wynik.wartosc == date(2026, 2, 15)


class TestZaleganie:
    def test_niedostarczone_po_terminie_to_zaleglosc(self) -> None:
        assert czy_zalega(status=StatusZabezpieczenia.WYMAGANE, termin=date(2026, 8, 1), dzis=DZIS)

    def test_niedostarczone_przed_terminem_to_jeszcze_nie_zaleglosc(self) -> None:
        assert not czy_zalega(
            status=StatusZabezpieczenia.WYMAGANE, termin=date(2026, 9, 1), dzis=DZIS
        )

    def test_w_dniu_terminu_jeszcze_nie_zalega(self) -> None:
        assert not czy_zalega(status=StatusZabezpieczenia.WYMAGANE, termin=DZIS, dzis=DZIS)

    def test_dostarczone_nie_zalega_nawet_po_terminie(self) -> None:
        assert not czy_zalega(
            status=StatusZabezpieczenia.DOSTARCZONE, termin=date(2026, 8, 1), dzis=DZIS
        )

    def test_zwrocone_i_zatrzymane_nie_zalegaja(self) -> None:
        for status in (StatusZabezpieczenia.ZWROCONE, StatusZabezpieczenia.ZATRZYMANE):
            assert not czy_zalega(status=status, termin=date(2026, 8, 1), dzis=DZIS)

    def test_brak_terminu_nie_generuje_alarmu(self) -> None:
        """Alarm bez pokrycia w danych uczy ludzi ignorowania alarmow."""
        assert not czy_zalega(status=StatusZabezpieczenia.WYMAGANE, termin=None, dzis=DZIS)


class TestZwrotKaucji:
    def test_termin_zwrotu_po_zakonczeniu_najmu(self) -> None:
        wynik = termin_zwrotu_kaucji(data_zakonczenia_najmu=date(2028, 1, 31), dni_na_zwrot=30)
        assert wynik.wartosc == date(2028, 3, 1)

    def test_bez_daty_zakonczenia_nie_ma_terminu_zwrotu(self) -> None:
        assert not termin_zwrotu_kaucji(data_zakonczenia_najmu=None, dni_na_zwrot=30).ustalone


class TestPolisa:
    def test_polisa_wygasla(self) -> None:
        assert czy_polisa_wygasla(data_waznosci=date(2026, 8, 24), dzis=DZIS)

    def test_polisa_wazna_dzis_jeszcze_nie_wygasla(self) -> None:
        assert not czy_polisa_wygasla(data_waznosci=DZIS, dzis=DZIS)

    def test_brak_daty_waznosci_nie_generuje_alarmu(self) -> None:
        assert not czy_polisa_wygasla(data_waznosci=None, dzis=DZIS)

    def test_polisa_wygasajaca_w_ciagu_30_dni(self) -> None:
        assert czy_polisa_wkrotce_wygasa(data_waznosci=date(2026, 9, 10), dzis=DZIS)

    def test_polisa_wygasajaca_dokladnie_za_30_dni(self) -> None:
        assert czy_polisa_wkrotce_wygasa(data_waznosci=date(2026, 9, 24), dzis=DZIS)

    def test_polisa_wygasajaca_za_31_dni_jeszcze_nie_ostrzega(self) -> None:
        assert not czy_polisa_wkrotce_wygasa(data_waznosci=date(2026, 9, 25), dzis=DZIS)

    def test_polisa_juz_wygasla_to_inne_zdarzenie(self) -> None:
        """Wygasla polisa nie jest "wkrotce wygasajaca". To osobne zdarzenie
        o innej wadze, wiec nie mieszamy ich w jednym warunku.
        """
        assert not czy_polisa_wkrotce_wygasa(data_waznosci=date(2026, 8, 1), dzis=DZIS)
        assert czy_polisa_wygasla(data_waznosci=date(2026, 8, 1), dzis=DZIS)


class TestSumaUbezpieczenia:
    def test_polisa_ponizej_wymaganej(self) -> None:
        wynik = czy_polisa_ponizej_wymaganej(
            suma_ubezpieczenia=pln("500000.00"), wymagana_kwota=pln("1000000.00")
        )
        assert wynik.wymagaj() is True

    def test_polisa_na_wymagana_kwote(self) -> None:
        wynik = czy_polisa_ponizej_wymaganej(
            suma_ubezpieczenia=pln("1000000.00"), wymagana_kwota=pln("1000000.00")
        )
        assert wynik.wymagaj() is False

    def test_rozne_waluty_wymagaja_decyzji_czlowieka(self) -> None:
        """Polisa w EUR przy wymaganiu w PLN nie jest porownywalna po liczbie."""
        euro = Kwota(Decimal("250000"), "EUR", RodzajKwoty.BRUTTO, None)
        wynik = czy_polisa_ponizej_wymaganej(
            suma_ubezpieczenia=euro, wymagana_kwota=pln("1000000.00")
        )
        assert not wynik.ustalone
        assert wynik.powod_braku is not None
        assert "EUR" in wynik.powod_braku

    def test_brak_sumy_z_polisy(self) -> None:
        assert not czy_polisa_ponizej_wymaganej(
            suma_ubezpieczenia=None, wymagana_kwota=pln("1000.00")
        ).ustalone

    def test_brak_wymagania_w_umowie(self) -> None:
        assert not czy_polisa_ponizej_wymaganej(
            suma_ubezpieczenia=pln("1000.00"), wymagana_kwota=None
        ).ustalone


class TestPrzeglady:
    def test_kolejny_przeglad_po_roku(self) -> None:
        wynik = nastepny_przeglad(ostatni_przeglad=date(2026, 3, 15), czestotliwosc_miesiace=12)
        assert wynik.wartosc == date(2027, 3, 15)

    def test_przeglad_polroczny(self) -> None:
        wynik = nastepny_przeglad(ostatni_przeglad=date(2026, 8, 31), czestotliwosc_miesiace=6)
        assert wynik.wartosc == date(2027, 2, 28)

    def test_brak_ostatniego_przegladu_nie_znaczy_ze_jest_aktualny(self) -> None:
        """To jest rzecz, ktora latwo zepsuc. Przeglad bez daty wyglada
        na zalatwiony tylko dlatego, ze nikt go nie wpisal.
        """
        wynik = nastepny_przeglad(ostatni_przeglad=None, czestotliwosc_miesiace=12)
        assert not wynik.ustalone
        assert status_przegladu(nastepny_termin=None, dzis=DZIS) is StatusPrzegladu.NIEUSTALONY

    def test_brak_czestotliwosci(self) -> None:
        assert not nastepny_przeglad(
            ostatni_przeglad=date(2026, 3, 15), czestotliwosc_miesiace=None
        ).ustalone

    def test_czestotliwosc_niedodatnia(self) -> None:
        assert not nastepny_przeglad(
            ostatni_przeglad=date(2026, 3, 15), czestotliwosc_miesiace=0
        ).ustalone

    def test_protokol_przesuwa_termin_do_przodu(self) -> None:
        wynik = przeglad_po_protokole(data_protokolu=DZIS, czestotliwosc_miesiace=12)
        assert wynik.wartosc == date(2027, 8, 25)


class TestStatusPrzegladu:
    def test_przeglad_odlegly_jest_aktualny(self) -> None:
        assert (
            status_przegladu(nastepny_termin=date(2027, 3, 1), dzis=DZIS)
            is StatusPrzegladu.AKTUALNY
        )

    def test_przeglad_w_ciagu_30_dni_sie_zbliza(self) -> None:
        assert (
            status_przegladu(nastepny_termin=date(2026, 9, 10), dzis=DZIS)
            is StatusPrzegladu.ZBLIZA_SIE
        )

    def test_przeglad_po_terminie_jest_przeterminowany(self) -> None:
        assert (
            status_przegladu(nastepny_termin=date(2026, 8, 24), dzis=DZIS)
            is StatusPrzegladu.PRZETERMINOWANY
        )

    def test_przeglad_dzis_jeszcze_nie_jest_przeterminowany(self) -> None:
        assert status_przegladu(nastepny_termin=DZIS, dzis=DZIS) is StatusPrzegladu.ZBLIZA_SIE


class TestKompletnosc:
    def test_pelny_profil(self) -> None:
        ocena = ocen_kompletnosc(POLA_KRYTYCZNE)
        assert ocena.kompletny
        assert ocena.wskaznik == Decimal("1")
        assert ocena.procent == 100

    def test_zaokraglenie_nie_przenosi_przez_prog_uzytecznosci(self) -> None:
        """Profil o kompletnosci 0,395 wyswietla sie jako 40 procent, ale nadal
        NIE jest uzyteczny. Prog dotyczy danych, nie tego, jak je pokazujemy.
        """
        ocena = ocen_kompletnosc({str(i) for i in range(79)}, wymagane={str(i) for i in range(200)})
        assert ocena.wskaznik == Decimal("0.395")
        assert ocena.procent == 40
        assert not ocena.uzyteczny

    def test_pusty_profil(self) -> None:
        ocena = ocen_kompletnosc([])
        assert not ocena.kompletny
        assert ocena.wskaznik == Decimal("0")
        assert ocena.brakujace == POLA_KRYTYCZNE
        assert not ocena.uzyteczny

    def test_polowa_pol(self) -> None:
        ocena = ocen_kompletnosc(
            {"najemca", "powierzchnia", "data_przekazania", "czynsz_podstawowy"}
        )
        assert ocena.wskaznik == Decimal("0.5")
        assert ocena.procent == 50
        assert ocena.uzyteczny

    def test_prog_uzytecznosci_40_procent(self) -> None:
        """Regula produktowa: ponizej 40 procent nie ma wyniku, a nie niski wynik."""
        trzy_z_osmiu = ocen_kompletnosc({"najemca", "powierzchnia", "czynsz_podstawowy"})
        assert trzy_z_osmiu.wskaznik == Decimal("0.375")
        assert trzy_z_osmiu.procent == 38
        assert not trzy_z_osmiu.uzyteczny

        cztery_z_osmiu = ocen_kompletnosc(
            {"najemca", "powierzchnia", "czynsz_podstawowy", "status_kaucji"}
        )
        assert cztery_z_osmiu.uzyteczny

    def test_pola_spoza_listy_nie_podnosza_wskaznika(self) -> None:
        """Inaczej wskaznik przestaje mierzyc to, co ma mierzyc."""
        ocena = ocen_kompletnosc({"najemca", "kolor_drzwi", "ulubiona_kawa"})
        assert ocena.wskaznik == Decimal("0.125")
        assert ocena.procent == 13
        assert ocena.wypelnione == frozenset({"najemca"})

    def test_wlasna_lista_wymaganych(self) -> None:
        ocena = ocen_kompletnosc({"a"}, wymagane={"a", "b"})
        assert ocena.wskaznik == Decimal("0.5")

    def test_pusta_lista_wymaganych_jest_bledem(self) -> None:
        with pytest.raises(ValueError, match="nie może być pusta"):
            ocen_kompletnosc({"a"}, wymagane=set())
