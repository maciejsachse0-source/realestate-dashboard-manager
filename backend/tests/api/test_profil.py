"""Endpointy dokładane w etapie E6: lista użytkowników i zmiana zabezpieczenia.

Plus pełna ścieżka użytkownika: od budynku po alert. Ten ostatni test jest
najbliższy temu, co robi człowiek pierwszego dnia z programem.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from najem.domena.slowniki import RolaUzytkownika
from najem.modele import Lokal, Najemca
from tests.api.conftest import zaloguj_jako

pytestmark = pytest.mark.integracja

DZIS = date(2026, 8, 25)


class TestListaUzytkownikow:
    def test_operator_widzi_liste(self, klient: TestClient, baza: Session) -> None:
        uzytkownik = zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        odpowiedz = klient.get("/api/v1/uzytkownicy")
        assert odpowiedz.status_code == 200
        assert any(u["id"] == uzytkownik.id for u in odpowiedz.json())

    def test_podglad_nie_widzi_listy(self, klient_podglad: TestClient) -> None:
        """Przypisywanie zadań to praca operatora, nie osoby z podglądem."""
        assert klient_podglad.get("/api/v1/uzytkownicy").status_code == 403

    def test_lista_nie_zdradza_danych_konta(self, klient: TestClient, baza: Session) -> None:
        """Lista wyboru w kokpicie nie jest miejscem na e-mail ani datę logowania."""
        zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        pozycja = klient.get("/api/v1/uzytkownicy").json()[0]
        assert set(pozycja) == {"id", "imie_nazwisko", "rola"}

    def test_konto_nieaktywne_nie_pojawia_sie(self, klient: TestClient, baza: Session) -> None:
        uzytkownik = zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        widoczne = klient.get("/api/v1/uzytkownicy").json()
        assert any(u["id"] == uzytkownik.id for u in widoczne)

        uzytkownik.aktywny = False
        baza.flush()
        # Konto nieaktywne traci też sesję, więc sprawdzamy z innego konta.
        klient.cookies.clear()
        zaloguj_jako(klient, baza, RolaUzytkownika.ZARZADCA)
        assert all(u["id"] != uzytkownik.id for u in klient.get("/api/v1/uzytkownicy").json())


class TestZmianaZabezpieczenia:
    @pytest.fixture
    def zabezpieczenie(
        self, klient_zarzadca: TestClient, lokal_api: Lokal, najemca_api: Najemca
    ) -> dict[str, object]:
        okres: dict[str, object] = klient_zarzadca.post(
            "/api/v1/okresy-najmu",
            json={
                "lokal_id": lokal_api.id,
                "najemca_id": najemca_api.id,
                "data_przekazania": "2026-02-01",
                "bazuje_na_dacie": "data_przekazania",
                "okres_zawarcia_miesiace": 24,
            },
        ).json()
        odpowiedz: dict[str, object] = klient_zarzadca.post(
            f"/api/v1/okresy-najmu/{okres['id']}/zabezpieczenia",
            json={"rodzaj": "kaucja", "status": "wymagane", "data_wymagalnosci": "2026-02-15"},
        ).json()
        return odpowiedz

    def test_odnotowanie_wplaty(
        self, klient_zarzadca: TestClient, zabezpieczenie: dict[str, object]
    ) -> None:
        odpowiedz = klient_zarzadca.put(
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
        self, klient_zarzadca: TestClient, zabezpieczenie: dict[str, object]
    ) -> None:
        """Reguła R4: nie da się zwrócić czegoś, czego nie dostarczono."""
        odpowiedz = klient_zarzadca.put(
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
        self, klient_zarzadca: TestClient, zabezpieczenie: dict[str, object]
    ) -> None:
        tresc = {
            "rodzaj": "kaucja",
            "status": "dostarczone",
            "wersja": zabezpieczenie["wersja"],
        }
        assert (
            klient_zarzadca.put(
                f"/api/v1/zabezpieczenia/{zabezpieczenie['id']}", json=tresc
            ).status_code
            == 200
        )
        assert (
            klient_zarzadca.put(
                f"/api/v1/zabezpieczenia/{zabezpieczenie['id']}", json=tresc
            ).status_code
            == 409
        )

    def test_podglad_nie_moze_zmienic(
        self, klient: TestClient, baza: Session, zabezpieczenie: dict[str, object]
    ) -> None:
        klient.cookies.clear()
        zaloguj_jako(klient, baza, RolaUzytkownika.PODGLAD)
        assert (
            klient.put(
                f"/api/v1/zabezpieczenia/{zabezpieczenie['id']}",
                json={"rodzaj": "kaucja", "status": "dostarczone", "wersja": 1},
            ).status_code
            == 403
        )


class TestPelnaSciezka:
    def test_od_budynku_do_alertu(self, klient_admin: TestClient) -> None:
        """To robi człowiek pierwszego dnia z programem.

        Test przechodzi całą drogę i sprawdza rzecz najważniejszą: wartość
        niezatwierdzona NIE pokazuje się jako czynsz, a po zatwierdzeniu — tak.
        """
        budynek = klient_admin.post(
            "/api/v1/budynki", json={"nazwa": "30X", "aktywny": True}
        ).json()

        lokal = klient_admin.post(
            "/api/v1/lokale",
            json={
                "budynek_id": budynek["id"],
                "oznaczenie": "30X/01",
                "typ": "biurowy",
                "powierzchnia_ewidencyjna": 50,
            },
        ).json()

        najemca = klient_admin.post(
            "/api/v1/najemcy", json={"nazwa_pelna": "Firma Testowa sp. z o.o."}
        ).json()

        okres = klient_admin.post(
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

        parametr = klient_admin.post(
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

        przed = klient_admin.get(f"/api/v1/lokale/{lokal['id']}/stan").json()
        assert "czynsz_podstawowy" not in przed["parametry"]

        klient_admin.post(
            f"/api/v1/parametry/{parametr['id']}/decyzja", json={"status": "zatwierdzona"}
        )

        po = klient_admin.get(f"/api/v1/lokale/{lokal['id']}/stan").json()
        assert po["parametry"]["czynsz_podstawowy"]["wartosc"] == "7400.00"

    def test_przeglad_przeterminowany_od_razu_po_dodaniu(
        self, klient_zarzadca: TestClient, lokal_api: Lokal
    ) -> None:
        """Przegląd sprzed pięciu lat z częstotliwością roczną jest przeterminowany
        w chwili wprowadzenia, a nie dopiero po nocnym przebiegu generatora.
        """
        przeglad = klient_zarzadca.post(
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

    def test_protokol_przesuwa_termin_do_przodu(
        self, klient_zarzadca: TestClient, lokal_api: Lokal
    ) -> None:
        przeglad = klient_zarzadca.post(
            "/api/v1/przeglady",
            json={
                "lokal_id": lokal_api.id,
                "element": "brama",
                "kto_obciazany": "wynajmujacy",
                "czestotliwosc_miesiace": 12,
                "ostatni_przeglad_data": "2021-05-01",
            },
        ).json()

        po = klient_zarzadca.post(
            f"/api/v1/przeglady/{przeglad['id']}/protokol?data_protokolu=2026-08-01"
        ).json()
        assert po["ostatni_przeglad_data"] == "2026-08-01"
        assert po["nastepny_przeglad_data"] == "2027-08-01"
        assert po["status"] != "przeterminowany"
