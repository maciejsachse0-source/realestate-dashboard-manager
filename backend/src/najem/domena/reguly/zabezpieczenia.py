"""Reguly R4, R5 i R6: kaucja, weksel i polisa ubezpieczeniowa.

Wspolny motyw: terminy sa w umowach relatywne ("14 dni od dnia przekazania"),
a system musi z nich wyliczyc konkretna date i pilnowac jej.

Wszystkie funkcje sprawdzajace zwracaja False, gdy brakuje danych. Alarm bez
pokrycia w danych uczy ludzi ignorowania alarmow, a to kosztuje wiecej niz
jeden pominiety termin.
"""

from datetime import date, timedelta

from najem.domena.kalendarz import przesun_na_dzien_roboczy
from najem.domena.pieniadze import Kwota
from najem.domena.reguly.wynik import Wynik, nieustalony, ustalony
from najem.domena.slowniki import StatusZabezpieczenia

#: Ile dni przed wygasnieciem polisy przypominamy (katalog zdarzen, sekcja 6).
PROG_OSTRZEZENIA_POLISA_DNI = 30


def termin_relatywny(
    *,
    punkt_odniesienia: date | None,
    dni: int | None,
    nazwa_punktu: str = "punktu odniesienia",
    przesun_na_roboczy: bool = True,
) -> Wynik[date]:
    """Konkretna data z terminu zapisanego jako "N dni od czegos".

    Dni liczymy kalendarzowo, tak jak w umowach, a dopiero wynik przesuwamy
    na dzien roboczy. Odwrotna kolejnosc dawalaby inne daty przy dlugich
    weekendach.
    """
    if punkt_odniesienia is None:
        return nieustalony(f"Brak {nazwa_punktu}, więc terminu nie da się wyliczyć.")
    if dni is None:
        return nieustalony("Nie podano liczby dni na dostarczenie.")
    if dni < 0:
        return nieustalony(f"Liczba dni nie może być ujemna, podano {dni}.")

    termin = punkt_odniesienia + timedelta(days=dni)
    if przesun_na_roboczy:
        przesuniety = przesun_na_dzien_roboczy(termin)
        if przesuniety != termin:
            return ustalony(
                przesuniety,
                f"{dni} dni od {punkt_odniesienia.isoformat()} to {termin.isoformat()}.",
                f"Termin wypadał w dzień wolny, więc przesunięto go na {przesuniety.isoformat()}.",
            )
        termin = przesuniety

    return ustalony(termin, f"{dni} dni od {punkt_odniesienia.isoformat()}.")


def czy_zalega(
    *,
    status: StatusZabezpieczenia,
    termin: date | None,
    dzis: date,
) -> bool:
    """Czy zabezpieczenie nie zostalo dostarczone mimo uplywu terminu.

    Reguly R4 (kaucja niewplacona) i R6 (polisa niedostarczona w terminie).
    """
    if termin is None:
        return False
    if status in {
        StatusZabezpieczenia.DOSTARCZONE,
        StatusZabezpieczenia.ZWROCONE,
        StatusZabezpieczenia.ZATRZYMANE,
    }:
        return False
    return dzis > termin


def termin_zwrotu_kaucji(
    *,
    data_zakonczenia_najmu: date | None,
    dni_na_zwrot: int | None,
) -> Wynik[date]:
    """Regula R4: kaucja do zwrotu w ciagu N dni od zakonczenia najmu.

    To jest termin, o ktorym latwo zapomniec i ktory generuje roszczenia.
    """
    return termin_relatywny(
        punkt_odniesienia=data_zakonczenia_najmu,
        dni=dni_na_zwrot,
        nazwa_punktu="daty zakończenia najmu",
    )


def czy_polisa_wygasla(*, data_waznosci: date | None, dzis: date) -> bool:
    """Regula R6: polisa juz nie obowiazuje."""
    if data_waznosci is None:
        return False
    return dzis > data_waznosci


def czy_polisa_wkrotce_wygasa(
    *,
    data_waznosci: date | None,
    dzis: date,
    prog_dni: int = PROG_OSTRZEZENIA_POLISA_DNI,
) -> bool:
    """Regula R6: polisa wygasa w ciagu progu ostrzegawczego.

    Polisa juz wygasla nie jest "wkrotce wygasajaca". To osobne zdarzenie
    o innej wadze, wiec nie mieszamy ich w jednym warunku.
    """
    if data_waznosci is None or dzis > data_waznosci:
        return False
    return (data_waznosci - dzis).days <= prog_dni


def czy_polisa_ponizej_wymaganej(
    *,
    suma_ubezpieczenia: Kwota | None,
    wymagana_kwota: Kwota | None,
) -> Wynik[bool]:
    """Regula R6: polisa opiewa na kwote nizsza niz wymagana umowa.

    Zwraca Wynik, a nie bool, bo roznica walut jest tu istotna: polisa w EUR
    przy wymaganiu w PLN wymaga decyzji czlowieka, a nie cichego porownania.
    """
    if suma_ubezpieczenia is None:
        return nieustalony("Nie wprowadzono sumy ubezpieczenia z polisy.")
    if wymagana_kwota is None:
        return nieustalony("Umowa nie określa wymaganej sumy ubezpieczenia.")
    if suma_ubezpieczenia.waluta != wymagana_kwota.waluta:
        return nieustalony(
            f"Polisa jest w {suma_ubezpieczenia.waluta}, a umowa wymaga "
            f"{wymagana_kwota.waluta}. Porównanie wymaga decyzji człowieka."
        )

    ponizej = suma_ubezpieczenia.wartosc < wymagana_kwota.wartosc
    return ustalony(
        ponizej,
        f"Polisa {suma_ubezpieczenia.wartosc} wobec wymaganych {wymagana_kwota.wartosc}.",
    )
