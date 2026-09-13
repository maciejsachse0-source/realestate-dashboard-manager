"""Liczby, kwoty i liczebniki z polskiego tekstu umowy.

Czysty Python. Wejściem jest napis, wyjściem `Decimal` wraz z pozycją, na
której stał w tekście — pozycja jest równie ważna jak wartość, bo bez niej
nie da się pokazać człowiekowi, skąd wzięła się propozycja (koncepcja, 7.2).

Nigdy `float`, także w środku. Ułamek dziesiętny przepuszczony przez `float`
traci grosze w sposób niewidoczny do momentu, w którym ktoś zsumuje sto pozycji.

**Największa pułapka tego pliku: kropka.** W polskim zapisie kwot kropka jest
separatorem tysięcy, więc „6.960" to sześć tysięcy dziewięćset sześćdziesiąt,
a nie sześć i dziewięćdziesiąt sześć setnych. W zapisie angielskim jest
odwrotnie. Umowy bywają pisane raz tak, raz tak, a różnica to trzy rzędy
wielkości na kwocie czynszu. Zasada rozstrzygająca jest w `czytaj_liczbe`,
a `separator_niejednoznaczny` mówi wprost, kiedy zapis nie daje pewności —
wtedy pewność propozycji spada i decyduje człowiek.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

#: Wszystkie odmiany spacji, które trafiają do dokumentów jako separator
#: tysięcy: zwykła, niełamiąca, wąska niełamiąca i cienka. Word wstawia
#: niełamiącą, PDF potrafi wstawić każdą z nich.
SPACJE = "    "

#: Kody walut i ich zapisy w tekście. Klucz to kod ISO 4217, który idzie
#: do bazy — `Kwota` przyjmuje wyłącznie trzyliterowy kod.
WALUTY: dict[str, tuple[str, ...]] = {
    "PLN": ("zł", "zl", "PLN", "złotych", "złote", "złotymi", "złotego"),
    "EUR": ("EUR", "€", "euro"),
    "USD": ("USD", "$", "dolarów"),
}

#: Liczebniki wielokrotne. Reguła R5: wartość weksla bywa zapisana jako
#: „czterokrotność czynszu", nigdy jako liczba. Bez tego słownika reguła
#: nie ma z czego policzyć wartości zabezpieczenia.
KROTNOSCI: dict[str, int] = {
    "jednokrotność": 1,
    "dwukrotność": 2,
    "trzykrotność": 3,
    "czterokrotność": 4,
    "pięciokrotność": 5,
    "sześciokrotność": 6,
    "siedmiokrotność": 7,
    "ośmiokrotność": 8,
    "dziewięciokrotność": 9,
    "dziesięciokrotność": 10,
    "dwunastokrotność": 12,
}

#: Liczebniki porządkowe w dopełniaczu, tak jak stoją w zapisie o terminie
#: płatności: „do dziesiątego dnia każdego miesiąca".
DNI_SLOWNIE: dict[str, int] = {
    "pierwszego": 1,
    "drugiego": 2,
    "trzeciego": 3,
    "czwartego": 4,
    "piątego": 5,
    "szóstego": 6,
    "siódmego": 7,
    "ósmego": 8,
    "dziewiątego": 9,
    "dziesiątego": 10,
    "jedenastego": 11,
    "dwunastego": 12,
    "trzynastego": 13,
    "czternastego": 14,
    "piętnastego": 15,
    "dwudziestego": 20,
    "dwudziestego piątego": 25,
    "ostatniego": 31,
}


@dataclass(frozen=True)
class Trafienie[T]:
    """Wartość znaleziona w tekście wraz z miejscem, w którym stała.

    `od` i `do` to offsety w tekście, który podano na wejściu. Trafiają
    do `parametr_wartosc.zrodlo_offset_od` i `..._do`, a ekran weryfikacji
    podświetla na ich podstawie fragment dokumentu.
    """

    wartosc: T
    od: int
    do: int
    tekst: str


@dataclass(frozen=True)
class KwotaSurowa:
    """Kwota tak, jak stoi w dokumencie: liczba i waluta, bez interpretacji.

    Świadomie **nie** jest to `domena.pieniadze.Kwota`. Tamta wymaga jeszcze
    informacji netto/brutto i stawki VAT, a tego z samej liczby nie widać —
    to wynika ze zdania obok i ustala je warstwa wzorców. Kwota bez tych
    trzech informacji nie jest kwotą, więc nie udajemy, że już ją mamy.
    """

    wartosc: Decimal
    waluta: str


#: Sama liczba: grupy tysięcy rozdzielone spacją albo kropką, część dziesiętna
#: po przecinku albo kropce. Dopuszczamy też zapis bez grupowania.
_LICZBA = (
    r"\d{1,3}(?:[" + SPACJE + r"\.]\d{3})+(?:[,\.]\d{1,2})?"
    r"|\d+(?:[,\.]\d+)?"
)

_WZORZEC_LICZBY = re.compile(_LICZBA)

_WZORZEC_KWOTY = re.compile(
    r"(?P<liczba>"
    + _LICZBA
    + r")\s*(?P<waluta>"
    + "|".join(
        re.escape(zapis)
        for zapisy in WALUTY.values()
        for zapis in sorted(zapisy, key=len, reverse=True)
    )
    + r")(?![\w])",
    re.IGNORECASE,
)

_WZORZEC_PROCENTU = re.compile(r"(?P<liczba>" + _LICZBA + r")\s*(?:%|procent)")

#: „do 10-go dnia", „do 10 dnia", „do 10. dnia", „płatny do 15-tego".
_WZORZEC_DNIA = re.compile(
    r"(?P<dzien>\d{1,2})\s*(?:-?\s*(?:go|tego|ego)|\.)?\s*dnia",
    re.IGNORECASE,
)

_ZAPIS_WALUTY: dict[str, str] = {
    zapis.casefold(): kod for kod, zapisy in WALUTY.items() for zapis in zapisy
}


def _bez_spacji(tekst: str) -> str:
    for spacja in SPACJE:
        tekst = tekst.replace(spacja, "")
    return tekst


def separator_niejednoznaczny(surowy: str) -> bool:
    """Czy zapis liczby nie rozstrzyga, czym jest kropka.

    Niejednoznaczne jest dokładnie jedno: jedna kropka, po niej dokładnie
    trzy cyfry i brak przecinka w całym zapisie. „6.960" to po polsku 6960,
    po angielsku 6,96 — a obu odczytów nie da się rozróżnić z samego zapisu.
    Wszystko inne rozstrzyga się jednoznacznie:

    * „6.960,00" — przecinek jest dziesiętny, więc kropka jest tysięczna,
    * „10.5" — po kropce jedna cyfra, więc kropka jest dziesiętna,
    * „1.234.567" — dwie kropki, więc obie są tysięczne.
    """
    czysty = _bez_spacji(surowy)
    if "," in czysty:
        return False
    czesci = czysty.split(".")
    return len(czesci) == 2 and len(czesci[1]) == 3


def czytaj_liczbe(surowy: str) -> Decimal | None:
    """Liczba z napisu albo None, gdy to nie jest liczba.

    Zasada rozstrzygająca kropkę, w tej kolejności:

    1. Jest przecinek → przecinek jest dziesiętny, kropki są tysięczne.
    2. Nie ma przecinka, a każda grupa po kropce ma dokładnie trzy cyfry
       → kropki są tysięczne (zapis polski).
    3. W pozostałych wypadkach kropka jest dziesiętna.

    Punkt 2 jest tym miejscem, gdzie świadomie wybieramy odczyt polski.
    `separator_niejednoznaczny` mówi, kiedy ten wybór był wyborem, a nie
    wnioskiem — warstwa pewności obniża wtedy ocenę propozycji.
    """
    czysty = _bez_spacji(surowy).strip()
    if not czysty:
        return None

    if "," in czysty:
        czysty = czysty.replace(".", "").replace(",", ".")
    elif "." in czysty:
        czesci = czysty.split(".")
        if all(len(czesc) == 3 for czesc in czesci[1:]):
            czysty = "".join(czesci)

    try:
        return Decimal(czysty)
    except InvalidOperation:
        return None


def znajdz_liczby(tekst: str) -> list[Trafienie[Decimal]]:
    """Wszystkie liczby w tekście, w kolejności występowania."""
    trafienia: list[Trafienie[Decimal]] = []
    for dopasowanie in _WZORZEC_LICZBY.finditer(tekst):
        wartosc = czytaj_liczbe(dopasowanie.group())
        if wartosc is not None:
            trafienia.append(
                Trafienie(wartosc, dopasowanie.start(), dopasowanie.end(), dopasowanie.group())
            )
    return trafienia


def znajdz_kwoty(tekst: str) -> list[Trafienie[KwotaSurowa]]:
    """Kwoty wraz z walutą.

    Waluta jest wynikiem, a nie założeniem. Punkt B z `docs/postep.md` pyta,
    czy istnieją umowy w EUR — jeśli tak, ekstrakcja pokaże to na pierwszej
    przetworzonej umowie, zamiast czekać na czyjąś pamięć.
    """
    trafienia: list[Trafienie[KwotaSurowa]] = []
    for dopasowanie in _WZORZEC_KWOTY.finditer(tekst):
        # Wzorzec dopuszcza zapisy, które nie są liczbą: „1.234.56" przechodzi
        # przez grupowanie tysięcy, ale nie da się go odczytać ani po polsku,
        # ani po angielsku. Takiego zapisu nie zgadujemy — pomijamy go.
        wartosc = czytaj_liczbe(dopasowanie.group("liczba"))
        if wartosc is None:
            continue
        # Indeksowanie wprost, nie `.get`: alternatywa w tym wzorcu jest zbudowana
        # z tego samego słownika, więc brak klucza znaczyłby błąd w kodzie,
        # a nie nierozpoznaną walutę. Cichy `continue` by go ukrył.
        kod = _ZAPIS_WALUTY[dopasowanie.group("waluta").casefold()]
        trafienia.append(
            Trafienie(
                KwotaSurowa(wartosc, kod),
                dopasowanie.start(),
                dopasowanie.end(),
                dopasowanie.group(),
            )
        )
    return trafienia


def znajdz_procenty(tekst: str) -> list[Trafienie[Decimal]]:
    """Wartości procentowe. Podstawa wskaźnika waloryzacji i stawki VAT."""
    trafienia: list[Trafienie[Decimal]] = []
    for dopasowanie in _WZORZEC_PROCENTU.finditer(tekst):
        wartosc = czytaj_liczbe(dopasowanie.group("liczba"))
        if wartosc is not None:
            trafienia.append(
                Trafienie(wartosc, dopasowanie.start(), dopasowanie.end(), dopasowanie.group())
            )
    return trafienia


def znajdz_krotnosci(tekst: str) -> list[Trafienie[int]]:
    """Liczebniki wielokrotne: „czterokrotność czynszu" → 4 (reguła R5)."""
    trafienia: list[Trafienie[int]] = []
    obnizony = tekst.casefold()
    for slowo, mnoznik in KROTNOSCI.items():
        poczatek = 0
        while (miejsce := obnizony.find(slowo, poczatek)) != -1:
            koniec = miejsce + len(slowo)
            trafienia.append(Trafienie(mnoznik, miejsce, koniec, tekst[miejsce:koniec]))
            poczatek = koniec
    return sorted(trafienia, key=lambda t: t.od)


