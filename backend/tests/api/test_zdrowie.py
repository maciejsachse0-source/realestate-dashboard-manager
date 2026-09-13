"""Endpoint /health musi odpowiadac takze wtedy, gdy baza nie stoi."""

import pytest
from fastapi.testclient import TestClient

from najem.main import KATALOG_INTERFEJSU, app

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


def test_index_nie_siedzi_w_cache_przegladarki() -> None:
    """Skrot pliku maja tylko pliki z assets/, index.html go nie ma.

    Gdy przegladarka poda go z wlasnego cache'u, uzytkownik oglada poprzednia
    wersje programu mimo zaktualizowanego serwera. Dokladnie ten objaw:
    "zmieniles cos, a ja tego nie widze".
    """
    if not KATALOG_INTERFEJSU.is_dir():
        pytest.skip("Interfejs nie jest zbudowany (brak frontend/dist).")

    odpowiedz = klient.get("/")
    assert odpowiedz.status_code == 200
    assert "no-cache" in odpowiedz.headers.get("cache-control", "")


def test_pliki_ze_skrotem_w_nazwie_moga_lezec_w_cache() -> None:
    """Odwrotna strona tej samej decyzji: assets/ nie unieważniamy, bo zmiana
    tresci zmienia nazwe pliku."""
    if not KATALOG_INTERFEJSU.is_dir():
        pytest.skip("Interfejs nie jest zbudowany (brak frontend/dist).")

    skrypty = sorted((KATALOG_INTERFEJSU / "assets").glob("*.js"))
    if not skrypty:
        pytest.skip("Brak zbudowanych plikow w assets/.")

    odpowiedz = klient.get(f"/assets/{skrypty[0].name}")
    assert odpowiedz.status_code == 200
    assert "no-cache" not in odpowiedz.headers.get("cache-control", "")


class TestAdresyEkranow:
    """Adresy w rodzaju /kartoteka istnieja tylko w routerze przegladarki.

    Serwer odpowiadal na nie 404, wiec kazde odswiezenie podstrony i kazdy
    wklejony adres konczyly sie strona bledu. Dzialalo wylacznie klikanie
    w menu, bo wtedy przegladarka nie pyta serwera o nowy adres.
    """

    @pytest.mark.parametrize(
        "adres",
        [
            "/kartoteka",
            "/kartoteka?zakladka=budynki",
            "/dokumenty-z-dysku",
            "/waloryzacja",
            "/terminy",
            "/lokale/327",
        ],
    )
    def test_odswiezenie_podstrony_zwraca_interfejs(self, adres: str) -> None:
        if not KATALOG_INTERFEJSU.is_dir():
            pytest.skip("Interfejs nie jest zbudowany (brak frontend/dist).")

        odpowiedz = klient.get(adres)
        assert odpowiedz.status_code == 200
        assert '<div id="root">' in odpowiedz.text
        assert "no-cache" in odpowiedz.headers.get("cache-control", "")

    def test_nieznany_endpoint_api_nadal_daje_404(self) -> None:
        """Front pytajacy o dane ma dostac czytelny 404, a nie kawalek HTML-a,
        na ktorym wywroci sie parsowanie odpowiedzi."""
        odpowiedz = klient.get("/api/v1/nie-ma-takiego-endpointu")
        assert odpowiedz.status_code == 404
        assert "text/html" not in odpowiedz.headers.get("content-type", "")

    def test_brakujacy_plik_zostaje_brakujacym_plikiem(self) -> None:
        """Nazwa z kropka to prosba o konkretny plik. Podstawienie pod nia
        interfejsu ukryloby brak pliku zamiast go pokazac."""
        if not KATALOG_INTERFEJSU.is_dir():
            pytest.skip("Interfejs nie jest zbudowany (brak frontend/dist).")

        assert klient.get("/nie-ma-takiego-pliku.png").status_code == 404
        assert klient.get("/assets/nie-ma-takiego.js").status_code == 404
