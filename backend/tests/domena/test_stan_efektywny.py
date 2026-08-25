"""Stan efektywny na dzien: serce mechaniki z decyzji D2.

Aneks nie nadpisuje wartosci, tylko doklada nowa wersje. Ten modul odpowiada
na pytanie "co obowiazuje danego dnia" i na pytanie "jaka byla stawka w maju".
"""

from datetime import date
from decimal import Decimal

import pytest

from najem.domena.parametry import (
    WartoscParametru,
    historia_klucza,
    klucze_bez_wartosci,
    stan_efektywny,
    wartosc_na_dzien,
)
from najem.domena.pieniadze import Kwota
from najem.domena.slowniki import RodzajKwoty, StatusWeryfikacji, TypWartosci

VAT23 = Decimal("23")


def kwota(wartosc: str) -> Kwota:
    return Kwota(Decimal(wartosc), "PLN", RodzajKwoty.NETTO, VAT23)


def czynsz(
    wartosc: str,
    od: date,
    do: date | None = None,
    status: StatusWeryfikacji = StatusWeryfikacji.ZATWIERDZONA,
    identyfikator: int | None = None,
) -> WartoscParametru:
    return WartoscParametru(
        klucz="czynsz_podstawowy",
        typ=TypWartosci.KWOTA,
        obowiazuje_od=od,
        obowiazuje_do=do,
        status=status,
        kwota=kwota(wartosc),
        identyfikator=identyfikator,
    )


class TestWartoscNaDzien:
    def test_brak_wartosci_daje_none_a_nie_wyjatek(self) -> None:
        """Brak danych to informacja, nie awaria (decyzja D5)."""
        assert wartosc_na_dzien([], "czynsz_podstawowy", date(2026, 5, 1)) is None

    def test_jedna_wartosc_obowiazujaca_bezterminowo(self) -> None:
        wartosci = [czynsz("12500.00", od=date(2026, 2, 1))]
        wynik = wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2026, 5, 1))
        assert wynik is not None
        assert wynik.kwota == kwota("12500.00")

    def test_wartosc_jeszcze_nieobowiazujaca_nie_wchodzi(self) -> None:
        """Aneks podpisany dzis, wchodzacy od marca, nie zmienia stanu na dzis."""
        wartosci = [czynsz("12500.00", od=date(2027, 3, 1))]
        assert wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2026, 5, 1)) is None

    def test_wartosc_juz_niaobowiazujaca_nie_wchodzi(self) -> None:
        wartosci = [czynsz("12500.00", od=date(2025, 1, 1), do=date(2025, 12, 31))]
        assert wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2026, 5, 1)) is None

    def test_granice_okresu_sa_domkniete(self) -> None:
        """Wartosc obowiazuje takze w pierwszym i ostatnim dniu swojego okresu."""
        wartosci = [czynsz("12500.00", od=date(2026, 2, 1), do=date(2026, 12, 31))]
        assert wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2026, 2, 1)) is not None
        assert wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2026, 12, 31)) is not None
        assert wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2026, 1, 31)) is None
        assert wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2027, 1, 1)) is None

    def test_aneks_zastepuje_wartosc_od_swojej_daty(self) -> None:
        wartosci = [
            czynsz("12500.00", od=date(2026, 2, 1)),
            czynsz("13000.00", od=date(2027, 3, 1)),
        ]
        przed = wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2027, 2, 28))
        po = wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2027, 3, 1))
        assert przed is not None and przed.kwota == kwota("12500.00")
        assert po is not None and po.kwota == kwota("13000.00")

    def test_historia_zostaje_nienaruszona(self) -> None:
        """Po aneksie nadal da sie odpowiedziec, jaka byla stawka w maju 2026."""
        wartosci = [
            czynsz("12500.00", od=date(2026, 2, 1)),
            czynsz("13000.00", od=date(2027, 3, 1)),
        ]
        maj = wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2026, 5, 15))
        assert maj is not None and maj.kwota == kwota("12500.00")

    def test_inny_klucz_nie_miesza_sie_do_wyniku(self) -> None:
        wartosci = [
            czynsz("12500.00", od=date(2026, 2, 1)),
            WartoscParametru(
                klucz="powierzchnia",
                typ=TypWartosci.LICZBA,
                obowiazuje_od=date(2026, 2, 1),
                obowiazuje_do=None,
                status=StatusWeryfikacji.ZATWIERDZONA,
                liczba=Decimal("128.5"),
            ),
        ]
        wynik = wartosc_na_dzien(wartosci, "powierzchnia", date(2026, 5, 1))
        assert wynik is not None and wynik.liczba == Decimal("128.5")


