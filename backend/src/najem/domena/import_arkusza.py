"""Walidacja wierszy importowanego arkusza. Czysta logika, bez bazy i bez pliku.

Firma prawie na pewno prowadzi to dziś w jakimś arkuszu. Import tego arkusza
to najszybsza droga do tego, żeby system był użyteczny w pierwszym tygodniu
(plan budowy, sekcja 1.2 punkt N).

Zasada nadrzędna: **albo cały plik, albo nic**. Import, który zapisuje połowę
wierszy i wywala się na trzydziestym, zostawia bazę w stanie, którego nikt
nie umie posprzątać. Dlatego najpierw sprawdzamy wszystko, a dopiero potem
cokolwiek zapisujemy.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class PoleImportu(StrEnum):
    """Pola, które arkusz może wnieść. Kolumny mapuje na nie człowiek."""

    BUDYNEK = "budynek"
    LOKAL = "lokal"
    TYP_LOKALU = "typ_lokalu"
    POWIERZCHNIA = "powierzchnia"
    NAJEMCA = "najemca"
    NIP = "nip"
    DATA_ZAWARCIA = "data_zawarcia"
    DATA_PRZEKAZANIA = "data_przekazania"
    OKRES_MIESIACE = "okres_miesiace"
    CZYNSZ = "czynsz"
    CZYNSZ_RODZAJ = "czynsz_rodzaj"
    STAWKA_VAT = "stawka_vat"
    DZIEN_PLATNOSCI = "dzien_platnosci"


#: Bez tych pól wiersz nie niesie nic, czego dałoby się użyć.
POLA_WYMAGANE: frozenset[PoleImportu] = frozenset(
    {PoleImportu.BUDYNEK, PoleImportu.LOKAL, PoleImportu.NAJEMCA}
)

#: Typy lokalu rozpoznawane w arkuszu, po polsku i bez ogonków.
TYPY_LOKALU: dict[str, str] = {
    "handlowy": "handlowy",
    "uslugowy": "handlowy",
    "usługowy": "handlowy",
    "biurowy": "biurowy",
    "biuro": "biurowy",
    "magazyn": "magazyn",
    "magazynowy": "magazyn",
    "parking": "miejsce_postojowe",
    "miejsce postojowe": "miejsce_postojowe",
    "postojowe": "miejsce_postojowe",
}


@dataclass(frozen=True)
class BladWiersza:
    """Jeden problem w jednym wierszu. Numer wiersza jest numerem z arkusza."""

    wiersz: int
    pole: str | None
    komunikat: str

    def __str__(self) -> str:
        gdzie = f", kolumna „{self.pole}”" if self.pole else ""
        return f"Wiersz {self.wiersz}{gdzie}: {self.komunikat}"


@dataclass(frozen=True)
class WierszImportu:
    """Wiersz arkusza sprowadzony do wartości, które system rozumie."""

    numer: int
    budynek: str
    lokal: str
    najemca: str
    typ_lokalu: str = "inny"
    powierzchnia: Decimal | None = None
    nip: str | None = None
    data_zawarcia: date | None = None
    data_przekazania: date | None = None
    okres_miesiace: int | None = None
    czynsz: Decimal | None = None
    czynsz_rodzaj: str = "netto"
    stawka_vat: Decimal | None = None
    dzien_platnosci: int | None = None


@dataclass
class WynikSprawdzenia:
    """Co da się zaimportować i co stoi na przeszkodzie."""

    wiersze: list[WierszImportu] = field(default_factory=list)
    bledy: list[BladWiersza] = field(default_factory=list)

    @property
    def poprawny(self) -> bool:
        return not self.bledy


def _tekst(wartosc: object) -> str:
    if wartosc is None:
        return ""
    return str(wartosc).strip()


def _liczba(wartosc: object) -> Decimal | None:
    """Liczba z komórki. Arkusze bywają wypełniane po polsku, z przecinkiem."""
    tekst = _tekst(wartosc)
    if not tekst:
        return None
    # Spacja nierozdzielająca trafia do arkuszy z formatowania tysięcy.
    tekst = tekst.replace(" ", "").replace(" ", "").replace(" ", "")
    tekst = tekst.replace("zł", "").replace("PLN", "").strip()
    tekst = tekst.replace(",", ".")
    try:
        return Decimal(tekst)
    except InvalidOperation:
        return None


def _data(wartosc: object) -> date | None:
    """Data z komórki. openpyxl zwraca datetime, gdy komórka jest sformatowana."""
    if wartosc is None:
        return None
    # Kolejność ma znaczenie: datetime dziedziczy po date, więc sprawdzamy
    # go pierwszy, inaczej godzina zostałaby przy dacie biznesowej.
    if isinstance(wartosc, datetime):
        return wartosc.date()
    if isinstance(wartosc, date):
        return wartosc

    tekst = _tekst(wartosc)
    if not tekst:
        return None
    for rozdzielacz, kolejnosc in ((".", "DMY"), ("-", "YMD"), ("/", "DMY")):
        czesci = tekst.split(rozdzielacz)
        if len(czesci) != 3:
            continue
        try:
            liczby = [int(c) for c in czesci]
        except ValueError:
            continue
        rok, miesiac, dzien = (
            (liczby[2], liczby[1], liczby[0])
            if kolejnosc == "DMY"
            else (liczby[0], liczby[1], liczby[2])
        )
        try:
            return date(rok, miesiac, dzien)
        except ValueError:
            return None
    return None


def sprawdz_wiersz(
    numer: int, komorki: dict[PoleImportu, object]
) -> tuple[WierszImportu | None, list[BladWiersza]]:
    """Sprawdza jeden wiersz. Zwraca wynik albo listę problemów.

    Zbiera **wszystkie** problemy wiersza, a nie tylko pierwszy. Człowiek
    poprawiający arkusz woli zobaczyć trzy błędy naraz niż trzy razy
    uruchamiać import.
    """
    bledy: list[BladWiersza] = []

    for pole in POLA_WYMAGANE:
        if not _tekst(komorki.get(pole)):
            bledy.append(
                BladWiersza(numer, pole.value, "wartość jest wymagana, a komórka jest pusta")
            )

    typ_surowy = _tekst(komorki.get(PoleImportu.TYP_LOKALU)).lower()
    typ = TYPY_LOKALU.get(typ_surowy, "inny" if not typ_surowy else "")
    if typ == "":
        bledy.append(
            BladWiersza(
                numer,
                PoleImportu.TYP_LOKALU.value,
                f"nieznany typ lokalu „{typ_surowy}”. Dozwolone: "
                + ", ".join(sorted(set(TYPY_LOKALU))),
            )
        )
        typ = "inny"

    powierzchnia = None
    if _tekst(komorki.get(PoleImportu.POWIERZCHNIA)):
        powierzchnia = _liczba(komorki.get(PoleImportu.POWIERZCHNIA))
        if powierzchnia is None:
            bledy.append(BladWiersza(numer, PoleImportu.POWIERZCHNIA.value, "to nie jest liczba"))
        elif powierzchnia <= 0:
            bledy.append(
                BladWiersza(numer, PoleImportu.POWIERZCHNIA.value, "powierzchnia musi być dodatnia")
            )

    czynsz = None
    if _tekst(komorki.get(PoleImportu.CZYNSZ)):
        czynsz = _liczba(komorki.get(PoleImportu.CZYNSZ))
        if czynsz is None:
            bledy.append(BladWiersza(numer, PoleImportu.CZYNSZ.value, "to nie jest kwota"))

    rodzaj = _tekst(komorki.get(PoleImportu.CZYNSZ_RODZAJ)).lower() or "netto"
    if rodzaj not in {"netto", "brutto"}:
        bledy.append(
            BladWiersza(
                numer,
                PoleImportu.CZYNSZ_RODZAJ.value,
                f"„{rodzaj}” to ani netto, ani brutto",
            )
        )
        rodzaj = "netto"

    vat = _liczba(komorki.get(PoleImportu.STAWKA_VAT))
    if czynsz is not None and rodzaj == "netto" and vat is None:
        # Kwoty netto bez stawki VAT nie da się zbrutować, więc nie jest kwotą.
        bledy.append(
            BladWiersza(
                numer,
                PoleImportu.STAWKA_VAT.value,
                "czynsz jest netto, więc stawka VAT jest wymagana",
            )
        )

    for pole in (PoleImportu.DATA_ZAWARCIA, PoleImportu.DATA_PRZEKAZANIA):
        if _tekst(komorki.get(pole)) and _data(komorki.get(pole)) is None:
            bledy.append(
                BladWiersza(numer, pole.value, "to nie jest data (oczekiwany format DD.MM.RRRR)")
            )

    okres = _liczba(komorki.get(PoleImportu.OKRES_MIESIACE))
    if _tekst(komorki.get(PoleImportu.OKRES_MIESIACE)) and (okres is None or okres <= 0):
        bledy.append(
            BladWiersza(numer, PoleImportu.OKRES_MIESIACE.value, "okres musi być liczbą dodatnią")
        )

    dzien = _liczba(komorki.get(PoleImportu.DZIEN_PLATNOSCI))
    if _tekst(komorki.get(PoleImportu.DZIEN_PLATNOSCI)) and (
        dzien is None or not (1 <= dzien <= 31)
    ):
        bledy.append(
            BladWiersza(
                numer, PoleImportu.DZIEN_PLATNOSCI.value, "dzień płatności musi być z zakresu 1–31"
            )
        )

    if bledy:
        return None, bledy

    return (
        WierszImportu(
            numer=numer,
            budynek=_tekst(komorki.get(PoleImportu.BUDYNEK)),
            lokal=_tekst(komorki.get(PoleImportu.LOKAL)),
            najemca=_tekst(komorki.get(PoleImportu.NAJEMCA)),
            typ_lokalu=typ,
            powierzchnia=powierzchnia,
            nip=_tekst(komorki.get(PoleImportu.NIP)) or None,
            data_zawarcia=_data(komorki.get(PoleImportu.DATA_ZAWARCIA)),
            data_przekazania=_data(komorki.get(PoleImportu.DATA_PRZEKAZANIA)),
            okres_miesiace=int(okres) if okres is not None else None,
            czynsz=czynsz,
            czynsz_rodzaj=rodzaj,
            stawka_vat=vat,
            dzien_platnosci=int(dzien) if dzien is not None else None,
        ),
        [],
    )


def sprawdz_arkusz(
    wiersze: list[dict[PoleImportu, object]], *, pierwszy_numer: int = 2
) -> WynikSprawdzenia:
    """Sprawdza cały arkusz i dodatkowo szuka duplikatów w samym pliku.

    Numeracja zaczyna się od drugiego wiersza, bo pierwszy to zwykle nagłówek.
    """
    wynik = WynikSprawdzenia()
    widziane: dict[tuple[str, str], int] = {}

    for przesuniecie, komorki in enumerate(wiersze):
        numer = pierwszy_numer + przesuniecie
        wiersz, bledy = sprawdz_wiersz(numer, komorki)
        wynik.bledy.extend(bledy)
        if wiersz is None:
            continue

        klucz = (wiersz.budynek.casefold(), wiersz.lokal.casefold())
        if klucz in widziane:
            wynik.bledy.append(
                BladWiersza(
                    numer,
                    PoleImportu.LOKAL.value,
                    f"ten lokal występuje już w wierszu {widziane[klucz]} tego samego pliku",
                )
            )
            continue
        widziane[klucz] = numer
        wynik.wiersze.append(wiersz)

    return wynik
