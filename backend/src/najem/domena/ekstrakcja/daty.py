"""Daty i terminy z polskiego tekstu umowy.

Czysty Python, zero I/O. Żadna funkcja w tym pliku nie woła `date.today()` —
data odniesienia zawsze wchodzi argumentem. Bez tego terminu względnego
(„14 dni od dnia przekazania") nie da się przetestować deterministycznie,
a test, który zmienia wynik jutro, nie jest testem.

Data zapisana w dokumencie jest **datą biznesową**, więc `date`, nigdy
`datetime`. Doklejenie godziny do daty przekazania lokalu daje błąd o jeden
dzień na przełomie miesiąca, kiedy ktoś przeliczy to na inną strefę.

Zapis DD.MM.RRRR czytamy po polsku: pierwsza liczba to dzień. To nie jest
zgadywanie — to konwencja obowiązująca w polskim dokumencie. Zapis ISO
(RRRR-MM-DD) rozpoznajemy po czterocyfrowym roku na początku.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

#: Miesiące w dopełniaczu — tak, jak stoją w dacie: „1 marca 2027 r.".
MIESIACE_DOPELNIACZ: dict[str, int] = {
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "wrzesnia": 9,
    "października": 10,
    "pazdziernika": 10,
    "listopada": 11,
    "grudnia": 12,
}

#: Miesiące w mianowniku — w nagłówkach tabel i w zapisie o waloryzacji
#: („waloryzacja w miesiącu styczeń").
MIESIACE_MIANOWNIK: dict[str, int] = {
    "styczeń": 1,
    "styczen": 1,
    "luty": 2,
    "marzec": 3,
    "kwiecień": 4,
    "kwiecien": 4,
    "maj": 5,
    "czerwiec": 6,
    "lipiec": 7,
    "sierpień": 8,
    "sierpien": 8,
    "wrzesień": 9,
    "wrzesien": 9,
    "październik": 10,
    "pazdziernik": 10,
    "listopad": 11,
    "grudzień": 12,
    "grudzien": 12,
}

#: Miesiące w miejscowniku — najczęstszy zapis o waloryzacji:
#: „waloryzacja następuje w styczniu".
MIESIACE_MIEJSCOWNIK: dict[str, int] = {
    "styczniu": 1,
    "lutym": 2,
    "marcu": 3,
    "kwietniu": 4,
    "maju": 5,
    "czerwcu": 6,
    "lipcu": 7,
    "sierpniu": 8,
    "wrześniu": 9,
    "wrzesniu": 9,
    "październiku": 10,
    "pazdzierniku": 10,
    "listopadzie": 11,
    "grudniu": 12,
}

#: Wszystkie rozpoznawane formy nazw miesięcy naraz.
MIESIACE: dict[str, int] = {
    **MIESIACE_MIANOWNIK,
    **MIESIACE_DOPELNIACZ,
    **MIESIACE_MIEJSCOWNIK,
}


#: Punkty odniesienia dla terminów względnych. Wartość to klucz zdarzenia,
#: od którego liczy się termin — rozwiązuje go dopiero warstwa usług,
#: bo tylko ona zna daty tej konkretnej umowy.
PUNKTY_ODNIESIENIA: dict[str, str] = {
    "przekazania": "data_przekazania",
    "wydania": "data_przekazania",
    "protokołu przekazania": "data_przekazania",
    "zawarcia": "data_zawarcia",
    "podpisania": "data_zawarcia",
    "zakończenia": "data_zakonczenia",
    "rozwiązania": "data_zakonczenia",
    "zwrotu lokalu": "data_zakonczenia",
}

#: Za rokiem stoi zakaz kolejnej cyfry, a nie granica słowa. Polskie umowy
#: piszą „30.06.2019r." bez spacji, a między cyfrą a literą granicy słowa nie
#: ma, więc taka data przepadała w całości. Samo \b myli się tu w obie strony:
#: albo gubi „2019r.", albo wpuszcza „01.03.20275" jako rok 2027.
_WZORZEC_KROPKOWY = re.compile(r"\b(?P<d>\d{1,2})[.\-/](?P<m>\d{1,2})[.\-/](?P<r>\d{4})(?!\d)")
_WZORZEC_ISO = re.compile(r"\b(?P<r>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b")
_WZORZEC_SLOWNY = re.compile(
    r"\b(?P<d>\d{1,2})\s+(?P<m>" + "|".join(MIESIACE_DOPELNIACZ) + r")\s+(?P<r>\d{4})",
    re.IGNORECASE,
)

#: „w terminie 14 dni od dnia przekazania lokalu", „w ciągu 30 dni od zawarcia",
#: „w terminie 14 dni od daty przekazania Obiektu stosowne polisy".
#:
#: Po „od" bierzemy najwyżej trzy słowa i dopiero one są rozstrzygane słownikiem
#: punktów odniesienia. Wcześniejszy wariant kończył dopasowanie przecinkiem albo
#: słowem „lokalu" i przez to nie widział ani terminu polisy (R6), ani kaucji (R4):
#: w prawdziwej umowie po punkcie odniesienia stoi dalszy ciąg zdania, nie kropka.
_WZORZEC_TERMINU = re.compile(
    r"(?:w\s+terminie|w\s+ciągu|nie\s+później\s+niż\s+w\s+terminie)\s+"
    r"(?P<dni>\d{1,3})\s+dni\s+(?:od|po)\s+(?:dnia|daty|chwili)?\s*"
    r"(?P<odniesienie>\w+(?:\s+\w+){0,2})",
    re.IGNORECASE,
)

#: Pojedyncze słowo wewnątrz dopasowanego punktu odniesienia. Potrzebne, żeby
#: przyciąć koniec trafienia dokładnie tam, gdzie kończy się rozpoznana nazwa.
_SLOWO = re.compile(r"\S+")

#: „na czas określony 24 miesięcy", „na okres 36 miesięcy", „na 24 miesiące".
_WZORZEC_OKRESU_MIESIACE = re.compile(
    r"(?P<ile>\d{1,3})\s*(?:\([^)]{0,60}\)\s*)?miesi(?:ęcy|ące|ąca|ecy|ace)",
    re.IGNORECASE,
)

#: „na okres 3 lat", „na 2 lata". Zamieniamy na miesiące, bo tak liczy R1.
_WZORZEC_OKRESU_LATA = re.compile(
    r"(?P<ile>\d{1,2})\s*(?:\([^)]{0,60}\)\s*)?(?:lat|lata|roku|rok)\b",
    re.IGNORECASE,
)


#: Nazwy miesięcy z granicami słowa. Dłuższe formy pierwsze, żeby „stycznia"
#: nie zostało obcięte do „styczeń" na wcześniejszym wariancie.
_WZORZEC_MIESIACA = re.compile(
    r"\b(?:" + "|".join(sorted(MIESIACE, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TrafienieDaty:
    """Data znaleziona w tekście wraz z pozycją i zapisem, z którego wynika."""

    wartosc: date
    od: int
    do: int
    tekst: str


@dataclass(frozen=True)
class TerminWzgledny:
    """Termin liczony od zdarzenia, a nie podany wprost.

    Umowy prawie nigdy nie piszą „polisę należy dostarczyć do 15.03.2027".
    Piszą „w terminie 14 dni od dnia przekazania lokalu". Konkretną datę
    da się z tego policzyć dopiero, gdy znana jest data przekazania —
    a ta bywa nieustalona (reguła R1, decyzja D5).
    """

    dni: int
    #: Klucz daty, od której liczymy: `data_przekazania`, `data_zawarcia`,
    #: `data_zakonczenia`. Rozwiązuje go warstwa, która zna tę umowę.
    odniesienie: str
    od: int
    do: int
    tekst: str


def zbuduj_date(rok: int, miesiac: int, dzien: int) -> date | None:
    """Data albo None, gdy taki dzień nie istnieje.

    31 lutego i 29 lutego roku nieprzestępnego dają None, a nie wyjątek
    i nie cichą korektę na 28. Data z literówką ma zostać zauważona,
    a nie po cichu naprawiona na sąsiedni dzień.
    """
    try:
        return date(rok, miesiac, dzien)
    except ValueError:
        return None


def znajdz_daty(tekst: str) -> list[TrafienieDaty]:
    """Wszystkie daty w tekście, w kolejności występowania, bez duplikatów.

    Rozpoznaje trzy zapisy: kropkowy (01.03.2027), ISO (2027-03-01)
    i słowny (1 marca 2027). Zapis kropkowy czytamy jako dzień-miesiąc-rok,
    zgodnie z polską konwencją.
    """
    trafienia: list[TrafienieDaty] = []
    zajete: list[tuple[int, int]] = []

    def dodaj(wartosc: date | None, poczatek: int, koniec: int, zapis: str) -> None:
        if wartosc is None:
            return
        if any(p < koniec and poczatek < k for p, k in zajete):
            return
        zajete.append((poczatek, koniec))
        trafienia.append(TrafienieDaty(wartosc, poczatek, koniec, zapis))

    # ISO pierwszy: czterocyfrowy rok na początku rozstrzyga jednoznacznie
    # i nie chcemy, żeby wzorzec kropkowy złapał kawałek tego zapisu.
    for dop in _WZORZEC_ISO.finditer(tekst):
        dodaj(
            zbuduj_date(int(dop.group("r")), int(dop.group("m")), int(dop.group("d"))),
            dop.start(),
            dop.end(),
            dop.group(),
        )

    for dop in _WZORZEC_SLOWNY.finditer(tekst):
        miesiac = MIESIACE_DOPELNIACZ[dop.group("m").casefold()]
        dodaj(
            zbuduj_date(int(dop.group("r")), miesiac, int(dop.group("d"))),
            dop.start(),
            dop.end(),
            dop.group(),
        )

    for dop in _WZORZEC_KROPKOWY.finditer(tekst):
        dodaj(
            zbuduj_date(int(dop.group("r")), int(dop.group("m")), int(dop.group("d"))),
            dop.start(),
            dop.end(),
            dop.group(),
        )

    return sorted(trafienia, key=lambda t: t.od)


def znajdz_terminy_wzgledne(tekst: str) -> list[TerminWzgledny]:
    """Terminy liczone od zdarzenia: „w terminie 14 dni od dnia przekazania".

    Zwraca liczbę dni i klucz punktu odniesienia. Terminu, którego punktu
    odniesienia nie rozpoznajemy, nie zwracamy w ogóle — „14 dni od czegoś"
    to nie jest termin, tylko liczba, a podstawienie pod nią daty zawarcia
    byłoby zgadywaniem (decyzja D5).
    """
    terminy: list[TerminWzgledny] = []
    for dop in _WZORZEC_TERMINU.finditer(tekst):
        granice = [(m.start(), m.end()) for m in _SLOWO.finditer(dop.group("odniesienie"))]
        slowa = [dop.group("odniesienie")[p:k].casefold() for p, k in granice]

        # Najdłuższy pasujący początek wygrywa: „protokołu przekazania" bije
        # samo „przekazania", a „zwrotu lokalu" bije „zwrotu". Reszta zdania
        # odpada, bo nie ma prawa zmienić punktu odniesienia.
        klucz: str | None = None
        ile_slow = 0
        for ile in range(len(slowa), 0, -1):
            klucz = PUNKTY_ODNIESIENIA.get(" ".join(slowa[:ile]))
            if klucz is not None:
                ile_slow = ile
                break

        if klucz is None:
            continue

        # Koniec trafienia przycinamy do rozpoznanej nazwy, żeby podświetlenie
        # w dokumencie objęło termin, a nie dalszy ciąg zdania.
        koniec = dop.start("odniesienie") + granice[ile_slow - 1][1]
        terminy.append(
            TerminWzgledny(
                int(dop.group("dni")), klucz, dop.start(), koniec, tekst[dop.start() : koniec]
            )
        )
    return terminy


def rozwiaz_termin(termin: TerminWzgledny, data_odniesienia: date) -> date:
    """Konkretna data terminu względnego.

    Dzień odniesienia się nie liczy: „14 dni od dnia przekazania" przy
    przekazaniu 1 marca daje 15 marca. Tak liczy się terminy w prawie
    cywilnym i tak rozumie to każdy, kto czyta umowę.
    """
    return data_odniesienia + timedelta(days=termin.dni)


def znajdz_okresy_najmu(tekst: str) -> list[tuple[int, int, int, str]]:
    """Okres najmu w miesiącach: (miesiące, offset_od, offset_do, zapis).

    Rozpoznaje zapis w miesiącach i w latach, sprowadzając oba do miesięcy,
    bo reguła R1 liczy koniec umowy w miesiącach. Zapis z liczebnikiem
    w nawiasie („24 (dwadzieścia cztery) miesiące") jest w umowach normą,
    więc nawias przeskakujemy.
    """
    wyniki: list[tuple[int, int, int, str]] = []

    for dop in _WZORZEC_OKRESU_MIESIACE.finditer(tekst):
        ile = int(dop.group("ile"))
        if 1 <= ile <= 600:
            wyniki.append((ile, dop.start(), dop.end(), dop.group()))

    # Bez sprawdzania nachodzenia: wzorzec miesięcy kończy się na słowie
    # „miesięcy", a wzorzec lat na „lat" albo „rok", więc dopasowania nie mają
    # jak na siebie wejść. „2 lata i 24 miesiące" daje dwa osobne kandydaty
    # i to jest poprawne — wybór między nimi należy do warstwy wzorców.
    for dop in _WZORZEC_OKRESU_LATA.finditer(tekst):
        ile = int(dop.group("ile"))
        if 1 <= ile <= 50:
            wyniki.append((ile * 12, dop.start(), dop.end(), dop.group()))

    return sorted(wyniki, key=lambda w: w[1])


def znajdz_miesiac_waloryzacji(tekst: str) -> int | None:
    """Miesiąc waloryzacji z zapisu „waloryzacja w styczniu" (reguła R2).

    Zwraca None, gdy w tekście nie ma jednoznacznej nazwy miesiąca. Wariant
    „w miesiącu rocznicy zawarcia umowy" nie jest miesiącem kalendarzowym
    i celowo tu nie wpada — obsługuje go osobne pole modelu.

    Dopasowanie idzie po granicach słów, nie po podciągu. Bez tego „maj"
    trafiałby w „majątek", a „rok" w „rokowania".
    """
    znalezione = {MIESIACE[dop.group().casefold()] for dop in _WZORZEC_MIESIACA.finditer(tekst)}
    # Dwa różne miesiące w jednym zdaniu to nie jest odpowiedź, tylko powód
    # do zapytania człowieka. Zwracamy brak, nie pierwszy z brzegu.
    return znalezione.pop() if len(znalezione) == 1 else None
