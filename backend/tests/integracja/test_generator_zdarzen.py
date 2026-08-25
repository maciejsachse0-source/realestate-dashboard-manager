"""Generator zdarzen na zywej bazie.

Kryterium akceptacji etapu E3: trzykrotne uruchomienie generatora na tych samych
danych tworzy dokladnie tyle samo zdarzen co jednokrotne.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from najem.domena.slowniki import (
    BazaOkresuNajmu,
    RodzajKwoty,
    RodzajZabezpieczenia,
    StatusOkresuNajmu,
    StatusWeryfikacji,
    StatusZabezpieczenia,
    TypWartosci,
    TypZdarzenia,
)
from najem.modele import (
    Lokal,
    Najemca,
    ObowiazekPrzegladu,
    OkresNajmu,
    ParametrWartosc,
    SkladnikOplaty,
    Zabezpieczenie,
    Zdarzenie,
)
from najem.uslugi.generator_zdarzen import uruchom_generator

pytestmark = pytest.mark.integracja

DZIS = date(2026, 8, 25)


@pytest.fixture
def okres_konczacy_sie_wkrotce(sesja: Session, lokal: Lokal, najemca: Najemca) -> OkresNajmu:
    """Umowa konczaca sie za 20 dni, wiec po wszystkich czterech progach."""
    okres = OkresNajmu(
        lokal_id=lokal.id,
        najemca_id=najemca.id,
        data_zawarcia=date(2026, 1, 15),
        data_przekazania=date(2026, 2, 1),
        bazuje_na_dacie=BazaOkresuNajmu.DATA_PRZEKAZANIA,
        okres_zawarcia_miesiace=7,
        status=StatusOkresuNajmu.AKTYWNA,
    )
    sesja.add(okres)
    sesja.flush()
    return okres


def liczba_zdarzen(sesja: Session) -> int:
    return sesja.scalar(select(func.count()).select_from(Zdarzenie)) or 0


class TestIdempotencja:
    def test_trzy_przebiegi_daja_tyle_samo_zdarzen_co_jeden(
        self, sesja: Session, okres_konczacy_sie_wkrotce: OkresNajmu
    ) -> None:
        """Kryterium akceptacji etapu E3, sprawdzone na bazie, a nie tylko w domenie."""
        pierwszy = uruchom_generator(sesja, DZIS)
        sesja.flush()
        po_pierwszym = liczba_zdarzen(sesja)

        assert pierwszy.zdarzen_dodanych > 0
        assert po_pierwszym == pierwszy.zdarzen_dodanych

        for _ in range(2):
            kolejny = uruchom_generator(sesja, DZIS)
            sesja.flush()
            assert kolejny.zdarzen_dodanych == 0
            assert kolejny.zdarzen_pominietych == kolejny.zdarzen_wyliczonych

        assert liczba_zdarzen(sesja) == po_pierwszym

    def test_kolejny_dzien_dokłada_tylko_nowe_zdarzenia(
        self, sesja: Session, okres_konczacy_sie_wkrotce: OkresNajmu
    ) -> None:
        """Przebieg dzien pozniej nie powiela wczorajszych alertow."""
        uruchom_generator(sesja, DZIS)
        sesja.flush()
        po_pierwszym = liczba_zdarzen(sesja)

        uruchom_generator(sesja, DZIS + timedelta(days=1))
        sesja.flush()
        assert liczba_zdarzen(sesja) == po_pierwszym

    def test_zdarzenie_usuniete_miekko_nie_wraca(
        self, sesja: Session, okres_konczacy_sie_wkrotce: OkresNajmu
    ) -> None:
        """Klucz naturalny nie ma warunku na usunieto_dnia wlasnie po to,
        zeby odrzucony alert nie odradzal sie przy kazdym przebiegu.
        """
        uruchom_generator(sesja, DZIS)
        sesja.flush()
        przed = liczba_zdarzen(sesja)

        pierwsze = sesja.scalars(select(Zdarzenie).limit(1)).one()
        pierwsze.usunieto_dnia = datetime.now(UTC)
        sesja.flush()

        uruchom_generator(sesja, DZIS)
        sesja.flush()
        assert liczba_zdarzen(sesja) == przed


class TestTresc:
    def test_zdarzenia_niosa_lokal_i_encje_zrodlowa(
        self, sesja: Session, okres_konczacy_sie_wkrotce: OkresNajmu, lokal: Lokal
    ) -> None:
        uruchom_generator(sesja, DZIS)
        sesja.flush()

        zdarzenia = sesja.scalars(select(Zdarzenie)).all()
        assert zdarzenia
        for z in zdarzenia:
            assert z.lokal_id == lokal.id
            assert z.encja_typ in {"okres_najmu", "zabezpieczenie", "obowiazek_przegladu"}
            assert z.tresc

    def test_oznaczenie_lokalu_jest_w_tresci(
        self, sesja: Session, okres_konczacy_sie_wkrotce: OkresNajmu, lokal: Lokal
    ) -> None:
        """Pracownik czyta tresc alertu, a nie identyfikator."""
        uruchom_generator(sesja, DZIS)
        sesja.flush()
        tresci = [z.tresc for z in sesja.scalars(select(Zdarzenie)).all()]
        assert any(lokal.oznaczenie in t for t in tresci)


class TestPelnyPortfel:
    def test_umowa_z_kompletem_danych_nie_generuje_alertu_o_niekompletnosci(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        okres = OkresNajmu(
            lokal_id=lokal.id,
            najemca_id=najemca.id,
            data_zawarcia=date(2026, 1, 15),
            data_przekazania=date(2026, 2, 1),
            bazuje_na_dacie=BazaOkresuNajmu.DATA_PRZEKAZANIA,
            okres_zawarcia_miesiace=60,
            status=StatusOkresuNajmu.AKTYWNA,
        )
        sesja.add(okres)
        sesja.flush()

        sesja.add_all(
            [
                ParametrWartosc(
                    okres_najmu_id=okres.id,
                    klucz="czynsz_podstawowy",
                    typ_wartosci=TypWartosci.KWOTA,
                    wartosc_kwota=Decimal("12500.00"),
                    wartosc_waluta="PLN",
                    wartosc_rodzaj_kwoty=RodzajKwoty.NETTO,
                    wartosc_stawka_vat=Decimal("23.00"),
                    obowiazuje_od=date(2026, 2, 1),
                    status_weryfikacji=StatusWeryfikacji.ZATWIERDZONA,
                ),
                ParametrWartosc(
                    okres_najmu_id=okres.id,
                    klucz="powierzchnia",
                    typ_wartosci=TypWartosci.LICZBA,
                    wartosc_liczba=Decimal("128.500000"),
                    obowiazuje_od=date(2026, 2, 1),
                    status_weryfikacji=StatusWeryfikacji.ZATWIERDZONA,
                ),
                SkladnikOplaty(
                    okres_najmu_id=okres.id,
                    nazwa="Czynsz podstawowy",
                    klucz_parametru="czynsz_podstawowy",
                    dzien_platnosci_miesiaca=10,
                ),
                Zabezpieczenie(
                    okres_najmu_id=okres.id,
                    rodzaj=RodzajZabezpieczenia.KAUCJA,
                    status=StatusZabezpieczenia.DOSTARCZONE,
                ),
                Zabezpieczenie(
                    okres_najmu_id=okres.id,
                    rodzaj=RodzajZabezpieczenia.POLISA,
                    status=StatusZabezpieczenia.DOSTARCZONE,
                    data_waznosci=date(2027, 12, 31),
                ),
            ]
        )
        sesja.flush()

        uruchom_generator(sesja, DZIS)
        sesja.flush()

        typy = {z.typ for z in sesja.scalars(select(Zdarzenie)).all()}
        assert TypZdarzenia.PROFIL_NIEKOMPLETNY not in typy

    def test_umowa_bez_protokolu_generuje_alert_i_nie_ma_daty_konca(
        self, sesja: Session, lokal: Lokal, najemca: Najemca
    ) -> None:
        okres = OkresNajmu(
            lokal_id=lokal.id,
            najemca_id=najemca.id,
            data_zawarcia=date(2026, 1, 15),
            data_przekazania=None,
            bazuje_na_dacie=BazaOkresuNajmu.DATA_PRZEKAZANIA,
            okres_zawarcia_miesiace=24,
            status=StatusOkresuNajmu.AKTYWNA,
        )
        sesja.add(okres)
        sesja.flush()

        uruchom_generator(sesja, DZIS)
        sesja.flush()

        typy = {z.typ for z in sesja.scalars(select(Zdarzenie)).all()}
        assert TypZdarzenia.BRAK_PROTOKOLU_PRZEKAZANIA in typy
        assert TypZdarzenia.KONIEC_UMOWY_SIE_ZBLIZA not in typy

    def test_przeglad_przeterminowany_z_bazy(
        self, sesja: Session, okres_konczacy_sie_wkrotce: OkresNajmu, lokal: Lokal
    ) -> None:
        sesja.add(
            ObowiazekPrzegladu(
                lokal_id=lokal.id,
                element="gaśnice",
                kto_obciazany="najemca",
                czestotliwosc_miesiace=12,
                ostatni_przeglad_data=date(2025, 6, 1),
                nastepny_przeglad_data=date(2026, 6, 1),
            )
        )
        sesja.flush()

        uruchom_generator(sesja, DZIS)
        sesja.flush()

        zdarzenia = sesja.scalars(
            select(Zdarzenie).where(Zdarzenie.typ == TypZdarzenia.PRZEGLAD_PRZETERMINOWANY)
        ).all()
        assert len(zdarzenia) == 1
        assert "gaśnice" in zdarzenia[0].tresc

    def test_pusta_baza_nie_wywala_generatora(self, sesja: Session) -> None:
        wynik = uruchom_generator(sesja, DZIS)
        assert wynik.umow_sprawdzonych == 0
        assert wynik.zdarzen_dodanych == 0
