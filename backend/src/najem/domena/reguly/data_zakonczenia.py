"""Regula R1: wyliczanie daty zakonczenia umowy.

Okres najmu liczy sie zwykle od daty przekazania lokalu, a nie od podpisania.
Bez protokolu przekazania data konca umowy jest NIEUSTALONA i tak ma zostac
pokazana. Lepiej "nieustalona" niz falszywy termin, na ktorym ktos oprze
decyzje o wypowiedzeniu.
"""

from datetime import date, timedelta

from najem.domena.kalendarz import dodaj_miesiace
from najem.domena.reguly.wynik import Wynik, nieustalony, ustalony
from najem.domena.slowniki import BazaOkresuNajmu

#: Czy ostatni dzien okresu nalezy jeszcze do umowy.
#:
#: True  -> umowa na 24 miesiace od 01.02.2026 konczy sie 31.01.2028
#: False -> ta sama umowa konczy sie 01.02.2028 (art. 112 Kodeksu cywilnego)
#:
#: Domyslnie True, bo tak formuluje to wiekszosc umow najmu komercyjnego
#: ("umowa obowiazuje do dnia..."). To zalozenie do potwierdzenia na realnych
#: dokumentach: patrz docs/postep.md, sekcja "Czego nadal nie wiem".
KONIEC_WLACZNIE = True


def data_zakonczenia(
    *,
    bazuje_na: BazaOkresuNajmu,
    okres_miesiace: int | None,
    data_zawarcia: date | None = None,
    data_przekazania: date | None = None,
    koniec_wlacznie: bool = KONIEC_WLACZNIE,
) -> Wynik[date]:
    """Planowana data zakonczenia umowy albo powod, dla ktorego jej nie ma."""
    if okres_miesiace is None:
        return nieustalony(
            "Nie podano okresu, na jaki zawarto umowę.",
            "Okres zawarcia jest parametrem umowy i powinien wynikać z dokumentu.",
        )
    if okres_miesiace <= 0:
        return nieustalony(
            f"Okres zawarcia umowy musi być dodatni, podano {okres_miesiace} miesięcy.",
        )

    if bazuje_na is BazaOkresuNajmu.DATA_PRZEKAZANIA:
        if data_przekazania is None:
            return nieustalony(
                "Brak protokołu przekazania, nie można wyliczyć końca umowy.",
                "Umowa liczy okres od dnia przekazania lokalu.",
                "Wprowadź datę przekazania albo zmień podstawę liczenia okresu.",
            )
        poczatek = data_przekazania
        podstawa = "daty przekazania lokalu"
    else:
        if data_zawarcia is None:
            return nieustalony(
                "Brak daty zawarcia umowy, nie można wyliczyć jej końca.",
            )
        poczatek = data_zawarcia
        podstawa = "daty zawarcia umowy"

    koniec = dodaj_miesiace(poczatek, okres_miesiace)
    if koniec_wlacznie:
        koniec -= timedelta(days=1)

    return ustalony(
        koniec,
        f"Okres {okres_miesiace} mies. liczony od {podstawa} ({poczatek.isoformat()}).",
        "Ostatni dzień okresu należy jeszcze do umowy."
        if koniec_wlacznie
        else "Umowa kończy się z upływem dnia odpowiadającego dacie początkowej.",
    )


def data_wypowiedzenia(
    *,
    data_zakonczenia_umowy: date | None,
    okres_wypowiedzenia_miesiace: int | None,
) -> Wynik[date]:
    """Ostatni dzien, w ktorym mozna jeszcze skutecznie wypowiedziec umowe.

    Po tej dacie umowa przedluza sie albo wygasa bez decyzji, co katalog zdarzen
    z sekcji 6 koncepcji traktuje jako zdarzenie krytyczne.
    """
    if data_zakonczenia_umowy is None:
        return nieustalony(
            "Data zakończenia umowy jest nieustalona, więc termin wypowiedzenia też.",
        )
    if okres_wypowiedzenia_miesiace is None:
        return nieustalony("Nie podano okresu wypowiedzenia.")
    if okres_wypowiedzenia_miesiace <= 0:
        return nieustalony(
            f"Okres wypowiedzenia musi być dodatni, podano {okres_wypowiedzenia_miesiace}.",
        )

    termin = dodaj_miesiace(data_zakonczenia_umowy, -okres_wypowiedzenia_miesiace)
    return ustalony(
        termin,
        f"{okres_wypowiedzenia_miesiace} mies. przed końcem umowy "
        f"({data_zakonczenia_umowy.isoformat()}).",
    )
