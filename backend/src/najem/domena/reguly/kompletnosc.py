"""Regula R9: kompletnosc profilu lokalu.

Decyzja D6: dziury w danych sa widoczne i policzalne, bo to one generuja
ryzyko. To jedyny sposob, zeby migracja starych umow kiedykolwiek sie skonczyla.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

#: Pola krytyczne z reguly R9. Bez nich profil jest niekompletny.
#:
#: Czesc z nich to klucze parametrow (czynsz, powierzchnia), czesc to fakty
#: spoza tabeli parametrow (najemca, status kaucji). Warstwa uslug sklada
#: jedno i drugie w zbior wypelnionych pol i podaje go tutaj.
POLA_KRYTYCZNE: frozenset[str] = frozenset(
    {
        "najemca",
        "powierzchnia",
        "data_przekazania",
        "data_zakonczenia",
        "czynsz_podstawowy",
        "terminy_platnosci",
        "status_kaucji",
        "status_polisy",
    }
)

#: Ponizej tego progu system nie pokazuje wyniku, tylko brak wyniku.
#: Regula produktowa z CLAUDE.md: coverage ponizej 40 procent oznacza
#: brak wyniku, a nie niski wynik.
PROG_UZYTECZNOSCI = Decimal("0.40")


@dataclass(frozen=True)
class OcenaKompletnosci:
    """Wskaznik kompletnosci wraz z lista tego, czego brakuje."""

    wypelnione: frozenset[str]
    brakujace: frozenset[str]
    wskaznik: Decimal

    @property
    def kompletny(self) -> bool:
        return not self.brakujace

    @property
    def uzyteczny(self) -> bool:
        """Czy danych jest dosc, zeby cokolwiek na nich opierac."""
        return self.wskaznik >= PROG_UZYTECZNOSCI

    @property
    def procent(self) -> int:
        """Wskaznik do pokazania uzytkownikowi, zaokraglony do pelnych procent.

        Zaokraglamy dopiero tutaj, a nie w `wskaznik`. Gdyby wskaznik byl
        zaokraglany przy wyliczaniu, profil o kompletnosci 0,395 podnioslby sie
        do 0,40 i przekroczylby prog uzytecznosci przez artefakt zaokraglenia,
        a nie przez uzupelnienie danych.
        """
        return int((self.wskaznik * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def ocen_kompletnosc(
    wypelnione: Iterable[str],
    wymagane: Iterable[str] = POLA_KRYTYCZNE,
) -> OcenaKompletnosci:
    """Kompletnosc jako udzial wypelnionych pol krytycznych.

    Pola spoza listy wymaganych sa pomijane: uzupelnienie pola nieobowiazkowego
    nie moze podnosic wskaznika, bo wtedy wskaznik przestaje mierzyc to,
    co ma mierzyc.
    """
    wymagane_zbior = frozenset(wymagane)
    if not wymagane_zbior:
        raise ValueError("Lista pól wymaganych nie może być pusta.")

    wypelnione_istotne = frozenset(wypelnione) & wymagane_zbior
    brakujace = wymagane_zbior - wypelnione_istotne
    # Wartosc dokladna, bez zaokraglania: porownanie z progiem uzytecznosci
    # musi zalezec od danych, a nie od tego, w ktora strone poszlo zaokraglenie.
    wskaznik = Decimal(len(wypelnione_istotne)) / Decimal(len(wymagane_zbior))

    return OcenaKompletnosci(
        wypelnione=wypelnione_istotne,
        brakujace=brakujace,
        wskaznik=wskaznik,
    )
