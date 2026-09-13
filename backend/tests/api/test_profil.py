"""Endpointy dokładane w etapie E6: lista użytkowników i zmiana zabezpieczenia.

Plus pełna ścieżka użytkownika: od budynku po alert. Ten ostatni test jest
najbliższy temu, co robi człowiek pierwszego dnia z programem.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from najem.modele import Lokal, Najemca

pytestmark = pytest.mark.integracja

DZIS = date(2026, 8, 25)


class TestZmianaZabezpieczenia:
    @pytest.fixture
    def zabezpieczenie(
        self, klient: TestClient, lokal_api: Lokal, najemca_api: Najemca
    ) -> dict[str, object]:
        okres: dict[str, object] = klient.post(
            "/api/v1/okresy-najmu",
            json={
                "lokal_id": lokal_api.id,
                "najemca_id": najemca_api.id,
                "data_przekazania": "2026-02-01",
                "bazuje_na_dacie": "data_przekazania",
                "okres_zawarcia_miesiace": 24,
            },
        ).json()
        odpowiedz: dict[str, object] = klient.post(
            f"/api/v1/okresy-najmu/{okres['id']}/zabezpieczenia",
            json={"rodzaj": "kaucja", "status": "wymagane", "data_wymagalnosci": "2026-02-15"},
        ).json()
        return odpowiedz

    def test_odnotowanie_wplaty(
        self, klient: TestClient, zabezpieczenie: dict[str, object]
    ) -> None:
        odpowiedz = klient.put(
            f"/api/v1/zabezpieczenia/{zabezpieczenie['id']}",
            json={
                "rodzaj": "kaucja",
                "status": "dostarczone",
                "data_wymagalnosci": "2026-02-15",
                "data_dostarczenia": "2026-02-12",
                "wersja": zabezpieczenie["wersja"],
            },
        )
        assert odpowiedz.status_code == 200
        assert odpowiedz.json()["status"] == "dostarczone"

    def test_niedozwolone_przejscie_jest_odrzucane(
        self, klient: TestClient, zabezpieczenie: dict[str, object]
    ) -> None:
        """Reguła R4: nie da się zwrócić czegoś, czego nie dostarczono."""
        odpowiedz = klient.put(
            f"/api/v1/zabezpieczenia/{zabezpieczenie['id']}",
            json={
                "rodzaj": "kaucja",
                "status": "zwrocone",
                "wersja": zabezpieczenie["wersja"],
            },
        )
        assert odpowiedz.status_code == 422
        assert "wymagane" in odpowiedz.json()["detail"]

    def test_stara_wersja_daje_konflikt(
        self, klient: TestClient, zabezpieczenie: dict[str, object]
    ) -> None:
        tresc = {
            "rodzaj": "kaucja",
            "status": "dostarczone",
            "wersja": zabezpieczenie["wersja"],
        }
        assert (
            klient.put(f"/api/v1/zabezpieczenia/{zabezpieczenie['id']}", json=tresc).status_code
            == 200
        )
        assert (
            klient.put(f"/api/v1/zabezpieczenia/{zabezpieczenie['id']}", json=tresc).status_code
            == 409
        )


class TestPelnaSciezka:
    def test_od_budynku_do_alertu(self, klient: TestClient) -> None:
        """To robi człowiek pierwszego dnia z programem.

        Test przechodzi całą drogę i sprawdza rzecz najważniejszą: wartość
        niezatwierdzona NIE pokazuje się jako czynsz, a po zatwierdzeniu — tak.
        """
        budynek = klient.post("/api/v1/budynki", json={"nazwa": "30X", "aktywny": True}).json()

        lokal = klient.post(
            "/api/v1/lokale",
            json={
                "budynek_id": budynek["id"],
                "oznaczenie": "30X/01",
                "typ": "biurowy",
                "powierzchnia_ewidencyjna": 50,
            },
        ).json()

        najemca = klient.post(
            "/api/v1/najemcy", json={"nazwa_pelna": "Firma Testowa sp. z o.o."}
        ).json()

        okres = klient.post(
            "/api/v1/okresy-najmu",
            json={
                "lokal_id": lokal["id"],
                "najemca_id": najemca["id"],
                "data_przekazania": "2026-02-01",
                "bazuje_na_dacie": "data_przekazania",
                "okres_zawarcia_miesiace": 36,
            },
        ).json()
        assert okres["data_zakonczenia_planowana"] == "2029-01-31"

        parametr = klient.post(
            f"/api/v1/okresy-najmu/{okres['id']}/parametry",
            json={
                "klucz": "czynsz_podstawowy",
                "typ_wartosci": "kwota",
                "wartosc_kwota": 7400,
                "wartosc_waluta": "PLN",
                "wartosc_rodzaj_kwoty": "netto",
                "wartosc_stawka_vat": 23,
                "obowiazuje_od": "2026-02-01",
            },
        ).json()
        assert parametr["status_weryfikacji"] == "zaproponowana"

        przed = klient.get(f"/api/v1/lokale/{lokal['id']}/stan").json()
        assert "czynsz_podstawowy" not in przed["parametry"]

        klient.post(f"/api/v1/parametry/{parametr['id']}/decyzja", json={"status": "zatwierdzona"})

        po = klient.get(f"/api/v1/lokale/{lokal['id']}/stan").json()
        assert po["parametry"]["czynsz_podstawowy"]["wartosc"] == "7400.00"

    def test_przeglad_przeterminowany_od_razu_po_dodaniu(
        self, klient: TestClient, lokal_api: Lokal
    ) -> None:
        """Przegląd sprzed pięciu lat z częstotliwością roczną jest przeterminowany
        w chwili wprowadzenia, a nie dopiero po nocnym przebiegu generatora.
        """
        przeglad = klient.post(
            "/api/v1/przeglady",
            json={
                "lokal_id": lokal_api.id,
                "element": "gaśnice",
                "kto_obciazany": "najemca",
                "czestotliwosc_miesiace": 12,
                "ostatni_przeglad_data": "2021-05-01",
            },
        ).json()
        assert przeglad["status"] == "przeterminowany"
        assert przeglad["nastepny_przeglad_data"] == "2022-05-01"

    def test_protokol_przesuwa_termin_do_przodu(self, klient: TestClient, lokal_api: Lokal) -> None:
        przeglad = klient.post(
            "/api/v1/przeglady",
            json={
                "lokal_id": lokal_api.id,
                "element": "brama",
                "kto_obciazany": "wynajmujacy",
                "czestotliwosc_miesiace": 12,
                "ostatni_przeglad_data": "2021-05-01",
            },
        ).json()

        po = klient.post(
            f"/api/v1/przeglady/{przeglad['id']}/protokol?data_protokolu=2026-08-01"
        ).json()
        assert po["ostatni_przeglad_data"] == "2026-08-01"
        assert po["nastepny_przeglad_data"] == "2027-08-01"
        assert po["status"] != "przeterminowany"
