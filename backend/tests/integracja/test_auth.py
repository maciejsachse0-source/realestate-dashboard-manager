"""Uwierzytelnianie, sesje, blokada konta i hierarchia rol."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from najem.auth.haslo import SlabeHaslo, wygeneruj_haslo, zahaszuj, zweryfikuj
from najem.auth.sesje import (
    LIMIT_NIEUDANYCH_LOGOWAN,
    BladLogowania,
    KontoZablokowane,
    odczytaj_sesje,
    uniewaznij_wszystkie,
    wyloguj,
    zaloguj,
)
from najem.auth.zaleznosci import POZIOM_ROLI
from najem.domena.slowniki import OperacjaAudytu, RolaUzytkownika
from najem.modele import LogAudytu, Uzytkownik
from najem.modele.sesje import SesjaUzytkownika
from najem.uslugi.audyt import UTAJNIONE, zapisz_zmiane
from najem.uslugi.inicjalizacja import zapewnij_konto_administratora

pytestmark = pytest.mark.integracja

TERAZ = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
HASLO = "PoprawneHaslo123"


@pytest.fixture
def operator(sesja: Session) -> Uzytkownik:
    u = Uzytkownik(
        login="operator",
        imie_nazwisko="Anna Operator",
        rola=RolaUzytkownika.OPERATOR,
        hash_hasla=zahaszuj(HASLO),
        wymaga_zmiany_hasla=False,
    )
    sesja.add(u)
    sesja.flush()
    return u


class TestHaszowanie:
    def test_poprawne_haslo_przechodzi(self) -> None:
        assert zweryfikuj(zahaszuj(HASLO), HASLO)

    def test_bledne_haslo_nie_przechodzi(self) -> None:
        assert not zweryfikuj(zahaszuj(HASLO), "InneHaslo12345")

    def test_ten_sam_tekst_daje_rozne_skroty(self) -> None:
        """Argon2 dokłada sól, więc dwa konta o tym samym haśle mają różne skróty."""
        assert zahaszuj(HASLO) != zahaszuj(HASLO)

    def test_brak_skrotu_nie_wywala_weryfikacji(self) -> None:
        """Konto bez ustawionego hasła zwraca fałsz, a nie wyjątek."""
        assert not zweryfikuj(None, HASLO)

    def test_krotkie_haslo_jest_odrzucane(self) -> None:
        with pytest.raises(SlabeHaslo, match="12 znaków"):
            zahaszuj("krotkie")

    def test_wygenerowane_haslo_spelnia_wymagania(self) -> None:
        for _ in range(5):
            zahaszuj(wygeneruj_haslo())


class TestLogowanie:
    def test_udane_logowanie_zaklada_sesje(self, sesja: Session, operator: Uzytkownik) -> None:
        uzytkownik, token = zaloguj(sesja, login="operator", haslo=HASLO, teraz=TERAZ)
        assert uzytkownik.id == operator.id
        assert token

        zalogowany = odczytaj_sesje(sesja, token, TERAZ)
        assert zalogowany is not None
        assert zalogowany.uzytkownik.id == operator.id

    def test_token_nie_jest_zapisywany_w_bazie(self, sesja: Session, operator: Uzytkownik) -> None:
        """W bazie leży skrót. Wyciek tabeli nie pozwala się nikim podszyć."""
        _, token = zaloguj(sesja, login="operator", haslo=HASLO, teraz=TERAZ)
        wpisy = sesja.scalars(select(SesjaUzytkownika)).all()
        assert len(wpisy) == 1
        assert wpisy[0].token_hash != token
        assert len(wpisy[0].token_hash) == 64

    def test_bledne_haslo_odrzucone(self, sesja: Session, operator: Uzytkownik) -> None:
        with pytest.raises(BladLogowania):
            zaloguj(sesja, login="operator", haslo="ZleHaslo12345", teraz=TERAZ)

    def test_nieistniejacy_login_daje_ten_sam_komunikat(self, sesja: Session) -> None:
        """Komunikat nie zdradza, które loginy istnieją."""
        with pytest.raises(BladLogowania, match="Nieprawidłowy login lub hasło"):
            zaloguj(sesja, login="nieistnieje", haslo=HASLO, teraz=TERAZ)

    def test_konto_nieaktywne_nie_loguje_sie(self, sesja: Session, operator: Uzytkownik) -> None:
        operator.aktywny = False
        sesja.flush()
        with pytest.raises(BladLogowania, match="nieaktywne"):
            zaloguj(sesja, login="operator", haslo=HASLO, teraz=TERAZ)

    def test_udane_logowanie_zeruje_licznik_nieudanych(
        self, sesja: Session, operator: Uzytkownik
    ) -> None:
        operator.nieudane_logowania = 3
        sesja.flush()
        zaloguj(sesja, login="operator", haslo=HASLO, teraz=TERAZ)
        assert operator.nieudane_logowania == 0
        assert operator.ostatnie_logowanie == TERAZ


class TestBlokadaKonta:
    def test_blokada_po_piatej_nieudanej_probie(self, sesja: Session, operator: Uzytkownik) -> None:
        """Punkt K planu: blokada po 5 nieudanych próbach na 15 minut."""
        for _ in range(LIMIT_NIEUDANYCH_LOGOWAN - 1):
            with pytest.raises(BladLogowania):
                zaloguj(sesja, login="operator", haslo="zle", teraz=TERAZ)

        with pytest.raises(KontoZablokowane):
            zaloguj(sesja, login="operator", haslo="zle", teraz=TERAZ)

        assert operator.zablokowany_do is not None

    def test_zablokowane_konto_odrzuca_takze_poprawne_haslo(
        self, sesja: Session, operator: Uzytkownik
    ) -> None:
        """Inaczej blokada nie chroni przed niczym."""
        operator.zablokowany_do = TERAZ + timedelta(minutes=10)
        sesja.flush()
        with pytest.raises(KontoZablokowane):
            zaloguj(sesja, login="operator", haslo=HASLO, teraz=TERAZ)

    def test_po_uplywie_blokady_mozna_sie_zalogowac(
        self, sesja: Session, operator: Uzytkownik
    ) -> None:
        operator.zablokowany_do = TERAZ - timedelta(minutes=1)
        sesja.flush()
        uzytkownik, _ = zaloguj(sesja, login="operator", haslo=HASLO, teraz=TERAZ)
        assert uzytkownik.zablokowany_do is None


class TestSesje:
    def test_wygasla_sesja_nie_jest_wazna(self, sesja: Session, operator: Uzytkownik) -> None:
        _, token = zaloguj(sesja, login="operator", haslo=HASLO, teraz=TERAZ)
        assert odczytaj_sesje(sesja, token, TERAZ + timedelta(hours=13)) is None

    def test_wylogowanie_uniewaznia_sesje(self, sesja: Session, operator: Uzytkownik) -> None:
        _, token = zaloguj(sesja, login="operator", haslo=HASLO, teraz=TERAZ)
        wyloguj(sesja, token, TERAZ)
        assert odczytaj_sesje(sesja, token, TERAZ) is None

    def test_nieznany_token_nie_daje_dostepu(self, sesja: Session) -> None:
        assert odczytaj_sesje(sesja, "wymyslony-token", TERAZ) is None

    def test_dezaktywacja_konta_odcina_czynne_sesje(
        self, sesja: Session, operator: Uzytkownik
    ) -> None:
        """Administrator musi móc odciąć dostęp natychmiast, bez czekania
        na wygaśnięcie ciasteczka.
        """
        _, token = zaloguj(sesja, login="operator", haslo=HASLO, teraz=TERAZ)
        operator.aktywny = False
        sesja.flush()
        assert odczytaj_sesje(sesja, token, TERAZ) is None

    def test_uniewaznienie_wszystkich_sesji(self, sesja: Session, operator: Uzytkownik) -> None:
        tokeny = [zaloguj(sesja, login="operator", haslo=HASLO, teraz=TERAZ)[1] for _ in range(3)]
        assert uniewaznij_wszystkie(sesja, operator.id, TERAZ) == 3
        for token in tokeny:
            assert odczytaj_sesje(sesja, token, TERAZ) is None


class TestHierarchiaRol:
    def test_kolejnosc_uprawnien(self) -> None:
        assert (
            POZIOM_ROLI[RolaUzytkownika.PODGLAD]
            < POZIOM_ROLI[RolaUzytkownika.OPERATOR]
            < POZIOM_ROLI[RolaUzytkownika.ZARZADCA]
            < POZIOM_ROLI[RolaUzytkownika.ADMINISTRATOR]
        )

    def test_kazda_rola_ma_poziom(self) -> None:
        assert set(POZIOM_ROLI) == set(RolaUzytkownika)


class TestAudyt:
    def test_zmiana_pola_trafia_do_logu(self, sesja: Session, operator: Uzytkownik) -> None:
        operator.imie_nazwisko = "Anna Nowak"
        zapisz_zmiane(sesja, operator, operacja=OperacjaAudytu.ZMIANA, uzytkownik_id=operator.id)
        sesja.flush()

        wpisy = sesja.scalars(select(LogAudytu).where(LogAudytu.pole == "imie_nazwisko")).all()
        assert len(wpisy) == 1
        assert wpisy[0].wartosc_stara == "Anna Operator"
        assert wpisy[0].wartosc_nowa == "Anna Nowak"

    def test_skrot_hasla_nie_trafia_do_logu(self, sesja: Session, operator: Uzytkownik) -> None:
        """Skrót hasła w logu audytu to ten sam sekret w drugiej tabeli."""
        stary = operator.hash_hasla
        operator.hash_hasla = zahaszuj("ZupelnieInne12345")
        zapisz_zmiane(sesja, operator, operacja=OperacjaAudytu.ZMIANA, uzytkownik_id=operator.id)
        sesja.flush()

        wpis = sesja.scalars(select(LogAudytu).where(LogAudytu.pole == "hash_hasla")).one()
        assert wpis.wartosc_stara == UTAJNIONE
        assert wpis.wartosc_nowa == UTAJNIONE
        assert stary not in (wpis.wartosc_stara, wpis.wartosc_nowa)

    def test_pola_techniczne_nie_smieca_w_logu(self, sesja: Session, operator: Uzytkownik) -> None:
        operator.imie_nazwisko = "Anna Nowak"
        sesja.flush()
        operator.imie_nazwisko = "Anna Kowalska"
        zapisz_zmiane(sesja, operator, operacja=OperacjaAudytu.ZMIANA, uzytkownik_id=operator.id)
        sesja.flush()

        pola = {w.pole for w in sesja.scalars(select(LogAudytu)).all()}
        assert "wersja" not in pola
        assert "zmodyfikowano" not in pola

    def test_utworzenie_zapisuje_jeden_wpis_bez_pola(self, sesja: Session) -> None:
        nowy = Uzytkownik(login="nowy", imie_nazwisko="Nowy", rola=RolaUzytkownika.PODGLAD)
        sesja.add(nowy)
        sesja.flush()
        zapisz_zmiane(sesja, nowy, operacja=OperacjaAudytu.UTWORZENIE, uzytkownik_id=None)
        sesja.flush()

        wpis = sesja.scalars(
            select(LogAudytu).where(LogAudytu.operacja == OperacjaAudytu.UTWORZENIE)
        ).one()
        assert wpis.pole is None
        assert wpis.rekord_id == nowy.id


class TestKontoPoczatkowe:
    def test_pusta_baza_dostaje_administratora(self, sesja: Session) -> None:
        konto = zapewnij_konto_administratora(sesja)
        assert konto is not None
        assert konto.login == "administrator"

        uzytkownik = sesja.scalars(
            select(Uzytkownik).where(Uzytkownik.login == "administrator")
        ).one()
        assert uzytkownik.rola is RolaUzytkownika.ADMINISTRATOR
        assert uzytkownik.wymaga_zmiany_hasla
        assert zweryfikuj(uzytkownik.hash_hasla, konto.haslo)

    def test_drugie_uruchomienie_niczego_nie_tworzy(self, sesja: Session) -> None:
        assert zapewnij_konto_administratora(sesja) is not None
        sesja.flush()
        assert zapewnij_konto_administratora(sesja) is None

    def test_istniejacy_uzytkownik_blokuje_tworzenie(
        self, sesja: Session, operator: Uzytkownik
    ) -> None:
        assert zapewnij_konto_administratora(sesja) is None

    def test_haslo_poczatkowe_jest_losowe(self, sesja: Session) -> None:
        """Żadnego domyślnego hasła w kodzie: takie zostaje na produkcji na zawsze."""
        pierwsze = zapewnij_konto_administratora(sesja)
        assert pierwsze is not None
        sesja.rollback()
        drugie = zapewnij_konto_administratora(sesja)
        assert drugie is not None
        assert pierwsze.haslo != drugie.haslo
