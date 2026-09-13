"""Liczba dni do terminu w odpowiedzi kokpitu terminow.

Wyliczenie nalezy do API, nie do przegladarki (CLAUDE.md, zasady architektury),
wiec sprawdzamy je tutaj, a nie w tescie interfejsu.
"""

from datetime import date

import pytest

from najem.api.v1.zdarzenia import na_wyjscie
from najem.domena.slowniki import StatusZdarzenia, TypZdarzenia, WagaZdarzenia
from najem.modele import Zdarzenie

DZIS = date(2026, 8, 28)


@pytest.fixture(autouse=True)
def dzien_odniesienia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zegar podmieniony na staly dzien.

    Bez tego test przechodzilby albo nie w zaleznosci od tego, kiedy zostal
    uruchomiony, a nagle czerwone testy pierwszego stycznia to najgorszy
    rodzaj testu.
    """
    monkeypatch.setattr("najem.api.v1.zdarzenia.dzis_lokalnie", lambda: DZIS)


def zdarzenie(data_zdarzenia: date) -> Zdarzenie:
    return Zdarzenie(
        id=1,
        typ=TypZdarzenia.POLISA_WYGASA,
        encja_typ="zabezpieczenie",
        encja_id=7,
        lokal_id=11,
        data_zdarzenia=data_zdarzenia,
        waga=WagaZdarzenia.OSTRZEZENIE,
        status=StatusZdarzenia.OTWARTE,
        tresc="Polisa wygasa.",
        wersja=1,
    )


def test_termin_w_przyszlosci() -> None:
    assert na_wyjscie(zdarzenie(date(2026, 9, 10))).dni_do_terminu == 13


def test_termin_dzisiaj_to_zero_a_nie_brak() -> None:
    """Zero i None znacza co innego: "dzis" kontra "nie wiadomo"."""
    wyjscie = na_wyjscie(zdarzenie(DZIS))
    assert wyjscie.dni_do_terminu == 0
    assert wyjscie.dni_do_terminu is not None


def test_termin_przeterminowany_jest_ujemny() -> None:
    assert na_wyjscie(zdarzenie(date(2026, 8, 15))).dni_do_terminu == -13


def test_pozostale_pola_zostaja_nietkniete() -> None:
    wyjscie = na_wyjscie(zdarzenie(date(2026, 9, 1)))
    assert wyjscie.tresc == "Polisa wygasa."
    assert wyjscie.waga == WagaZdarzenia.OSTRZEZENIE
    assert wyjscie.lokal_id == 11
