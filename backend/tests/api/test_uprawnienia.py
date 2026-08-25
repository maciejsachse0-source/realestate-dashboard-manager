"""Testy autoryzacji per rola.

Kryterium akceptacji etapu E4: rola `podglad` NIE MOŻE modyfikować danych.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from najem.domena.slowniki import RolaUzytkownika
from najem.modele import Budynek, Lokal
from tests.api.conftest import HASLO, zaloguj_jako

pytestmark = pytest.mark.integracja

NOWY_BUDYNEK = {"nazwa": "20C", "adres": "ul. Nowa 20C", "aktywny": True}


class TestBezZalogowania:
    def test_lista_wymaga_zalogowania(self, klient: TestClient) -> None:
        assert klient.get("/api/v1/budynki").status_code == 401

    def test_zapis_wymaga_zalogowania(self, klient: TestClient) -> None:
        assert klient.post("/api/v1/budynki", json=NOWY_BUDYNEK).status_code == 401

    def test_wymyslone_ciasteczko_nie_daje_dostepu(self, klient: TestClient) -> None:
        klient.cookies.set("najem_sesja", "cokolwiek")
        assert klient.get("/api/v1/budynki").status_code == 401

    def test_health_dziala_bez_logowania(self, klient: TestClient) -> None:
        """Diagnostyka musi odpowiadać także wtedy, gdy nikt się nie zalogował."""
        assert klient.get("/api/v1/health").status_code == 200


class TestRolaPodglad:
    """Sedno kryterium akceptacji E4."""

    def test_moze_czytac_liste(self, klient_podglad: TestClient) -> None:
        assert klient_podglad.get("/api/v1/budynki").status_code == 200

    def test_moze_czytac_lokale(self, klient_podglad: TestClient, lokal_api: Lokal) -> None:
        assert klient_podglad.get("/api/v1/lokale").status_code == 200

    def test_nie_moze_dodac_budynku(self, klient_podglad: TestClient) -> None:
        odpowiedz = klient_podglad.post("/api/v1/budynki", json=NOWY_BUDYNEK)
        assert odpowiedz.status_code == 403
        assert "administrator" in odpowiedz.json()["detail"]

    def test_nie_moze_zmienic_budynku(
        self, klient_podglad: TestClient, budynek_api: Budynek
    ) -> None:
        assert (
            klient_podglad.put(f"/api/v1/budynki/{budynek_api.id}", json=NOWY_BUDYNEK).status_code
            == 403
        )

    def test_nie_moze_usunac_budynku(
        self, klient_podglad: TestClient, budynek_api: Budynek
    ) -> None:
        assert klient_podglad.delete(f"/api/v1/budynki/{budynek_api.id}").status_code == 403

    def test_nie_moze_dodac_lokalu(self, klient_podglad: TestClient, budynek_api: Budynek) -> None:
        odpowiedz = klient_podglad.post(
            "/api/v1/lokale",
            json={"budynek_id": budynek_api.id, "oznaczenie": "18A/99", "typ": "biurowy"},
        )
        assert odpowiedz.status_code == 403

    def test_nie_moze_dodac_najemcy(self, klient_podglad: TestClient) -> None:
        assert (
            klient_podglad.post(
                "/api/v1/najemcy", json={"nazwa_pelna": "Podszywacz sp. z o.o."}
            ).status_code
            == 403
        )

    def test_nie_moze_usunac_najemcy(self, klient_podglad: TestClient, najemca_api) -> None:  # type: ignore[no-untyped-def]
        assert klient_podglad.delete(f"/api/v1/najemcy/{najemca_api.id}").status_code == 403


class TestRolaZarzadca:
    def test_moze_dodac_lokal(self, klient_zarzadca: TestClient, budynek_api: Budynek) -> None:
        odpowiedz = klient_zarzadca.post(
            "/api/v1/lokale",
            json={"budynek_id": budynek_api.id, "oznaczenie": "18A/77", "typ": "biurowy"},
        )
        assert odpowiedz.status_code == 201
        assert odpowiedz.json()["oznaczenie"] == "18A/77"

    def test_moze_dodac_najemce(self, klient_zarzadca: TestClient) -> None:
        odpowiedz = klient_zarzadca.post(
            "/api/v1/najemcy", json={"nazwa_pelna": "Nowa Spółka z o.o.", "nip": "1234563218"}
        )
        assert odpowiedz.status_code == 201

    def test_nie_moze_dodac_budynku(self, klient_zarzadca: TestClient) -> None:
        """Kartoteka budynków należy do administratora (koncepcja, sekcja 7.9)."""
        assert klient_zarzadca.post("/api/v1/budynki", json=NOWY_BUDYNEK).status_code == 403


class TestRolaAdministrator:
    def test_moze_wszystko_co_nizsze_role(self, klient_admin: TestClient) -> None:
        assert klient_admin.post("/api/v1/budynki", json=NOWY_BUDYNEK).status_code == 201
        assert klient_admin.get("/api/v1/budynki").status_code == 200
        assert (
            klient_admin.post(
                "/api/v1/najemcy", json={"nazwa_pelna": "Spółka Administratora"}
            ).status_code
            == 201
        )


class TestLogowanieHttp:
    def test_pelny_cykl_logowania(self, klient: TestClient, baza: Session) -> None:
        uzytkownik = zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        klient.cookies.clear()

        odpowiedz = klient.post(
            "/api/v1/auth/logowanie", json={"login": uzytkownik.login, "haslo": HASLO}
        )
        assert odpowiedz.status_code == 200
        assert odpowiedz.json()["rola"] == "operator"

        ja = klient.get("/api/v1/auth/ja")
        assert ja.status_code == 200
        assert ja.json()["login"] == uzytkownik.login

        assert klient.post("/api/v1/auth/wylogowanie").status_code == 204
        klient.cookies.clear()
        assert klient.get("/api/v1/auth/ja").status_code == 401

    def test_ciasteczko_jest_httponly(self, klient: TestClient, baza: Session) -> None:
        """Skrypt na stronie nie może odczytać tokenu sesji."""
        uzytkownik = zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        klient.cookies.clear()
        odpowiedz = klient.post(
            "/api/v1/auth/logowanie", json={"login": uzytkownik.login, "haslo": HASLO}
        )
        naglowek = odpowiedz.headers["set-cookie"].lower()
        assert "httponly" in naglowek
        assert "samesite=lax" in naglowek

    def test_bledne_haslo_daje_401(self, klient: TestClient, baza: Session) -> None:
        uzytkownik = zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        klient.cookies.clear()
        odpowiedz = klient.post(
            "/api/v1/auth/logowanie", json={"login": uzytkownik.login, "haslo": "zle-haslo"}
        )
        assert odpowiedz.status_code == 401

    def test_zmiana_hasla_wymaga_biezacego(self, klient: TestClient, baza: Session) -> None:
        zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        odpowiedz = klient.post(
            "/api/v1/auth/haslo",
            json={"haslo_biezace": "nie-to-haslo", "haslo_nowe": "NoweHaslo123456"},
        )
        assert odpowiedz.status_code == 400

    def test_zmiana_hasla_wylogowuje_wszedzie(self, klient: TestClient, baza: Session) -> None:
        """Jeśli powodem zmiany było podejrzenie przejęcia konta, stare sesje
        muszą przestać działać.
        """
        zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        odpowiedz = klient.post(
            "/api/v1/auth/haslo",
            json={"haslo_biezace": HASLO, "haslo_nowe": "ZupelnieNoweHaslo123"},
        )
        assert odpowiedz.status_code == 204
        assert klient.get("/api/v1/auth/ja").status_code == 401

    def test_nowe_haslo_nie_moze_byc_takie_samo(self, klient: TestClient, baza: Session) -> None:
        zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        odpowiedz = klient.post(
            "/api/v1/auth/haslo", json={"haslo_biezace": HASLO, "haslo_nowe": HASLO}
        )
        assert odpowiedz.status_code == 400

    def test_krotkie_nowe_haslo_jest_odrzucane(self, klient: TestClient, baza: Session) -> None:
        zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        odpowiedz = klient.post(
            "/api/v1/auth/haslo", json={"haslo_biezace": HASLO, "haslo_nowe": "krotkie"}
        )
        assert odpowiedz.status_code == 400
        assert "12 znaków" in odpowiedz.json()["detail"]


class TestKonfliktWersji:
    """Optimistic locking przez HTTP: punkt H z listy blokującej planu."""

    def test_zapis_na_aktualnej_wersji_przechodzi(
        self, klient_admin: TestClient, budynek_api: Budynek
    ) -> None:
        aktualny = klient_admin.get("/api/v1/budynki").json()["pozycje"][0]
        odpowiedz = klient_admin.put(
            f"/api/v1/budynki/{budynek_api.id}",
            json={**NOWY_BUDYNEK, "wersja": aktualny["wersja"]},
        )
        assert odpowiedz.status_code == 200
        assert odpowiedz.json()["wersja"] == aktualny["wersja"] + 1

    def test_zapis_na_starej_wersji_daje_409(
        self, klient_admin: TestClient, budynek_api: Budynek
    ) -> None:
        """Dwie osoby otwierają ten sam profil. Druga nie może nadpisać po cichu."""
        pierwsza = klient_admin.put(
            f"/api/v1/budynki/{budynek_api.id}", json={**NOWY_BUDYNEK, "wersja": 1}
        )
        assert pierwsza.status_code == 200

        druga = klient_admin.put(
            f"/api/v1/budynki/{budynek_api.id}",
            json={**NOWY_BUDYNEK, "nazwa": "Nadpisane", "wersja": 1},
        )
        assert druga.status_code == 409
        assert "zmieniony" in druga.json()["detail"]

    def test_odpowiedz_409_niesie_aktualna_wersje(
        self, klient_admin: TestClient, budynek_api: Budynek
    ) -> None:
        """Front ma pokazać różnicę, a nie tylko komunikat 'spróbuj jeszcze raz'."""
        klient_admin.put(f"/api/v1/budynki/{budynek_api.id}", json={**NOWY_BUDYNEK, "wersja": 1})
        druga = klient_admin.put(
            f"/api/v1/budynki/{budynek_api.id}", json={**NOWY_BUDYNEK, "wersja": 1}
        )
        assert druga.headers["X-Wersja-Biezaca"] == "2"
        assert "aktualna: 2" in druga.json()["detail"]

    def test_brak_wersji_w_zadaniu_jest_bledem(
        self, klient_admin: TestClient, budynek_api: Budynek
    ) -> None:
        odpowiedz = klient_admin.put(f"/api/v1/budynki/{budynek_api.id}", json=NOWY_BUDYNEK)
        assert odpowiedz.status_code == 422
