"""Rozpoznawanie dokumentow po nazwie pliku.

Nazwy w tych testach sa wymyslone, ale ich ksztalt odwzorowuje to, jak
uzytkownik faktycznie nazywa pliki: raz z ogonkami, raz bez, raz z numerem
aneksu, raz z podkresleniami zamiast spacji.
"""

import pytest

from najem.domena.skan import (
    bez_ogonkow,
    czy_plik_dokumentu,
    numer_z_nazwy,
    rozpoznaj_typ_z_nazwy,
)
from najem.domena.slowniki import TypDokumentu


class TestRozpoznawanieTypu:
    @pytest.mark.parametrize(
        ("nazwa", "oczekiwany"),
        [
            ("Umowa najmu.pdf", TypDokumentu.UMOWA),
            ("umowa_najmu_lokal_3.docx", TypDokumentu.UMOWA),
            ("Aneks nr 2.pdf", TypDokumentu.ANEKS),
            ("Protokół przekazania lokalu.pdf", TypDokumentu.PROTOKOL_PRZEKAZANIA),
            ("protokol przekazania lokalu.pdf", TypDokumentu.PROTOKOL_PRZEKAZANIA),
            ("Polisa OC 2026.pdf", TypDokumentu.POLISA),
            ("wypowiedzenie umowy.pdf", TypDokumentu.WYPOWIEDZENIE),
            ("Przegląd gaśnic 2026.pdf", TypDokumentu.PROTOKOL_PRZEGLADU),
            ("Protokol zdawczy.pdf", TypDokumentu.PROTOKOL_ZDAWCZY),
        ],
    )
    def test_typowe_nazwy(self, nazwa: str, oczekiwany: TypDokumentu) -> None:
        assert rozpoznaj_typ_z_nazwy(nazwa) == oczekiwany

    def test_aneks_wygrywa_nad_umowa(self) -> None:
        """ "Aneks do umowy najmu" to aneks. Kolejnosc wzorcow to zasada,
        a nie przypadek."""
        assert rozpoznaj_typ_z_nazwy("Aneks nr 1 do umowy najmu.pdf") == TypDokumentu.ANEKS

    def test_nierozpoznana_nazwa_nie_dostaje_typu_domyslnego(self) -> None:
        """Decyzja D5: brak danych to informacja, nie wartosc podstawiona."""
        assert rozpoznaj_typ_z_nazwy("skan_0012.pdf") is None
        assert rozpoznaj_typ_z_nazwy("dokument.pdf") is None

    def test_zdawczo_odbiorczy_jest_dwuznaczny(self) -> None:
        """Ten sam protokol bywa przy wydaniu lokalu i przy jego zwrocie.
        Z nazwy nie da sie tego rozstrzygnac, wiec nie zgadujemy."""
        assert rozpoznaj_typ_z_nazwy("Protokół zdawczo-odbiorczy.pdf") is None
        assert rozpoznaj_typ_z_nazwy("protokol zdawczo odbiorczy 2026.pdf") is None

    def test_rozszerzenie_nie_wchodzi_do_dopasowania(self) -> None:
        """Koncowka ".doc" zawiera "oc", a to skrot polisy. Gdyby rozszerzenie
        bylo dopasowywane, kazda umowa w starym formacie Worda byla polisa."""
        assert rozpoznaj_typ_z_nazwy("Umowa najmu.doc") == TypDokumentu.UMOWA


class TestNumerAneksu:
    @pytest.mark.parametrize(
        ("nazwa", "oczekiwany"),
        [
            ("Aneks nr 2 do umowy.pdf", "2"),
            ("aneks_3.docx", "3"),
            ("Aneks nr. 03 z 2026.pdf", "3"),
            ("ANEKS 12.pdf", "12"),
        ],
    )
    def test_numer_z_nazwy(self, nazwa: str, oczekiwany: str) -> None:
        assert numer_z_nazwy(nazwa) == oczekiwany

    def test_aneks_bez_numeru(self) -> None:
        assert numer_z_nazwy("Aneks do umowy.pdf") is None

    def test_zera_wiodace_znikaja(self) -> None:
        """ "03" i "3" to ten sam aneks, a nie dwa rozne."""
        assert numer_z_nazwy("aneks 03.pdf") == numer_z_nazwy("aneks 3.pdf")

    @pytest.mark.parametrize(
        ("nazwa", "oczekiwany"),
        [
            ("Aneks nr 2_16.05.2022_ Hansa Flex.doc", "2"),
            ("Aneks nr 1_01.07.2021.doc", "1"),
            ("aneks nr 3-15.01.2020.pdf", "3"),
            ("Aneks nr 2.16.05.2022.doc", "2"),
        ],
    )
    def test_numer_sklejony_z_data(self, nazwa: str, oczekiwany: str) -> None:
        """Uzytkownik pisze "Aneks nr 2_16.05.2022_ Najemca.doc" i to jest
        w tym archiwum norma, nie wyjatek. Podkreslnik zaraz za cyfra jest
        znakiem slowa, wiec granica slowa za numerem nigdy tam nie wypada
        i numer przepadal na trzech aneksach z czterech."""
        assert numer_z_nazwy(nazwa) == oczekiwany

    def test_numer_nie_zjada_cyfr_z_daty(self) -> None:
        """Numer to "2", a nie "216" ani "2_1". Data zaraz obok nie ma prawa
        wejsc do numeru."""
        assert numer_z_nazwy("Aneks nr 2_2022.doc") == "2"

    def test_liczba_w_nazwie_bez_aneksu_nie_jest_numerem(self) -> None:
        assert numer_z_nazwy("Umowa najmu 2026.pdf") is None

    def test_data_przed_slowem_aneks_nie_jest_numerem(self) -> None:
        """ "11.02.2020_ aneks Eco Club.doc" -- data stoi PRZED slowem "aneks",
        wiec nie jest jego numerem. Ten aneks numeru w nazwie nie ma."""
        assert numer_z_nazwy("11.02.2020_ aneks Eco Club.doc") is None


class TestFiltrPlikow:
    @pytest.mark.parametrize(
        "nazwa", ["Umowa.pdf", "umowa.PDF", "aneks.docx", "stara umowa.doc", "skan.jpg"]
    )
    def test_dokumenty_przechodza(self, nazwa: str) -> None:
        assert czy_plik_dokumentu(nazwa)

    @pytest.mark.parametrize(
        "nazwa", ["~$umowa.docx", ".DS_Store", "Thumbs.db", "notatki.txt", "bez_rozszerzenia"]
    )
    def test_smieci_odpadaja(self, nazwa: str) -> None:
        assert not czy_plik_dokumentu(nazwa)


class TestNormalizacja:
    def test_ogonki_znikaja(self) -> None:
        assert bez_ogonkow("Protokół Zdawczy ŻÓŁĆ") == "protokol zdawczy zolc"

    def test_l_z_kreska_tez(self) -> None:
        """ "ł" nie rozklada sie przez NFKD, wiec wymaga osobnej podmiany."""
        assert "l" in bez_ogonkow("Łódź")
        assert bez_ogonkow("Łódź") == "lodz"