class TestWartosciNiezatwierdzone:
    def test_wartosc_zaproponowana_nie_wchodzi_do_stanu(self) -> None:
        """Decyzja D4: ekstrakcja proponuje, nie decyduje.

        To jest ta regula, ktora chroni przed jedna glosna pomylka w kwocie.
        """
        wartosci = [czynsz("12500.00", od=date(2026, 2, 1), status=StatusWeryfikacji.ZAPROPONOWANA)]
        assert wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2026, 5, 1)) is None

    def test_wartosc_odrzucona_nie_wchodzi(self) -> None:
        wartosci = [czynsz("99999.00", od=date(2026, 2, 1), status=StatusWeryfikacji.ODRZUCONA)]
        assert wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2026, 5, 1)) is None

    def test_wartosc_niejednoznaczna_nie_wchodzi(self) -> None:
        wartosci = [
            czynsz("12500.00", od=date(2026, 2, 1), status=StatusWeryfikacji.NIEJEDNOZNACZNA)
        ]
        assert wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2026, 5, 1)) is None

    def test_wartosc_poprawiona_wchodzi(self) -> None:
        """Poprawiona to zatwierdzona po korekcie czlowieka, wiec obowiazuje."""
        wartosci = [czynsz("12500.00", od=date(2026, 2, 1), status=StatusWeryfikacji.POPRAWIONA)]
        assert wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2026, 5, 1)) is not None

    def test_nowsza_wartosc_niezatwierdzona_nie_przesloni_starszej_zatwierdzonej(self) -> None:
        """Kluczowy przypadek. Ekstrakcja z aneksu proponuje 13 000, ale nikt
        tego jeszcze nie zatwierdzil. Stan efektywny ma dalej pokazywac 12 500,
        a nie pusto i nie 13 000.
        """
        wartosci = [
            czynsz("12500.00", od=date(2026, 2, 1)),
            czynsz("13000.00", od=date(2027, 3, 1), status=StatusWeryfikacji.ZAPROPONOWANA),
        ]
        wynik = wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2027, 6, 1))
        assert wynik is not None and wynik.kwota == kwota("12500.00")


class TestWartosciNakladajaceSie:
    def test_wygrywa_pozniejsza_data_obowiazywania(self) -> None:
        wartosci = [
            czynsz("12500.00", od=date(2026, 2, 1), do=date(2027, 12, 31)),
            czynsz("13000.00", od=date(2027, 3, 1)),
        ]
        wynik = wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2027, 6, 1))
        assert wynik is not None and wynik.kwota == kwota("13000.00")

    def test_przy_tej_samej_dacie_wygrywa_wiekszy_identyfikator(self) -> None:
        """Dwa aneksy wchodzace tego samego dnia. Rozstrzyga kolejnosc wprowadzenia,
        bo to jedyna informacja, ktora system ma. Regula musi byc deterministyczna,
        inaczej ten sam stan raz pokaze jedno, raz drugie.
        """
        wartosci = [
            czynsz("13000.00", od=date(2027, 3, 1), identyfikator=7),
            czynsz("12500.00", od=date(2027, 3, 1), identyfikator=3),
        ]
        wynik = wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2027, 6, 1))
        assert wynik is not None and wynik.kwota == kwota("13000.00")

    def test_kolejnosc_wejsciowa_nie_wplywa_na_wynik(self) -> None:
        wartosci = [
            czynsz("12500.00", od=date(2026, 2, 1), identyfikator=1),
            czynsz("13000.00", od=date(2027, 3, 1), identyfikator=2),
        ]
        a = wartosc_na_dzien(wartosci, "czynsz_podstawowy", date(2027, 6, 1))
        b = wartosc_na_dzien(list(reversed(wartosci)), "czynsz_podstawowy", date(2027, 6, 1))
        assert a == b


class TestStanEfektywny:
    def test_zwraca_po_jednej_wartosci_na_klucz(self) -> None:
        wartosci = [
            czynsz("12500.00", od=date(2026, 2, 1)),
            czynsz("13000.00", od=date(2027, 3, 1)),
            WartoscParametru(
                klucz="powierzchnia",
                typ=TypWartosci.LICZBA,
                obowiazuje_od=date(2026, 2, 1),
                obowiazuje_do=None,
                status=StatusWeryfikacji.ZATWIERDZONA,
                liczba=Decimal("128.5"),
            ),
        ]
        stan = stan_efektywny(wartosci, date(2027, 6, 1))
        assert set(stan) == {"czynsz_podstawowy", "powierzchnia"}
        assert stan["czynsz_podstawowy"].kwota == kwota("13000.00")

    def test_pusty_zbior_daje_pusty_stan(self) -> None:
        assert stan_efektywny([], date(2026, 5, 1)) == {}

    def test_klucz_bez_obowiazujacej_wartosci_nie_pojawia_sie_w_stanie(self) -> None:
        """Nie ma pozycji z wartoscia None. Brak klucza to brak klucza."""
        wartosci = [czynsz("12500.00", od=date(2027, 1, 1))]
        assert stan_efektywny(wartosci, date(2026, 5, 1)) == {}


