"""Odczyt arkusza XLSX. Cienka warstwa nad openpyxl, bez żadnej logiki.

Walidacja siedzi w `domena/import_arkusza.py` i nie wie, że dane przyszły
z Excela. Ten plik tylko zamienia arkusz na listę słowników.
"""

from dataclasses import dataclass
from io import BytesIO

from openpyxl import load_workbook

#: Ile wierszy pokazujemy w podglądzie przed importem.
WIERSZE_PODGLADU = 20

#: Ile wierszy w ogóle przyjmujemy z jednego pliku.
#: Wyżej zaczyna się temat importu wsadowego w tle, a nie żądania HTTP.
LIMIT_WIERSZY = 5000


class BladArkusza(Exception):
    """Pliku nie da się odczytać jako arkusza."""


#: Ten sam komunikat niezależnie od tego, która funkcja zawiedzie.
#: Człowiek, który trafi na jedną albo drugą, potrzebuje tej samej podpowiedzi.
KOMUNIKAT_ZLEGO_PLIKU = (
    "Nie udało się odczytać pliku jako arkusza Excela. "
    "Sprawdź, czy to plik XLSX, a nie XLS albo CSV."
)


@dataclass(frozen=True)
class OdczytanyArkusz:
    """Nagłówki i wiersze arkusza w postaci surowej."""

    naglowki: list[str]
    wiersze: list[list[object]]

    @property
    def liczba_wierszy(self) -> int:
        return len(self.wiersze)


def wczytaj_arkusz(zawartosc: bytes, *, nazwa_arkusza: str | None = None) -> OdczytanyArkusz:
    """Pierwszy arkusz pliku (albo wskazany po nazwie) jako nagłówki i wiersze.

    Wiersze całkowicie puste są pomijane: arkusze prowadzone ręcznie mają
    zwykle kilkadziesiąt pustych wierszy na końcu i bez tego każdy z nich
    byłby zgłoszony jako błąd braku danych.
    """
    try:
        # read_only i data_only: interesują nas wartości, nie formuły ani style.
        skoroszyt = load_workbook(BytesIO(zawartosc), read_only=True, data_only=True)
    except Exception as blad:
        raise BladArkusza(KOMUNIKAT_ZLEGO_PLIKU) from blad

    try:
        arkusz = skoroszyt[nazwa_arkusza] if nazwa_arkusza else skoroszyt.worksheets[0]
    except (KeyError, IndexError) as blad:
        raise BladArkusza(f"W pliku nie ma arkusza o nazwie „{nazwa_arkusza}”.") from blad

    wiersze_iter = arkusz.iter_rows(values_only=True)
    try:
        naglowki_surowe = next(wiersze_iter)
    except StopIteration as blad:
        raise BladArkusza("Arkusz jest pusty.") from blad

    naglowki = [str(n).strip() if n is not None else "" for n in naglowki_surowe]
    if not any(naglowki):
        raise BladArkusza("Pierwszy wiersz arkusza jest pusty, a powinien zawierać nagłówki.")

    wiersze: list[list[object]] = []
    for wiersz in wiersze_iter:
        if all(k is None or str(k).strip() == "" for k in wiersz):
            continue
        wiersze.append(list(wiersz))
        if len(wiersze) > LIMIT_WIERSZY:
            raise BladArkusza(
                f"Arkusz ma ponad {LIMIT_WIERSZY} wierszy. "
                "Podziel go na części albo zgłoś potrzebę importu wsadowego."
            )

    skoroszyt.close()
    return OdczytanyArkusz(naglowki=naglowki, wiersze=wiersze)


def nazwy_arkuszy(zawartosc: bytes) -> list[str]:
    """Nazwy arkuszy w pliku. Człowiek wybiera, który importujemy."""
    try:
        skoroszyt = load_workbook(BytesIO(zawartosc), read_only=True, data_only=True)
    except Exception as blad:
        raise BladArkusza(KOMUNIKAT_ZLEGO_PLIKU) from blad
    nazwy = list(skoroszyt.sheetnames)
    skoroszyt.close()
    return nazwy
