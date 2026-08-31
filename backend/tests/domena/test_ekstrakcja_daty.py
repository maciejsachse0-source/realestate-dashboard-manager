"""Daty i terminy wyjęte z polskiego tekstu umowy.

Przypadki brzegowe obowiązkowe w tym projekcie: rok przestępny, przełom
miesiąca i roku, data, która nie istnieje.
"""

from datetime import date

import pytest

from najem.domena.ekstrakcja.daty import (
    rozwiaz_termin,
    zbuduj_date,
    znajdz_daty,
    znajdz_miesiac_waloryzacji,
    znajdz_okresy_najmu,
    znajdz_terminy_wzgledne,
)


class TestBudowanieDaty:
    def test_zwykla_data(self) -> None:
        assert zbuduj_date(2027, 3, 1) == date(2027, 3, 1)

    def test_rok_przestepny_ma_29_lutego(self) -> None:
        assert zbuduj_date(2028, 2, 29) == date(2028, 2, 29)

    def test_rok_nieprzestepny_nie_ma_29_lutego(self) -> None:
        """None, a nie cicha korekta na 28. Literówka ma być widoczna."""
        assert zbuduj_date(2027, 2, 29) is None

    @pytest.mark.parametrize(
        ("rok", "miesiac", "dzien"),
        [(2027, 2, 31), (2027, 13, 1), (2027, 0, 1), (2027, 4, 31), (2027, 1, 0)],
    )
    def test_daty_ktore_nie_istnieja(self, rok: int, miesiac: int, dzien: int) -> None:
        assert zbuduj_date(rok, miesiac, dzien) is None


class TestZnajdywanieDat:
    @pytest.mark.parametrize(
        ("tekst", "oczekiwana"),
        [
            ("zawarta dnia 01.03.2027 r.", date(2027, 3, 1)),
            ("zawarta dnia 1.3.2027 r.", date(2027, 3, 1)),
            ("zawarta dnia 01-03-2027 r.", date(2027, 3, 1)),
            ("zawarta dnia 01/03/2027 r.", date(2027, 3, 1)),
            ("obowiązuje od 2027-03-01", date(2027, 3, 1)),
            ("zawarta dnia 1 marca 2027 roku", date(2027, 3, 1)),
            ("zawarta dnia 15 września 2027 r.", date(2027, 9, 15)),
            ("zawarta dnia 15 wrzesnia 2027 r.", date(2027, 9, 15)),
        ],
    )
    def test_rozpoznaje_zapisy(self, tekst: str, oczekiwana: date) -> None:
        (trafienie,) = znajdz_daty(tekst)
        assert trafienie.wartosc == oczekiwana

    def test_zapis_kropkowy_czytamy_po_polsku(self) -> None:
        """03.01.2027 to 3 stycznia, nie 1 marca. Konwencja polska."""
        (trafienie,) = znajdz_daty("Umowa z dnia 03.01.2027 r.")
        assert trafienie.wartosc == date(2027, 1, 3)

    def test_offsety_wskazuja_zapis(self) -> None:
        tekst = "Protokół przekazania sporządzono 01.03.2027 r."
        (trafienie,) = znajdz_daty(tekst)
        assert tekst[trafienie.od : trafienie.do] == "01.03.2027"

    def test_kilka_dat_w_kolejnosci(self) -> None:
        tekst = "Zawarta 01.02.2026, przekazanie 15.02.2026, koniec 31.01.2028."
        assert [t.wartosc for t in znajdz_daty(tekst)] == [
            date(2026, 2, 1),
            date(2026, 2, 15),
            date(2028, 1, 31),
        ]

    def test_ten_sam_zapis_nie_jest_liczony_dwa_razy(self) -> None:
        """ISO i wzorzec kropkowy mogłyby zachodzić na siebie."""
        assert len(znajdz_daty("termin 2027-03-01 nieprzekraczalny")) == 1

    def test_sklejony_zakres_dat_nie_daje_daty_widma(self) -> None:
        """Odczyt tekstu z PDF-a potrafi zgubić spacje i skleić zakres w jeden
        ciąg. Wtedy wzorzec kropkowy widzi w „2027-03-01-2028" drugą datę
        (3 stycznia 2028), która w dokumencie nie istnieje. Wygrywa zapis
        rozpoznany wcześniej, czyli ISO."""
        trafienia = znajdz_daty("okres 2027-03-01-2028")
        assert [t.wartosc for t in trafienia] == [date(2027, 3, 1)]

    @pytest.mark.parametrize(
        ("tekst", "oczekiwana"),
        [
            ("w terminie do 30.06.2019r. zakonczy budowe", date(2019, 6, 30)),
            ("w terminie do 30.06.2019 r. zakonczy budowe", date(2019, 6, 30)),
            ("obowiazuje od 01.03.2027roku", date(2027, 3, 1)),
            ("umowa z 15.09.2026r", date(2026, 9, 15)),
        ],
    )
    def test_skrot_roku_sklejony_z_rokiem(self, tekst: str, oczekiwana: date) -> None:
        """„2019r." bez spacji to w polskich umowach zapis normalny. Granica
        slowa za rokiem nigdy tam nie wypada, bo cyfra i litera sa obie
        znakami slowa, wiec taka data przepadala w calosci."""
        (trafienie,) = znajdz_daty(tekst)
        assert trafienie.wartosc == oczekiwana

    def test_rok_nie_zjada_piatej_cyfry(self) -> None:
        """Rozluznienie granicy nie moze przepuscic „01.03.20275" jako roku
        2027. Za rokiem wolno stac litera, ale nie kolejna cyfra."""
        assert znajdz_daty("numer 01.03.20275 w rejestrze") == []

    def test_data_nieistniejaca_jest_pomijana(self) -> None:
        assert znajdz_daty("rzekomo 31.02.2027 r.") == []

    def test_brak_daty_to_pusta_lista(self) -> None:
        assert znajdz_daty("Umowa najmu lokalu użytkowego.") == []


