"""Dashboard, stan efektywny i kokpit terminów przez HTTP.

Sprawdzamy pełną pionową ścieżkę: żądanie → reguły domenowe → baza → odpowiedź.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from najem.domena.slowniki import (
    BazaOkresuNajmu,
    RodzajKwoty,
    StatusOkresuNajmu,
    StatusWeryfikacji,
    TypWartosci,
)
from najem.modele import Budynek, Lokal, Najemca, OkresNajmu, ParametrWartosc

pytestmark = pytest.mark.integracja

DZIS = date(2026, 8, 25)


@pytest.fixture
def umowa(baza: Session, lokal_api: Lokal, najemca_api: Najemca) -> OkresNajmu:
    okres = OkresNajmu(
        lokal_id=lokal_api.id,
        najemca_id=najemca_api.id,
        data_zawarcia=date(2026, 1, 15),
        data_przekazania=date(2026, 2, 1),
        bazuje_na_dacie=BazaOkresuNajmu.DATA_PRZEKAZANIA,
        okres_zawarcia_miesiace=24,
        data_zakonczenia_planowana=date(2028, 1, 31),
        status=StatusOkresuNajmu.AKTYWNA,
    )
    baza.add(okres)
    baza.flush()
    return okres


def dodaj_czynsz(
    baza: Session,
    okres: OkresNajmu,
    kwota: str,
    od: date,
    status: StatusWeryfikacji = StatusWeryfikacji.ZATWIERDZONA,
) -> ParametrWartosc:
    p = ParametrWartosc(
        okres_najmu_id=okres.id,
        klucz="czynsz_podstawowy",
        typ_wartosci=TypWartosci.KWOTA,
        wartosc_kwota=Decimal(kwota),
        wartosc_waluta="PLN",
        wartosc_rodzaj_kwoty=RodzajKwoty.NETTO,
        wartosc_stawka_vat=Decimal("23.00"),
        obowiazuje_od=od,
        status_weryfikacji=status,
    )
    baza.add(p)
    baza.flush()
    return p


class TestListaLokali:
    def test_pusty_wynik_ma_poprawny_ksztalt(self, klient: TestClient) -> None:
        dane = klient.get("/api/v1/lokale").json()
        assert dane["pozycje"] == []
        assert dane["wszystkich"] == 0

    def test_lokal_bez_umowy(self, klient: TestClient, lokal_api: Lokal) -> None:
        wiersz = klient.get("/api/v1/lokale").json()["pozycje"][0]
        assert wiersz["oznaczenie"] == "18A/12"
        assert wiersz["okres_najmu_id"] is None
        assert wiersz["najemca_nazwa"] is None

    def test_lokal_z_umowa_i_czynszem(
        self, klient: TestClient, baza: Session, umowa: OkresNajmu
    ) -> None:
        dodaj_czynsz(baza, umowa, "12500.00", date(2026, 2, 1))
        wiersz = klient.get(f"/api/v1/lokale?na_dzien={DZIS}").json()["pozycje"][0]

        assert wiersz["najemca_nazwa"] == "Przykładowa Spółka z o.o."
        assert wiersz["status_umowy"] == "aktywna"
        assert wiersz["data_zakonczenia"] == "2028-01-31"

    def test_czynsz_wraca_jako_tekst_bez_utraty_groszy(
        self, klient: TestClient, baza: Session, umowa: OkresNajmu
    ) -> None:
        """JSON nie ma typu dziesiętnego. Kwota jako liczba gubiłaby grosze."""
        dodaj_czynsz(baza, umowa, "12345.67", date(2026, 2, 1))
        wiersz = klient.get(f"/api/v1/lokale?na_dzien={DZIS}").json()["pozycje"][0]
        assert wiersz["czynsz"] == "12345.67"
        assert isinstance(wiersz["czynsz"], str)
        assert wiersz["czynsz_waluta"] == "PLN"
        assert wiersz["czynsz_rodzaj"] == "netto"

    def test_czynsz_niezatwierdzony_nie_pokazuje_sie(
        self, klient: TestClient, baza: Session, umowa: OkresNajmu
    ) -> None:
        """Decyzja D4 działa przez cały stos, aż do wiersza tabeli."""
        dodaj_czynsz(
            baza, umowa, "12500.00", date(2026, 2, 1), status=StatusWeryfikacji.ZAPROPONOWANA
        )
        wiersz = klient.get(f"/api/v1/lokale?na_dzien={DZIS}").json()["pozycje"][0]
        assert wiersz["czynsz"] is None
        assert "czynsz_podstawowy" in wiersz["brakujace_pola"]

    def test_brak_protokolu_daje_powod_zamiast_daty(
        self, klient: TestClient, baza: Session, lokal_api: Lokal, najemca_api: Najemca
    ) -> None:
        """Reguła R1 aż do interfejsu: 'nieustalona' z powodem, nie pusta komórka."""
        baza.add(
            OkresNajmu(
                lokal_id=lokal_api.id,
                najemca_id=najemca_api.id,
                data_zawarcia=date(2026, 1, 15),
                data_przekazania=None,
                bazuje_na_dacie=BazaOkresuNajmu.DATA_PRZEKAZANIA,
                okres_zawarcia_miesiace=24,
                status=StatusOkresuNajmu.AKTYWNA,
            )
        )
        baza.flush()

        wiersz = klient.get("/api/v1/lokale").json()["pozycje"][0]
        assert wiersz["data_zakonczenia"] is None
        assert "protokołu przekazania" in wiersz["powod_braku_daty_zakonczenia"]

    def test_kompletnosc_i_braki(
        self, klient: TestClient, baza: Session, umowa: OkresNajmu
    ) -> None:
        dodaj_czynsz(baza, umowa, "12500.00", date(2026, 2, 1))
        wiersz = klient.get(f"/api/v1/lokale?na_dzien={DZIS}").json()["pozycje"][0]
        assert 0 < wiersz["kompletnosc_procent"] < 100
        assert "status_polisy" in wiersz["brakujace_pola"]


class TestFiltryISortowanie:
    def test_filtr_po_budynku(
        self, klient: TestClient, baza: Session, lokal_api: Lokal, budynek_api: Budynek
    ) -> None:
        inny = Budynek(nazwa="20C")
        baza.add(inny)
        baza.flush()

        assert klient.get(f"/api/v1/lokale?budynek_id={budynek_api.id}").json()["wszystkich"] == 1
        assert klient.get(f"/api/v1/lokale?budynek_id={inny.id}").json()["wszystkich"] == 0

    def test_filtr_po_zakresie_konca_umowy(self, klient: TestClient, umowa: OkresNajmu) -> None:
        """Pytanie z sekcji 1.1 koncepcji: 'umowy kończące się w Q2 2027'."""
        w_zakresie = klient.get("/api/v1/lokale?koniec_od=2028-01-01&koniec_do=2028-12-31").json()
        poza = klient.get("/api/v1/lokale?koniec_od=2027-04-01&koniec_do=2027-06-30").json()
        assert w_zakresie["wszystkich"] == 1
        assert poza["wszystkich"] == 0

    def test_wyszukiwanie_po_najemcy(self, klient: TestClient, umowa: OkresNajmu) -> None:
        assert klient.get("/api/v1/lokale?szukaj=Przykładowa").json()["wszystkich"] == 1
        assert klient.get("/api/v1/lokale?szukaj=NieMaTakiego").json()["wszystkich"] == 0

    def test_wyszukiwanie_po_oznaczeniu(self, klient: TestClient, lokal_api: Lokal) -> None:
        assert klient.get("/api/v1/lokale?szukaj=18A/12").json()["wszystkich"] == 1

    def test_nieznana_kolumna_sortowania_jest_odrzucana(self, klient: TestClient) -> None:
        """Biała lista kolumn. Do ORDER BY nie trafia dowolny tekst."""
        odpowiedz = klient.get("/api/v1/lokale?sortuj=DROP+TABLE")
        assert odpowiedz.status_code == 422
        assert "Dostępne" in odpowiedz.json()["detail"]

    def test_paginacja(self, klient: TestClient, lokal_api: Lokal) -> None:
        dane = klient.get("/api/v1/lokale?limit=1&offset=0").json()
        assert dane["limit"] == 1
        assert len(dane["pozycje"]) <= 1

    def test_limit_ponad_maksimum_jest_odrzucany(self, klient: TestClient) -> None:
        assert klient.get("/api/v1/lokale?limit=5000").status_code == 422


class TestStanNaDzien:
    def test_stan_pokazuje_wartosc_z_danego_dnia(
        self, klient: TestClient, baza: Session, umowa: OkresNajmu, lokal_api: Lokal
    ) -> None:
        """Decyzja D2 przez cały stos: 'jaka była stawka w maju 2026'."""
        dodaj_czynsz(baza, umowa, "12500.00", date(2026, 2, 1))
        dodaj_czynsz(baza, umowa, "13000.00", date(2027, 3, 1))

        maj = klient.get(f"/api/v1/lokale/{lokal_api.id}/stan?na_dzien=2026-05-15").json()
        pozniej = klient.get(f"/api/v1/lokale/{lokal_api.id}/stan?na_dzien=2027-06-01").json()

        assert maj["parametry"]["czynsz_podstawowy"]["wartosc"] == "12500.00"
        assert pozniej["parametry"]["czynsz_podstawowy"]["wartosc"] == "13000.00"

    def test_stan_niesie_slad_do_dokumentu(
        self, klient: TestClient, baza: Session, umowa: OkresNajmu, lokal_api: Lokal
    ) -> None:
        """Każda wartość z dokumentu jest klikalna do źródła (koncepcja 7.2)."""
        parametr = dodaj_czynsz(baza, umowa, "12500.00", date(2026, 2, 1))
        parametr.zrodlo_strona = 3
        parametr.zrodlo_paragraf = "par. 5 ust. 1"
        baza.flush()

        pozycja = klient.get(f"/api/v1/lokale/{lokal_api.id}/stan?na_dzien={DZIS}").json()[
            "parametry"
        ]["czynsz_podstawowy"]
        assert pozycja["zrodlo_strona"] == 3
        assert pozycja["zrodlo_paragraf"] == "par. 5 ust. 1"
        assert pozycja["status_weryfikacji"] == "zatwierdzona"

    def test_lokal_bez_umowy_ma_zerowa_kompletnosc(
        self, klient: TestClient, lokal_api: Lokal
    ) -> None:
        dane = klient.get(f"/api/v1/lokale/{lokal_api.id}/stan").json()
        assert dane["okres_najmu_id"] is None
        assert dane["kompletnosc_procent"] == 0
        assert "bieżącej umowy" in dane["powod_braku_daty_zakonczenia"]

    def test_nieistniejacy_lokal_daje_404(self, klient: TestClient) -> None:
        assert klient.get("/api/v1/lokale/999999/stan").status_code == 404


class TestKokpitTerminow:
    def test_generator_i_lista_zdarzen(
        self, klient: TestClient, baza: Session, lokal_api: Lokal, najemca_api: Najemca
    ) -> None:
        baza.add(
            OkresNajmu(
                lokal_id=lokal_api.id,
                najemca_id=najemca_api.id,
                data_przekazania=date(2026, 2, 1),
                bazuje_na_dacie=BazaOkresuNajmu.DATA_PRZEKAZANIA,
                okres_zawarcia_miesiace=7,
                status=StatusOkresuNajmu.AKTYWNA,
            )
        )
        baza.flush()

        przebieg = klient.post(f"/api/v1/zdarzenia/generuj?na_dzien={DZIS}")
        assert przebieg.status_code == 200
        assert przebieg.json()["zdarzen_dodanych"] > 0

        lista = klient.get("/api/v1/zdarzenia").json()
        assert lista["wszystkich"] > 0
        assert lista["pozycje"][0]["status"] == "otwarte"

    def test_krytyczne_sa_na_gorze_listy(
        self, klient: TestClient, baza: Session, lokal_api: Lokal, najemca_api: Najemca
    ) -> None:
        """Kokpit grupuje według pilności (koncepcja, sekcja 7.3)."""
        baza.add(
            OkresNajmu(
                lokal_id=lokal_api.id,
                najemca_id=najemca_api.id,
                data_przekazania=date(2026, 2, 1),
                bazuje_na_dacie=BazaOkresuNajmu.DATA_PRZEKAZANIA,
                okres_zawarcia_miesiace=7,
                status=StatusOkresuNajmu.AKTYWNA,
            )
        )
        baza.flush()
        klient.post(f"/api/v1/zdarzenia/generuj?na_dzien={DZIS}")

        wagi = [z["waga"] for z in klient.get("/api/v1/zdarzenia").json()["pozycje"]]
        if "krytyczne" in wagi:
            assert wagi[0] == "krytyczne"

    def test_obsluzenie_zdarzenia(
        self, klient: TestClient, baza: Session, lokal_api: Lokal, najemca_api: Najemca
    ) -> None:
        baza.add(
            OkresNajmu(
                lokal_id=lokal_api.id,
                najemca_id=najemca_api.id,
                data_przekazania=date(2026, 2, 1),
                bazuje_na_dacie=BazaOkresuNajmu.DATA_PRZEKAZANIA,
                okres_zawarcia_miesiace=7,
                status=StatusOkresuNajmu.AKTYWNA,
            )
        )
        baza.flush()
        klient.post(f"/api/v1/zdarzenia/generuj?na_dzien={DZIS}")

        pierwsze = klient.get("/api/v1/zdarzenia").json()["pozycje"][0]
        odpowiedz = klient.post(
            f"/api/v1/zdarzenia/{pierwsze['id']}/obsluzone",
            json={"notatka": "Zadzwoniłem do najemcy."},
        )
        assert odpowiedz.status_code == 200
        assert odpowiedz.json()["status"] == "obsluzone"
        assert odpowiedz.json()["notatka"] == "Zadzwoniłem do najemcy."

    def test_odroczenie_w_przeszlosc_jest_odrzucane(
        self, klient: TestClient, baza: Session, lokal_api: Lokal, najemca_api: Najemca
    ) -> None:
        """Odroczenie na wczoraj niczego nie załatwia."""
        baza.add(
            OkresNajmu(
                lokal_id=lokal_api.id,
                najemca_id=najemca_api.id,
                data_przekazania=date(2026, 2, 1),
                bazuje_na_dacie=BazaOkresuNajmu.DATA_PRZEKAZANIA,
                okres_zawarcia_miesiace=7,
                status=StatusOkresuNajmu.AKTYWNA,
            )
        )
        baza.flush()
        klient.post(f"/api/v1/zdarzenia/generuj?na_dzien={DZIS}")

        pierwsze = klient.get("/api/v1/zdarzenia").json()["pozycje"][0]
        wczoraj = (date.today() - timedelta(days=1)).isoformat()
        odpowiedz = klient.post(
            f"/api/v1/zdarzenia/{pierwsze['id']}/odroczenie", json={"odroczone_do": wczoraj}
        )
        assert odpowiedz.status_code == 422

    def test_licznik_zdarzen_na_liscie_lokali(
        self, klient: TestClient, baza: Session, lokal_api: Lokal, najemca_api: Najemca
    ) -> None:
        """Licznik alertów u góry dashboardu (koncepcja, sekcja 7.1)."""
        baza.add(
            OkresNajmu(
                lokal_id=lokal_api.id,
                najemca_id=najemca_api.id,
                data_przekazania=date(2026, 2, 1),
                bazuje_na_dacie=BazaOkresuNajmu.DATA_PRZEKAZANIA,
                okres_zawarcia_miesiace=7,
                status=StatusOkresuNajmu.AKTYWNA,
            )
        )
        baza.flush()
        klient.post(f"/api/v1/zdarzenia/generuj?na_dzien={DZIS}")

        wiersz = klient.get("/api/v1/lokale").json()["pozycje"][0]
        assert wiersz["zdarzen_otwartych"] > 0