def znajdz_dni_platnosci(tekst: str) -> list[Trafienie[int]]:
    """Dzień miesiąca z zapisu o terminie płatności (reguła R3).

    Rozpoznaje zapis cyfrowy („do 10-go dnia") i słowny („do dziesiątego
    dnia miesiąca"). Dni spoza zakresu 1–31 odrzucamy w ciszy: to nie jest
    dzień miesiąca, tylko liczba, która przypadkiem stoi przed słowem „dnia"
    („w terminie 45 dnia" nie istnieje, ale „w ciągu 45 dni" już tak).
    """
    trafienia: list[Trafienie[int]] = []

    for dopasowanie in _WZORZEC_DNIA.finditer(tekst):
        dzien = int(dopasowanie.group("dzien"))
        if 1 <= dzien <= 31:
            trafienia.append(
                Trafienie(dzien, dopasowanie.start(), dopasowanie.end(), dopasowanie.group())
            )

    obnizony = tekst.casefold()
    # Dłuższe zapisy pierwsze, żeby „dwudziestego piątego" nie zostało
    # rozpoznane jako samo „dwudziestego".
    for slowo in sorted(DNI_SLOWNIE, key=len, reverse=True):
        poczatek = 0
        while (miejsce := obnizony.find(slowo, poczatek)) != -1:
            koniec = miejsce + len(slowo)
            poczatek = koniec
            if any(t.od <= miejsce < t.do for t in trafienia):
                continue
            trafienia.append(Trafienie(DNI_SLOWNIE[slowo], miejsce, koniec, tekst[miejsce:koniec]))

    return sorted(trafienia, key=lambda t: t.od)
