"""Endpoint /health musi odpowiadac takze wtedy, gdy baza nie stoi."""

from fastapi.testclient import TestClient

from najem.main import app

klient = TestClient(app)


def test_zdrowie_odpowiada_200() -> None:
    odpowiedz = klient.get("/api/v1/health")
    assert odpowiedz.status_code == 200


def test_zdrowie_ma_komplet_pol() -> None:
    dane = klient.get("/api/v1/health").json()
    assert dane["status"] in {"ok", "degradacja"}
    assert "srodowisko" in dane
    assert "polaczona" in dane["baza"]


def test_brak_bazy_to_degradacja_a_nie_wyjatek() -> None:
    """Diagnostyka ma raportowac awarie, nie wywalac sie razem z nia."""
    dane = klient.get("/api/v1/health").json()
    if not dane["baza"]["polaczona"]:
        assert dane["status"] == "degradacja"
        assert dane["baza"]["blad"]