class TestTerminowWzglednych:
    def test_polisa_w_terminie_od_przekazania(self) -> None:
        """Reguła R6: termin dostarczenia polisy jest zawsze względny."""
        tekst = "Najemca dostarczy polisę w terminie 14 dni od dnia przekazania lokalu."
        (termin,) = znajdz_terminy_wzgledne(tekst)
        assert termin.dni == 14
        assert termin.odniesienie == "data_przekazania"

    @pytest.mark.parametrize(
        ("tekst", "dni", "odniesienie"),
        [
            ("w terminie 14 dni od dnia przekazania,", 14, "data_przekazania"),
            ("w ciągu 30 dni od zawarcia umowy", 30, "data_zawarcia"),
            ("w terminie 7 dni od podpisania.", 7, "data_zawarcia"),
            ("w terminie 30 dni od zakończenia najmu", 30, "data_zakonczenia"),
        ],
    )
    def test_rozpoznaje_punkty_odniesienia(self, tekst: str, dni: int, odniesienie: str) -> None:
        (termin,) = znajdz_terminy_wzgledne(tekst)
        assert (termin.dni, termin.odniesienie) == (dni, odniesienie)

    @pytest.mark.parametrize(
        ("tekst", "dni", "odniesienie"),
        [
            (
                "Najemca okaze w terminie 14 dni od daty przekazania Obiektu"
                " stosowne polisy ubezpieczeniowe.",
                14,
                "data_przekazania",
            ),
            (
                "Najemca wplaci w terminie 7 dni od daty zawarcia niniejszej umowy"
                " kaucje zabezpieczajaca w wysokosci sumy 2 czynszow.",
                7,
                "data_zawarcia",
            ),
            (
                "Najemca w ciągu 7 dni od dnia podpisania niniejszej umowy wystawi"
                " weksel wlasny in blanco.",
                7,
                "data_zawarcia",
            ),
            (
                "zwrot nastapi w terminie 30 dni od dnia zwrotu lokalu Wynajmujacemu",
                30,
                "data_zakonczenia",
            ),
        ],
    )
    def test_termin_w_zdaniu_bez_przecinka(self, tekst: str, dni: int, odniesienie: str) -> None:
        """Tak te terminy stoja w prawdziwych umowach: „od daty przekazania
        Obiektu stosowne polisy", bez przecinka i bez slowa „lokalu" tuz za
        punktem odniesienia. Wczesniejszy wzorzec wymagal jednego albo
        drugiego i nie znajdowal ani terminu polisy (R6), ani kaucji (R4)."""
        (termin,) = znajdz_terminy_wzgledne(tekst)
        assert (termin.dni, termin.odniesienie) == (dni, odniesienie)

    def test_punkt_odniesienia_ktorego_nie_znamy_nie_jest_zgadywany(self) -> None:
        """„od daty kiedy decyzja stanie sie ostateczna" to zdarzenie, ktorego
        system nie zna. Podstawienie pod nie daty zawarcia byloby zgadywaniem
        (decyzja D5) — takie zdanie jest w tych umowach naprawde."""
        tekst = (
            "nastapi najpozniej w terminie 7 dni od daty kiedy decyzja"
            " o pozwoleniu na uzytkowanie stanie sie ostateczna"
        )
        assert znajdz_terminy_wzgledne(tekst) == []

    def test_nieznany_punkt_odniesienia_jest_pomijany(self) -> None:
        """„14 dni od czegoś" to nie termin. Podstawienie daty byłoby zgadywaniem."""
        assert znajdz_terminy_wzgledne("w terminie 14 dni od wezwania.") == []

    def test_rozwiazanie_terminu(self) -> None:
        (termin,) = znajdz_terminy_wzgledne("w terminie 14 dni od dnia przekazania,")
        assert rozwiaz_termin(termin, date(2027, 3, 1)) == date(2027, 3, 15)

    def test_termin_przez_przelom_miesiaca(self) -> None:
        (termin,) = znajdz_terminy_wzgledne("w terminie 14 dni od dnia przekazania,")
        assert rozwiaz_termin(termin, date(2027, 1, 25)) == date(2027, 2, 8)

    def test_termin_przez_przelom_roku(self) -> None:
        (termin,) = znajdz_terminy_wzgledne("w terminie 30 dni od dnia przekazania,")
        assert rozwiaz_termin(termin, date(2027, 12, 15)) == date(2028, 1, 14)

    def test_termin_przez_luty_roku_przestepnego(self) -> None:
        (termin,) = znajdz_terminy_wzgledne("w terminie 14 dni od dnia przekazania,")
        assert rozwiaz_termin(termin, date(2028, 2, 20)) == date(2028, 3, 5)


