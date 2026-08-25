"""Regula R7: przeglady okresowe.

Element jest osobnym bytem, a nie polem tekstowym, dlatego da sie zadac pytanie
"wszystkie gasnice do przegladu w tym kwartale". W praktyce zleca sie je hurtowo.
"""

from datetime import date

from najem.domena.kalendarz import dodaj_miesiace
from najem.domena.reguly.wynik import Wynik, nieustalony, ustalony
from najem.domena.slowniki import StatusPrzegladu

#: Ile dni przed terminem przeglad zaczyna sie "zblizac" (katalog zdarzen, sekcja 6).
PROG_OSTRZEZENIA_DNI = 30


def nastepny_przeglad(
    *,
    ostatni_przeglad: date | None,
    czestotliwosc_miesiace: int | None,
) -> Wynik[date]:
    """Termin kolejnego przegladu: ostatni plus czestotliwosc.

    Brak daty ostatniego przegladu to NIE jest powod, zeby uznac przeglad
    za aktualny. To powod, zeby go ustalic, i taki wlasnie komunikat wraca.
    """
    if czestotliwosc_miesiace is None:
        return nieustalony("Nie podano częstotliwości przeglądu.")
    if czestotliwosc_miesiace <= 0:
        return nieustalony(
            f"Częstotliwość przeglądu musi być dodatnia, podano {czestotliwosc_miesiace}."
        )
    if ostatni_przeglad is None:
        return nieustalony(
            "Brak daty ostatniego przeglądu, więc terminu kolejnego nie da się wyliczyć.",
            "Wprowadź datę z ostatniego protokołu przeglądu.",
        )

    termin = dodaj_miesiace(ostatni_przeglad, czestotliwosc_miesiace)
    return ustalony(
        termin,
        f"{czestotliwosc_miesiace} mies. od ostatniego przeglądu ({ostatni_przeglad.isoformat()}).",
    )


def status_przegladu(
    *,
    nastepny_termin: date | None,
    dzis: date,
    prog_ostrzezenia_dni: int = PROG_OSTRZEZENIA_DNI,
) -> StatusPrzegladu:
    """Ocena stanu przegladu na dany dzien.

    Brak terminu daje NIEUSTALONY, a nie AKTUALNY. Roznica jest istotna:
    przeglad, ktorego terminu nie znamy, wyglada na zalatwiony tylko dlatego,
    ze nikt go nie wpisal.
    """
    if nastepny_termin is None:
        return StatusPrzegladu.NIEUSTALONY
    if nastepny_termin < dzis:
        return StatusPrzegladu.PRZETERMINOWANY
    if (nastepny_termin - dzis).days <= prog_ostrzezenia_dni:
        return StatusPrzegladu.ZBLIZA_SIE
    return StatusPrzegladu.AKTUALNY


def przeglad_po_protokole(
    *,
    data_protokolu: date,
    czestotliwosc_miesiace: int | None,
) -> Wynik[date]:
    """Nowy termin po wgraniu protokolu z przegladu.

    Wgranie protokolu aktualizuje date ostatniego przegladu i przelicza kolejny
    termin. To jedyna sciezka, ktora przesuwa termin do przodu.
    """
    return nastepny_przeglad(
        ostatni_przeglad=data_protokolu,
        czestotliwosc_miesiace=czestotliwosc_miesiace,
    )
