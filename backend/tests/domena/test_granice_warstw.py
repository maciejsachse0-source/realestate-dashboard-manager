"""Najwazniejsza granica w projekcie: domena/ to czysty Python.

Plan, sekcja 3: katalog domena/ nie importuje niczego z modele/, api/ ani z SQLAlchemy.
Ten test pilnuje tego automatycznie, zeby nie trzeba bylo pamietac.
"""

import ast
from pathlib import Path

KATALOG_DOMENY = Path(__file__).resolve().parents[2] / "src" / "najem" / "domena"

ZAKAZANE_KORZENIE = {
    "sqlalchemy",
    "fastapi",
    "psycopg",
    "alembic",
    "requests",
    "httpx",
    "starlette",
}
ZAKAZANE_MODULY_NAJEM = {"modele", "api", "repozytoria", "baza", "uslugi", "auth"}


def _pliki_domeny() -> list[Path]:
    return sorted(KATALOG_DOMENY.rglob("*.py"))


def _korzen(nazwa: str) -> str:
    return nazwa.split(".")[0]


def test_domena_nie_importuje_infrastruktury() -> None:
    naruszenia: list[str] = []

    for plik in _pliki_domeny():
        drzewo = ast.parse(plik.read_text(encoding="utf-8"), filename=str(plik))
        for wezel in ast.walk(drzewo):
            nazwy: list[str] = []
            linia = 0
            if isinstance(wezel, ast.Import):
                nazwy = [alias.name for alias in wezel.names]
                linia = wezel.lineno
            elif isinstance(wezel, ast.ImportFrom) and wezel.module:
                nazwy = [wezel.module]
                linia = wezel.lineno

            for nazwa in nazwy:
                if _korzen(nazwa) in ZAKAZANE_KORZENIE:
                    naruszenia.append(f"{plik.name}:{linia} importuje {nazwa}")
                if nazwa.startswith("najem."):
                    czlon = nazwa.split(".")[1]
                    if czlon in ZAKAZANE_MODULY_NAJEM:
                        naruszenia.append(f"{plik.name}:{linia} importuje {nazwa}")

    assert not naruszenia, "domena/ musi byc czysta:\n" + "\n".join(naruszenia)


def test_katalog_domeny_istnieje() -> None:
    assert KATALOG_DOMENY.is_dir()
