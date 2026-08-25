"""Swieta polskie i dni robocze.

Bez tego alerty klamalyby kilka razy w roku: termin "do 10-go" wypadajacy
w niedziele i termin "14 dni od przekazania" konczacy sie w Boze Cialo.

Swieta ruchome sa liczone algorytmem, a nie wpisane na sztywno, bo tabela
wpisana recznie konczy sie w roku, do ktorego ktos ja doprowadzil.
"""

import calendar
from datetime import date, timedelta

#: Dzien wolny 6 stycznia przywrocono ustawa obowiazujaca od 2011 roku.
#: Umowy z archiwum bywaja starsze, wiec dla wczesniejszych lat to dzien roboczy.
PIERWSZY_ROK_TRZECH_KROLI = 2011

#: Swieta o stalej dacie: (miesiac, dzien).
SWIETA_STALE: tuple[tuple[int, int], ...] = (
    (1, 1),  # Nowy Rok
    (5, 1),  # Swieto Pracy
    (5, 3),  # Swieto Narodowe Trzeciego Maja
    (8, 15),  # Wniebowziecie Najswietszej Maryi Panny
    (11, 1),  # Wszystkich Swietych
    (11, 11),  # Narodowe Swieto Niepodleglosci
    (12, 25),  # Boze Narodzenie
    (12, 26),  # drugi dzien Bozego Narodzenia
)

#: Przesuniecia swiat ruchomych wzgledem Wielkanocy, w dniach.
PONIEDZIALEK_WIELKANOCNY = 1
ZIELONE_SWIATKI = 49
BOZE_CIALO = 60


def wielkanoc(rok: int) -> date:
    """Niedziela Wielkanocna w kalendarzu gregorianskim.

    Algorytm anonimowy gregorianski (wariant Meeusa). Wynik zawsze wypada
    miedzy 22 marca a 25 kwietnia i zawsze w niedziele.
    """
    a = rok % 19
    b, c = divmod(rok, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lam = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lam) // 451
    miesiac, dzien = divmod(h + lam - 7 * m + 114, 31)
    return date(rok, miesiac, dzien + 1)


def swieta_polskie(rok: int) -> frozenset[date]:
    """Wszystkie dni ustawowo wolne od pracy w danym roku."""
    dni = {date(rok, miesiac, dzien) for miesiac, dzien in SWIETA_STALE}

    if rok >= PIERWSZY_ROK_TRZECH_KROLI:
        dni.add(date(rok, 1, 6))

    niedziela_wielkanocna = wielkanoc(rok)
    dni.add(niedziela_wielkanocna)
    for przesuniecie in (PONIEDZIALEK_WIELKANOCNY, ZIELONE_SWIATKI, BOZE_CIALO):
        dni.add(niedziela_wielkanocna + timedelta(days=przesuniecie))

    return frozenset(dni)


def czy_swieto(dzien: date) -> bool:
    return dzien in swieta_polskie(dzien.year)


def czy_dzien_roboczy(dzien: date) -> bool:
    """Dzien roboczy to nie-sobota, nie-niedziela i nie-swieto."""
    return dzien.weekday() < 5 and not czy_swieto(dzien)


def przesun_na_dzien_roboczy(dzien: date) -> date:
    """Termin przesuniety na najblizszy dzien roboczy, liczac od podanego.

    Dzien, ktory juz jest roboczy, zostaje bez zmian. Tego uzywamy do terminow
    platnosci: "do 10-go" wypadajace w niedziele oznacza poniedzialek,
    a nie sobote przed.
    """
    biezacy = dzien
    while not czy_dzien_roboczy(biezacy):
        biezacy += timedelta(days=1)
    return biezacy


def nastepny_dzien_roboczy(dzien: date) -> date:
    """Pierwszy dzien roboczy PO podanym. Zawsze idzie do przodu."""
    return przesun_na_dzien_roboczy(dzien + timedelta(days=1))


def dodaj_dni_robocze(dzien: date, ile: int) -> date:
    """Data oddalona o podana liczbe dni roboczych. Liczba ujemna cofa."""
    if ile == 0:
        return dzien

    krok = timedelta(days=1 if ile > 0 else -1)
    pozostalo = abs(ile)
    biezacy = dzien
    while pozostalo:
        biezacy += krok
        if czy_dzien_roboczy(biezacy):
            pozostalo -= 1
    return biezacy


def dzien_miesiaca(rok: int, miesiac: int, dzien: int) -> date:
    """Konkretna data dla terminu typu "do 10-go dnia miesiaca".

    Gdy umowa mowi "do 31-go", a miesiac ma 30 dni, terminem jest ostatni dzien
    miesiaca. Bez tego kwiecien, czerwiec, wrzesien, listopad i luty w ogole
    nie mialyby terminu.
    """
    if not 1 <= dzien <= 31:
        raise ValueError(f"Dzień miesiąca musi mieścić się między 1 a 31, otrzymano {dzien}.")
    ostatni = calendar.monthrange(rok, miesiac)[1]
    return date(rok, miesiac, min(dzien, ostatni))
