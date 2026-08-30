"""Ustawienia, ktore zmienia sie z interfejsu, nie z pliku .env.

Kolejnosc jest ustalona i wazna: **baza wygrywa z plikiem**. Wartosc w .env
jest tym, co ustawil ten, kto program instalowal; wartosc w bazie tym, co
ustawil uzytkownik. Gdy w bazie nic nie ma, wracamy do pliku -- dzieki temu
program dziala tak samo jak przed ta zmiana, dopoki nikt niczego nie kliknie.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from najem.config import ustawienia
from najem.modele import KLUCZ_KATALOG_SKANU, UstawienieSystemu


class BladUstawienia(Exception):
    """Wartosc nie nadaje sie do zapisania. Komunikat idzie wprost do czlowieka."""


@dataclass(frozen=True)
class KatalogSkanu:
    """Skad pochodzi katalog i czy w ogole da sie go dzis odczytac."""

    sciezka: Path | None
    #: baza | plik | brak -- czlowiek musi wiedziec, co wlasciwie zmienia.
    zrodlo: str
    istnieje: bool

    @property
    def czy_ustawiony(self) -> bool:
        return self.sciezka is not None


def _wiersz(baza: Session, klucz: str) -> UstawienieSystemu | None:
    return baza.scalars(
        select(UstawienieSystemu).where(
            UstawienieSystemu.klucz == klucz,
            UstawienieSystemu.usunieto_dnia.is_(None),
        )
    ).one_or_none()


def katalog_skanu(baza: Session) -> Path | None:
    """Katalog z dokumentami: najpierw z bazy, potem z .env, na koncu nic."""
    wiersz = _wiersz(baza, KLUCZ_KATALOG_SKANU)
    if wiersz is not None and wiersz.wartosc:
        return Path(wiersz.wartosc)
    return ustawienia().katalog_skanu


def opis_katalogu_skanu(baza: Session) -> KatalogSkanu:
    """To samo co wyzej, ale z informacja, skad wartosc pochodzi.

    Ekran ustawien musi umiec powiedziec "to jest z pliku .env, zmiana tutaj
    go przykryje", bo inaczej zmiana wyglada na nieskuteczna.
    """
    wiersz = _wiersz(baza, KLUCZ_KATALOG_SKANU)
    if wiersz is not None and wiersz.wartosc:
        sciezka = Path(wiersz.wartosc)
        return KatalogSkanu(sciezka=sciezka, zrodlo="baza", istnieje=_czy_katalog(sciezka))

    z_pliku = ustawienia().katalog_skanu
    if z_pliku is not None:
        return KatalogSkanu(sciezka=z_pliku, zrodlo="plik", istnieje=_czy_katalog(z_pliku))

    return KatalogSkanu(sciezka=None, zrodlo="brak", istnieje=False)


def _czy_katalog(sciezka: Path) -> bool:
    """Czy sciezka wskazuje dzis na istniejacy katalog.

    Odlaczony dysk sieciowy podnosi OSError zamiast zwrocic falsz, wiec
    sprawdzenie musi to przewidziec -- inaczej ekran ustawien wywala sie
    razem z dyskiem, ktory ktos wypial.
    """
    try:
        return sciezka.is_dir()
    except OSError:
        return False


def sprawdz_katalog(tekst: str) -> Path:
    """Waliduje sciezke wpisana przez czlowieka i zwraca ja znormalizowana.

    Wymagamy, zeby katalog **istnial w chwili zapisu**. To celowe: literowka
    w sciezce jest najczestszym bledem przy tym polu, a wykryta od razu kosztuje
    poprawke jednego znaku zamiast pol godziny szukania, czemu skan nic nie
    znajduje.
    """
    czysty = tekst.strip().strip('"')
    if not czysty:
        raise BladUstawienia("Podaj ścieżkę do katalogu z dokumentami.")

    sciezka = Path(czysty)
    if not sciezka.is_absolute():
        raise BladUstawienia(
            "Podaj pełną ścieżkę, na przykład C:\\Users\\Nazwa\\Documents\\Budynki."
        )

    try:
        istnieje = sciezka.is_dir()
        plik = sciezka.is_file()
    except OSError as blad:
        raise BladUstawienia("Tej ścieżki nie da się odczytać w tym systemie.") from blad

    if plik:
        raise BladUstawienia("To jest plik, a potrzebny jest katalog.")
    if not istnieje:
        raise BladUstawienia(f"Katalog {sciezka} nie istnieje albo jest niedostępny.")

    return Path(str(sciezka))


def zapisz_katalog_skanu(baza: Session, *, sciezka: Path) -> UstawienieSystemu:
    """Zapisuje katalog w bazie. Zwraca wiersz do zapisania w audycie."""
    wiersz = _wiersz(baza, KLUCZ_KATALOG_SKANU)
    if wiersz is None:
        wiersz = UstawienieSystemu(klucz=KLUCZ_KATALOG_SKANU)
        baza.add(wiersz)

    wiersz.wartosc = str(sciezka)
    baza.flush()
    return wiersz


def wyczysc_katalog_skanu(baza: Session) -> UstawienieSystemu | None:
    """Usuwa ustawienie z bazy, czyli wraca do wartosci z pliku .env."""
    wiersz = _wiersz(baza, KLUCZ_KATALOG_SKANU)
    if wiersz is None:
        return None

    wiersz.usunieto_dnia = datetime.now(UTC)
    baza.flush()
    return wiersz