class TestHistoria:
    def test_historia_jest_uporzadkowana_rosnaco(self) -> None:
        wartosci = [
            czynsz("13000.00", od=date(2027, 3, 1), identyfikator=2),
            czynsz("12500.00", od=date(2026, 2, 1), identyfikator=1),
        ]
        historia = historia_klucza(wartosci, "czynsz_podstawowy")
        assert [w.obowiazuje_od for w in historia] == [date(2026, 2, 1), date(2027, 3, 1)]

    def test_historia_pokazuje_takze_wartosci_niezatwierdzone(self) -> None:
        """Os czasu na karcie lokalu ma pokazywac propozycje czekajace na decyzje,
        wyroznione wizualnie. Filtrowanie ich tutaj ukryloby prace do zrobienia.
        """
        wartosci = [
            czynsz("12500.00", od=date(2026, 2, 1)),
            czynsz("13000.00", od=date(2027, 3, 1), status=StatusWeryfikacji.ZAPROPONOWANA),
        ]
        assert len(historia_klucza(wartosci, "czynsz_podstawowy")) == 2

    def test_historia_innego_klucza_jest_pusta(self) -> None:
        assert historia_klucza([czynsz("100.00", od=date(2026, 1, 1))], "powierzchnia") == []


class TestBrakiDanych:
    def test_wskazuje_klucze_bez_obowiazujacej_wartosci(self) -> None:
        """Podstawa wskaznika kompletnosci profilu (decyzja D6, regula R9)."""
        wartosci = [czynsz("12500.00", od=date(2026, 2, 1))]
        braki = klucze_bez_wartosci(
            wartosci,
            wymagane={"czynsz_podstawowy", "powierzchnia", "data_zakonczenia"},
            na_dzien=date(2026, 5, 1),
        )
        assert braki == {"powierzchnia", "data_zakonczenia"}

    def test_wartosc_niezatwierdzona_liczy_sie_jako_brak(self) -> None:
        """Profil z sama propozycja nie jest kompletny. Ktos musi ja zatwierdzic."""
        wartosci = [czynsz("12500.00", od=date(2026, 2, 1), status=StatusWeryfikacji.ZAPROPONOWANA)]
        braki = klucze_bez_wartosci(
            wartosci, wymagane={"czynsz_podstawowy"}, na_dzien=date(2026, 5, 1)
        )
        assert braki == {"czynsz_podstawowy"}

    def test_komplet_danych_daje_pusty_zbior(self) -> None:
        wartosci = [czynsz("12500.00", od=date(2026, 2, 1))]
        assert (
            klucze_bez_wartosci(wartosci, wymagane={"czynsz_podstawowy"}, na_dzien=date(2026, 5, 1))
            == set()
        )


class TestSpojnoscWartosci:
    def test_typ_musi_zgadzac_sie_z_wypelniona_kolumna(self) -> None:
        """To samo ograniczenie, ktore pilnuje baza. Warstwa domenowa dostaje
        dane takze z importu z Excela, wiec nie moze zakladac, ze przeszly
        przez ograniczenia bazy.
        """
        with pytest.raises(ValueError, match="kwota"):
            WartoscParametru(
                klucz="czynsz_podstawowy",
                typ=TypWartosci.KWOTA,
                obowiazuje_od=date(2026, 2, 1),
                obowiazuje_do=None,
                status=StatusWeryfikacji.ZATWIERDZONA,
                liczba=Decimal("100"),
            )

    def test_okres_konczacy_sie_przed_poczatkiem_jest_bledem(self) -> None:
        with pytest.raises(ValueError, match=r"[Oo]kres"):
            czynsz("100.00", od=date(2026, 5, 1), do=date(2026, 4, 1))

    def test_wypelnienie_dwoch_pol_wartosci_jest_bledem(self) -> None:
        with pytest.raises(ValueError, match="wypełniono także"):
            WartoscParametru(
                klucz="czynsz_podstawowy",
                typ=TypWartosci.KWOTA,
                obowiazuje_od=date(2026, 2, 1),
                obowiazuje_do=None,
                status=StatusWeryfikacji.ZATWIERDZONA,
                kwota=kwota("100.00"),
                tekst="sto zlotych",
            )
