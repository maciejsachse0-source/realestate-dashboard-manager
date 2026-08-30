"""Model danych na zywej bazie: tworzenie, kaskady, unikalnosc, miekkie usuwanie,
konflikt wersji i ograniczenia, ktore maja nie przepuscic zlych danych.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from najem.domena.slowniki import (
    BazaOkresuNajmu,
    OperacjaAudytu,
    RodzajKwoty,
    RodzajZabezpieczenia,
    StatusOkresuNajmu,
    StatusWeryfikacji,
    TypDokumentu,
    TypLokalu,
    TypWartosci,
    TypZdarzenia,
    WagaZdarzenia,
)
from najem.modele import (
    Budynek,
    Dokument,
    LogAudytu,
    Lokal,
    Najemca,
    OkresNajmu,
    ParametrWartosc,
    Zabezpieczenie,
    Zdarzenie,
)

pytestmark = pytest.mark.integracja


def _okres(sesja: Session, lokal: Lokal, najemca: Najemca) -> OkresNajmu:
    okres = OkresNajmu(
        lokal_id=lokal.id,
        najemca_id=najemca.id,
        data_zawarcia=date(2026, 1, 15),
        data_przekazania=date(2026, 2, 1),
        bazuje_na_dacie=BazaOkresuNajmu.DATA_PRZEKAZANIA,
        okres_zawarcia_miesiace=24,
        status=StatusOkresuNajmu.AKTYWNA,
    )
    sesja.add(okres)
    sesja.flush()
    return okres


class TestTworzenieEncji:
    def test_pelna_sciezka_od_budynku_do_parametru(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        okres = _okres(sesja, lokal, najemca)

        dokument = Dokument(
            okres_najmu_id=okres.id,
            typ=TypDokumentu.UMOWA,
            numer="12/2026",
            data_dokumentu=date(2026, 1, 15),
            hash_sha256="a" * 64,
        )
        sesja.add(dokument)
        sesja.flush()

        parametr = ParametrWartosc(
            okres_najmu_id=okres.id,
            klucz="czynsz_podstawowy",
            typ_wartosci=TypWartosci.KWOTA,
            wartosc_kwota=Decimal("12500.00"),
            wartosc_waluta="PLN",
            wartosc_rodzaj_kwoty=RodzajKwoty.NETTO,
            wartosc_stawka_vat=Decimal("23.00"),
            obowiazuje_od=date(2026, 2, 1),
            dokument_zrodlowy_id=dokument.id,
            zrodlo_strona=3,
            zrodlo_paragraf="par. 5 ust. 1",
            status_weryfikacji=StatusWeryfikacji.ZATWIERDZONA,
            zatwierdzono_dnia=datetime.now(UTC),
        )
        sesja.add(parametr)
        sesja.flush()

        assert parametr.id is not None
        assert parametr.wersja == 1
        assert okres.parametry == [parametr]

    def test_kwoty_wracaja_z_bazy_jako_decimal_a_nie_float(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        """Gdyby kolumna byla FLOAT, 0.1 + 0.2 przestaloby sie zgadzac na fakturze."""
        okres = _okres(sesja, lokal, najemca)
        sesja.add(
            ParametrWartosc(
                okres_najmu_id=okres.id,
                klucz="czynsz_podstawowy",
                typ_wartosci=TypWartosci.KWOTA,
                wartosc_kwota=Decimal("1234.56"),
                wartosc_waluta="PLN",
                wartosc_rodzaj_kwoty=RodzajKwoty.BRUTTO,
                obowiazuje_od=date(2026, 2, 1),
            )
        )
        sesja.flush()
        sesja.expire_all()

        odczytany = sesja.scalars(select(ParametrWartosc)).one()
        assert isinstance(odczytany.wartosc_kwota, Decimal)
        assert odczytany.wartosc_kwota == Decimal("1234.56")

    def test_znaczniki_czasu_maja_strefe(self, sesja: Session, budynek: Budynek) -> None:
        sesja.refresh(budynek)
        assert budynek.utworzono.tzinfo is not None


class TestUnikalnosc:
    def test_oznaczenie_lokalu_unikalne_w_budynku(
        self, sesja: Session, budynek: Budynek, lokal: Lokal
    ) -> None:
        sesja.add(Lokal(budynek_id=budynek.id, oznaczenie=lokal.oznaczenie, typ=TypLokalu.BIUROWY))
        with pytest.raises(IntegrityError):
            sesja.flush()

    def test_to_samo_oznaczenie_w_innym_budynku_jest_dozwolone(
        self, sesja: Session, lokal: Lokal
    ) -> None:
        inny = Budynek(nazwa="20C")
        sesja.add(inny)
        sesja.flush()
        sesja.add(Lokal(budynek_id=inny.id, oznaczenie=lokal.oznaczenie, typ=TypLokalu.BIUROWY))
        sesja.flush()

    def test_ten_sam_plik_nie_wchodzi_dwa_razy(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        """Deduplikacja po SHA-256 (plan budowy, sekcja E7)."""
        okres = _okres(sesja, lokal, najemca)
        for _ in range(2):
            sesja.add(
                Dokument(okres_najmu_id=okres.id, typ=TypDokumentu.UMOWA, hash_sha256="b" * 64)
            )
        with pytest.raises(IntegrityError):
            sesja.flush()

    def test_generator_zdarzen_nie_zdubluje_alertu(self, sesja: Session, lokal: Lokal) -> None:
        """Klucz naturalny wymusza idempotencje generatora (plan, punkt M).

        To jest ograniczenie, o ktore opiera sie ON CONFLICT DO NOTHING w etapie E3.
        """
        for _ in range(2):
            sesja.add(
                Zdarzenie(
                    typ=TypZdarzenia.KONIEC_UMOWY_SIE_ZBLIZA,
                    encja_typ="okres_najmu",
                    encja_id=1,
                    lokal_id=lokal.id,
                    data_zdarzenia=date(2027, 1, 1),
                    waga=WagaZdarzenia.OSTRZEZENIE,
                    tresc="Umowa konczy sie za 90 dni.",
                )
            )
        with pytest.raises(IntegrityError):
            sesja.flush()


class TestMiekkieUsuwanie:
    def test_po_usunieciu_mozna_zalozyc_lokal_o_tym_samym_oznaczeniu(
        self, sesja: Session, budynek: Budynek, lokal: Lokal
    ) -> None:
        """Indeks unikalny jest czesciowy, wiec usuniety rekord nie blokuje nowego."""
        lokal.usunieto_dnia = datetime.now(UTC)
        sesja.flush()

        sesja.add(Lokal(budynek_id=budynek.id, oznaczenie="18A/12", typ=TypLokalu.BIUROWY))
        sesja.flush()

        wszystkie = sesja.scalars(select(Lokal).where(Lokal.oznaczenie == "18A/12")).all()
        assert len(wszystkie) == 2
        assert sum(1 for lok in wszystkie if not lok.czy_usuniety) == 1

    def test_usuniety_rekord_zostaje_w_bazie(self, sesja: Session, lokal: Lokal) -> None:
        lokal.usunieto_dnia = datetime.now(UTC)
        sesja.flush()
        sesja.expire_all()
        assert sesja.get(Lokal, lokal.id) is not None


class TestKaskady:
    def test_usuniecie_okresu_zabiera_jego_parametry(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        """Parametr bez okresu najmu nie znaczy nic, wiec idzie razem z nim."""
        okres = _okres(sesja, lokal, najemca)
        sesja.add(
            ParametrWartosc(
                okres_najmu_id=okres.id,
                klucz="powierzchnia",
                typ_wartosci=TypWartosci.LICZBA,
                wartosc_liczba=Decimal("128.500000"),
                obowiazuje_od=date(2026, 2, 1),
            )
        )
        sesja.flush()

        sesja.delete(okres)
        sesja.flush()
        assert sesja.scalars(select(ParametrWartosc)).all() == []

    def test_lokalu_z_umowa_nie_da_sie_usunac_twardo(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        """RESTRICT na kluczu obcym. Lokal usuwa sie miekko albo wcale."""
        _okres(sesja, lokal, najemca)
        sesja.delete(lokal)
        with pytest.raises(IntegrityError):
            sesja.flush()


class TestKonfliktWersji:
    def test_druga_osoba_dostaje_konflikt_zamiast_nadpisac(
        self, sesja: Session, budynek: Budynek
    ) -> None:
        """Dwie osoby edytuja ten sam profil. Bez tego cicha utrata zmian."""
        assert budynek.wersja == 1

        # Ktos inny zapisal zmiane w miedzyczasie, poza nasza sesja.
        sesja.execute(
            text("UPDATE budynek SET wersja = wersja + 1, nazwa = :n WHERE id = :i"),
            {"n": "18A (zmienione gdzie indziej)", "i": budynek.id},
        )

        budynek.nazwa = "18A (nasza zmiana)"
        with pytest.raises(StaleDataError):
            sesja.flush()

    def test_wersja_rosnie_przy_kazdym_zapisie(self, sesja: Session, budynek: Budynek) -> None:
        budynek.adres = "ul. Inna 1"
        sesja.flush()
        assert budynek.wersja == 2


class TestOgraniczeniaWartosci:
    def test_parametr_nie_moze_byc_jednoczesnie_kwota_i_data(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        okres = _okres(sesja, lokal, najemca)
        sesja.add(
            ParametrWartosc(
                okres_najmu_id=okres.id,
                klucz="czynsz_podstawowy",
                typ_wartosci=TypWartosci.KWOTA,
                wartosc_kwota=Decimal("100.00"),
                wartosc_waluta="PLN",
                wartosc_rodzaj_kwoty=RodzajKwoty.BRUTTO,
                wartosc_data=date(2026, 5, 1),
                obowiazuje_od=date(2026, 2, 1),
            )
        )
        with pytest.raises(IntegrityError):
            sesja.flush()

    def test_typ_kwoty_wymaga_wypelnionej_kwoty(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        okres = _okres(sesja, lokal, najemca)
        sesja.add(
            ParametrWartosc(
                okres_najmu_id=okres.id,
                klucz="czynsz_podstawowy",
                typ_wartosci=TypWartosci.KWOTA,
                wartosc_waluta="PLN",
                wartosc_rodzaj_kwoty=RodzajKwoty.BRUTTO,
                obowiazuje_od=date(2026, 2, 1),
            )
        )
        with pytest.raises(IntegrityError):
            sesja.flush()

    def test_kwota_netto_bez_stawki_vat_jest_odrzucana(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        """Kwoty netto bez VAT nie da sie zbrutowac, wiec nie jest kwota."""
        okres = _okres(sesja, lokal, najemca)
        sesja.add(
            ParametrWartosc(
                okres_najmu_id=okres.id,
                klucz="czynsz_podstawowy",
                typ_wartosci=TypWartosci.KWOTA,
                wartosc_kwota=Decimal("12500.00"),
                wartosc_waluta="PLN",
                wartosc_rodzaj_kwoty=RodzajKwoty.NETTO,
                obowiazuje_od=date(2026, 2, 1),
            )
        )
        with pytest.raises(IntegrityError):
            sesja.flush()

    def test_kwota_bez_waluty_jest_odrzucana(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        okres = _okres(sesja, lokal, najemca)
        sesja.add(
            ParametrWartosc(
                okres_najmu_id=okres.id,
                klucz="czynsz_podstawowy",
                typ_wartosci=TypWartosci.KWOTA,
                wartosc_kwota=Decimal("100.00"),
                wartosc_waluta=None,
                wartosc_rodzaj_kwoty=RodzajKwoty.BRUTTO,
                obowiazuje_od=date(2026, 2, 1),
            )
        )
        with pytest.raises(IntegrityError):
            sesja.flush()

    def test_okres_obowiazywania_nie_moze_konczyc_sie_przed_poczatkiem(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        okres = _okres(sesja, lokal, najemca)
        sesja.add(
            ParametrWartosc(
                okres_najmu_id=okres.id,
                klucz="powierzchnia",
                typ_wartosci=TypWartosci.LICZBA,
                wartosc_liczba=Decimal("100"),
                obowiazuje_od=date(2026, 5, 1),
                obowiazuje_do=date(2026, 4, 1),
            )
        )
        with pytest.raises(IntegrityError):
            sesja.flush()

    def test_zabezpieczenie_netto_wymaga_vat(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        okres = _okres(sesja, lokal, najemca)
        sesja.add(
            Zabezpieczenie(
                okres_najmu_id=okres.id,
                rodzaj=RodzajZabezpieczenia.KAUCJA,
                wymagana_wartosc=Decimal("50000.00"),
                wymagana_waluta="PLN",
                wymagana_rodzaj_kwoty=RodzajKwoty.NETTO,
            )
        )
        with pytest.raises(IntegrityError):
            sesja.flush()

    def test_miesiac_waloryzacji_poza_zakresem_jest_odrzucany(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        okres = _okres(sesja, lokal, najemca)
        okres.waloryzacja_podlega = True
        okres.waloryzacja_miesiac = 13
        with pytest.raises(IntegrityError):
            sesja.flush()

    def test_dokument_nie_moze_byc_wlasnym_aneksem(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        okres = _okres(sesja, lokal, najemca)
        dokument = Dokument(okres_najmu_id=okres.id, typ=TypDokumentu.UMOWA)
        sesja.add(dokument)
        sesja.flush()

        dokument.dokument_nadrzedny_id = dokument.id
        with pytest.raises(IntegrityError):
            sesja.flush()


class TestLogAudytu:
    def test_wpis_da_sie_dodac(self, sesja: Session) -> None:
        sesja.add(
            LogAudytu(
                operacja=OperacjaAudytu.ZMIANA,
                tabela="budynek",
                rekord_id=1,
                pole="nazwa",
                wartosc_stara="18A",
                wartosc_nowa="18B",
            )
        )
        sesja.flush()
        assert sesja.scalars(select(LogAudytu)).one().pole == "nazwa"

    def test_wpisu_nie_da_sie_zmienic(self, sesja: Session) -> None:
        """Log, ktory da sie poprawic, nie jest dowodem na nic."""
        sesja.add(LogAudytu(operacja=OperacjaAudytu.UTWORZENIE, tabela="budynek", rekord_id=1))
        sesja.flush()

        with pytest.raises(DBAPIError, match="tylko do zapisu"):
            sesja.execute(text("UPDATE log_audytu SET tabela = 'podmieniona'"))

    def test_wpisu_nie_da_sie_usunac(self, sesja: Session) -> None:
        sesja.add(LogAudytu(operacja=OperacjaAudytu.UTWORZENIE, tabela="budynek", rekord_id=1))
        sesja.flush()

        with pytest.raises(DBAPIError, match="tylko do zapisu"):
            sesja.execute(text("DELETE FROM log_audytu"))


class TestIndeksy:
    def test_kluczowe_indeksy_istnieja(self, sesja: Session) -> None:
        """Bez tych indeksow dashboard i kokpit terminow beda skanowac tabele."""
        inspektor = inspect(sesja.connection())
        wymagane = {
            "parametr_wartosc": {"ix_parametr_stan_efektywny", "ix_parametr_do_weryfikacji"},
            "okres_najmu": {"ix_okres_najmu_koniec", "ix_okres_najmu_waloryzacja"},
            "lokal": {"ix_lokal_budynek_status"},
            "zdarzenie": {"uq_zdarzenie_klucz_naturalny", "ix_zdarzenie_otwarte"},
            "zabezpieczenie": {"ix_zabezpieczenie_waznosc"},
            "obowiazek_przegladu": {"ix_przeglad_nastepny_termin"},
            "najemca": {"ix_najemca_nazwa_trgm"},
        }
        for tabela, oczekiwane in wymagane.items():
            istniejace = {i["name"] for i in inspektor.get_indexes(tabela)}
            assert oczekiwane <= istniejace, f"{tabela}: brakuje {oczekiwane - istniejace}"

    def test_indeks_stanu_efektywnego_jest_czesciowy(self, sesja: Session) -> None:
        """Wartosci niezatwierdzone nie wchodza do stanu efektywnego (decyzja D4),
        wiec nie ma powodu, zeby zajmowaly miejsce w tym indeksie.
        """
        definicja = sesja.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_parametr_stan_efektywny'")
        ).scalar_one()
        assert "WHERE" in definicja
        assert "zatwierdzona" in definicja
        assert "DESC" in definicja