class TestOkresuNajmu:
    @pytest.mark.parametrize(
        ("tekst", "miesiace"),
        [
            ("na czas określony 24 miesięcy", 24),
            ("na okres 36 miesięcy", 36),
            ("na 24 miesiące", 24),
            ("na okres 24 (dwadzieścia cztery) miesięcy", 24),
            ("na okres 3 lat", 36),
            ("na 2 lata", 24),
        ],
    )
    def test_sprowadza_do_miesiecy(self, tekst: str, miesiace: int) -> None:
        wyniki = znajdz_okresy_najmu(tekst)
        assert wyniki[0][0] == miesiace

    def test_miesiace_wygrywaja_z_latami_gdy_zachodza(self) -> None:
        """„24 miesiące" nie może zostać policzone także jako lata."""
        assert len(znajdz_okresy_najmu("na okres 24 miesięcy")) == 1

    def test_brak_okresu(self) -> None:
        assert znajdz_okresy_najmu("Umowa na czas nieokreślony.") == []


class TestMiesiacaWaloryzacji:
    @pytest.mark.parametrize(
        ("tekst", "miesiac"),
        [
            ("Waloryzacja następuje w styczniu.", 1),
            ("Waloryzacja w miesiącu styczeń.", 1),
            ("Waloryzacja od 1 stycznia każdego roku.", 1),
            ("Czynsz waloryzowany w lutym.", 2),
            ("Waloryzacja we wrześniu.", 9),
        ],
    )
    def test_jednoznaczny_miesiac(self, tekst: str, miesiac: int) -> None:
        assert znajdz_miesiac_waloryzacji(tekst) == miesiac

    def test_nazwa_miesiaca_w_srodku_slowa_sie_nie_liczy(self) -> None:
        """„maj" siedzi w „majątku", a „rok" w „rokowaniach"."""
        assert znajdz_miesiac_waloryzacji("Waloryzacja obejmuje majątek trwały.") is None

    def test_dwa_miesiace_to_brak_odpowiedzi(self) -> None:
        """Dwa miesiące w zdaniu to powód do pytania człowieka, nie do wyboru."""
        tekst = "Waloryzacja w styczeń albo luty, zależnie od wskaźnika."
        assert znajdz_miesiac_waloryzacji(tekst) is None

    def test_brak_miesiaca(self) -> None:
        assert znajdz_miesiac_waloryzacji("Waloryzacja w rocznicę zawarcia.") is None
