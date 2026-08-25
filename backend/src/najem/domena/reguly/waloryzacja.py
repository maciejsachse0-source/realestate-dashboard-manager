"""Regula R2: waloryzacja roczna czynszu.

Administrator wprowadza wskaznik raz w roku, a system znajduje wszystkie umowy
do przeliczenia i przygotowuje propozycje do zbiorczego zatwierdzenia.
Dzis to kilkanascie godzin pracy recznej rocznie.

Regula NIE zapisuje niczego. Zwraca propozycje. Zatwierdza czlowiek (decyzja D4),
a zatwierdzenie tworzy nowe wiersze parametr_wartosc od miesiaca waloryzacji.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from najem.domena.pieniadze import Kwota
from najem.domena.reguly.wynik import Wynik, nieustalony, ustalony
from najem.domena.slowniki import RodzajWskaznika


@dataclass(frozen=True)
class PropozycjaWaloryzacji:
    """Propozycja podwyzki dla jednej umowy. Do zatwierdzenia przez czlowieka."""

    kwota_stara: Kwota
    kwota_nowa: Kwota
    wskaznik_procent: Decimal
    obowiazuje_od: date

    @property
    def roznica(self) -> Kwota:
        return self.kwota_nowa - self.kwota_stara


def wskaznik_dla_umowy(
    *,
    rodzaj: RodzajWskaznika | None,
    stala_stawka_procent: Decimal | None,
    wskazniki_gus: dict[RodzajWskaznika, Decimal],
) -> Wynik[Decimal]:
    """Wskaznik, ktorym waloryzuje sie ta konkretna umowa.

    Umowy definiuja wskaznik roznie i to jest powod, dla ktorego trzymamy
    slownik wskaznikow, a nie jedno pole (pytanie otwarte nr 4 koncepcji).
    """
    if rodzaj is None:
        return nieustalony("Umowa nie określa rodzaju wskaźnika waloryzacji.")

    if rodzaj is RodzajWskaznika.STALA_STAWKA:
        if stala_stawka_procent is None:
            return nieustalony("Umowa waloryzuje się stałą stawką, ale jej wysokości nie podano.")
        return ustalony(stala_stawka_procent, "Stała stawka zapisana w umowie.")

    if rodzaj not in wskazniki_gus:
        return nieustalony(
            f"Brak wprowadzonego wskaźnika {rodzaj.value} dla tego roku.",
            "Administrator wprowadza wskaźnik raz, po publikacji przez GUS.",
        )
    return ustalony(wskazniki_gus[rodzaj], f"Wskaźnik {rodzaj.value}.")


def propozycja_waloryzacji(
    *,
    czynsz: Kwota | None,
    podlega: bool,
    miesiac_waloryzacji: int | None,
    rok: int,
    wskaznik_procent: Decimal,
    data_pierwszej_waloryzacji: date | None = None,
) -> Wynik[PropozycjaWaloryzacji]:
    """Nowa wysokosc czynszu po waloryzacji albo powod pominiecia umowy.

    Waloryzacja dziala na kwocie w tej postaci, w jakiej definiuje ja umowa.
    Jesli czynsz jest netto, podnosi sie netto; jesli brutto, to brutto.
    Typ Kwota niesie te informacje ze soba, wiec regula nie musi zgadywac.
    """
    if not podlega:
        return nieustalony("Umowa nie podlega waloryzacji.")
    if czynsz is None:
        return nieustalony(
            "Czynsz jest nieustalony, więc nie ma czego waloryzować.",
            "Sprawdź, czy kwota czynszu została zatwierdzona.",
        )
    if miesiac_waloryzacji is None:
        return nieustalony("Umowa nie określa miesiąca waloryzacji.")
    if not 1 <= miesiac_waloryzacji <= 12:
        return nieustalony(
            f"Miesiąc waloryzacji musi mieścić się między 1 a 12, podano {miesiac_waloryzacji}."
        )

    obowiazuje_od = date(rok, miesiac_waloryzacji, 1)

    if data_pierwszej_waloryzacji is not None and obowiazuje_od < data_pierwszej_waloryzacji:
        return nieustalony(
            "Pierwsza waloryzacja tej umowy przypada dopiero "
            f"{data_pierwszej_waloryzacji.isoformat()}.",
        )

    nowy = czynsz.powieksz_o_procent(wskaznik_procent)
    return ustalony(
        PropozycjaWaloryzacji(
            kwota_stara=czynsz,
            kwota_nowa=nowy,
            wskaznik_procent=wskaznik_procent,
            obowiazuje_od=obowiazuje_od,
        ),
        f"{czynsz.wartosc} razy (1 + {wskaznik_procent}%) = {nowy.wartosc}.",
        f"Obowiązuje od {obowiazuje_od.isoformat()}.",
    )


def wartosc_z_wielokrotnosci(czynsz: Kwota | None, krotnosc: Decimal | None) -> Wynik[Kwota]:
    """Regula R5: wartosc zabezpieczenia wyrazona jako wielokrotnosc czynszu.

    Uzywane tez po waloryzacji: jesli wartosc weksla jest wielokrotnoscia
    czynszu, a czynsz sie zmienil, weksel przestaje pokrywac ekspozycje.
    """
    if czynsz is None:
        return nieustalony("Czynsz jest nieustalony, więc nie da się wyliczyć wielokrotności.")
    if krotnosc is None:
        return nieustalony("Nie podano krotności czynszu.")
    if krotnosc <= 0:
        return nieustalony(f"Krotność musi być dodatnia, podano {krotnosc}.")

    return ustalony(
        czynsz.pomnoz(krotnosc),
        f"{krotnosc} razy czynsz {czynsz.wartosc} {czynsz.waluta}.",
    )


def czy_zabezpieczenie_wymaga_przeliczenia(
    *,
    wartosc_biezaca: Kwota | None,
    czynsz_po_waloryzacji: Kwota | None,
    krotnosc: Decimal | None,
) -> bool:
    """Czy po waloryzacji zabezpieczenie przestalo pokrywac ekspozycje (R5).

    Zwraca False, gdy czegokolwiek brakuje: brak danych nie jest podstawa
    do wystawienia alertu, bo alarm bez pokrycia w danych uczy ludzi
    ignorowania alarmow.
    """
    if wartosc_biezaca is None or czynsz_po_waloryzacji is None or krotnosc is None:
        return False
    wymagana = wartosc_z_wielokrotnosci(czynsz_po_waloryzacji, krotnosc)
    if not wymagana.ustalone:
        return False
    return wymagana.wymagaj().wartosc != wartosc_biezaca.wartosc
