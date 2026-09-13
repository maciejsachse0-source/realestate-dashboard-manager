"""Czytanie konfiguracji z pliku .env.

Jeden przypadek, ale kosztowal pierwsze wrazenie z programu: instalator
zapisuje `KATALOG_SKANU=` bez wartosci, bo katalog wskazuje sie dopiero
w programie. Pydantic robil z pustego napisu `Path("")`, czyli `Path(".")`,
a to jest istniejacy katalog -- katalog roboczy serwera. Skan pokazywal wiec
`alembic` i `src` jako budynki uzytkownika i twierdzil, ze wszystko dziala.
"""

from pathlib import Path

import pytest

from najem.config import Ustawienia


def _ustawienia(tmp_path: Path, linia: str) -> Ustawienia:
    """Ustawienia zbudowane z pliku .env o jednej interesujacej nas linii."""
    plik = tmp_path / ".env"
    plik.write_text(f"SRODOWISKO=prod\n{linia}\n", encoding="utf-8")
    return Ustawienia(_env_file=plik)  # type: ignore[call-arg]


class TestKatalogSkanu:
    @pytest.mark.parametrize(
        "linia",
        [
            "KATALOG_SKANU=",
            "KATALOG_SKANU=   ",
            'KATALOG_SKANU=""',
        ],
    )
    def test_pusta_wartosc_to_brak_katalogu(self, tmp_path: Path, linia: str) -> None:
        """Brak wartosci ma dac None, a nie katalog biezacy.

        None wlacza na ekranie skanu komunikat "nie wskazano katalogu".
        `Path(".")` przechodzi przez `is_dir()` i udaje poprawna konfiguracje.
        """
        assert _ustawienia(tmp_path, linia).katalog_skanu is None

    def test_brak_klucza_to_brak_katalogu(self, tmp_path: Path) -> None:
        assert _ustawienia(tmp_path, "# bez klucza").katalog_skanu is None

    def test_kropka_wpisana_swiadomie_tez_nie_przechodzi(self, tmp_path: Path) -> None:
        """Nikt nie trzyma umow w katalogu roboczym serwera. Jesli w pliku stoi
        kropka, to jest to slad po pustej wartosci, a nie decyzja."""
        assert _ustawienia(tmp_path, "KATALOG_SKANU=.").katalog_skanu is None

    def test_prawdziwa_sciezka_przechodzi(self, tmp_path: Path) -> None:
        katalog = tmp_path / "Budynki"
        katalog.mkdir()
        wynik = _ustawienia(tmp_path, f"KATALOG_SKANU={katalog}").katalog_skanu
        assert wynik == katalog

    def test_sciezki_w_cudzyslowach_nie_wpisujemy_do_env(self, tmp_path: Path) -> None:
        """Cudzyslow w .env psuje sciezke Windows i tego nie da sie naprawic
        po naszej stronie.

        Czytnik .env przetwarza w cudzyslowach sekwencje z ukosnikiem wstecznym,
        wiec katalog "Temp" z podkatalogiem zaczynajacym sie na "t" traci
        ukosnik z litera na rzecz tabulatora. Cudzyslowy zdejmujemy, ale znak
        juz zamieniony nie wraca. Skutek jest widoczny -- taka sciezka nie
        istnieje i ekran mowi o tym wprost -- a nie cichy, i to jest tu jedyna
        gwarancja, jakiej mozemy udzielic.

        Wlasciwa droga to ekran "Dokumenty z dysku": `sprawdz_katalog` zdejmuje
        cudzyslowy z tego, co wklei czlowiek, i sprawdza katalog przy zapisie.
        """
        katalog = tmp_path / "dla Macka"
        katalog.mkdir()
        wpis = chr(34) + str(katalog) + chr(34)
        wynik = _ustawienia(tmp_path, "KATALOG_SKANU=" + wpis).katalog_skanu
        assert wynik is not None
