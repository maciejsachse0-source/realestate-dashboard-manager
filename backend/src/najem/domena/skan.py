"""Rozpoznawanie dokumentow po nazwie pliku.

Czysty Python, zero I/O. Funkcje dostaja nazwe pliku jako tekst i zwracaja
propozycje, ktora czlowiek zatwierdza albo poprawia (decyzja D4).

Do etapu E9 system nie czyta tresci dokumentow. Nazwa pliku to jedyna
przeslanka, jaka mamy, i traktujemy ja jako przeslanke, a nie jako fakt:
gdy nic nie pasuje albo pasuje dwuznacznie, zwracamy None. Podstawienie
"umowa" pod kazdy nierozpoznany plik byloby zamiana braku danych w fakt
(decyzja D5).
"""

import re
import unicodedata

from najem.domena.slowniki import TypDokumentu

#: Rozszerzenia, ktore w ogole moga byc dokumentem umowy.
#: Rozpoznanie typu pliku i tak idzie po zawartosci przy imporcie
#: (dokumenty/przechowalnia.py). Tutaj chodzi wylacznie o to, zeby nie
#: pokazywac czlowiekowi listy zlozonej z plikow tymczasowych Worda.
ROZSZERZENIA_DOKUMENTOW: frozenset[str] = frozenset(
    {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
)


def bez_ogonkow(tekst: str) -> str:
    """Tekst do porownan: male litery, bez znakow diakrytycznych.

    Nazwy plikow bywaja i z ogonkami, i bez ("protokół" obok "protokol"),
    a czasem z polskimi znakami rozbitymi na dwa punkty kodowe przez system
    plikow. Porownania robimy na jednej, ustalonej postaci.
    """
    rozlozony = unicodedata.normalize("NFKD", tekst.lower())
    # Litera "ł" nie rozklada sie na "l" plus znak lacz\u0105cy, wiec sama
    # normalizacja jej nie zdejmie. Stad podmiana przed odsianiem znakow.
    rozlozony = rozlozony.replace("\u0142", "l")
    return "".join(znak for znak in rozlozony if not unicodedata.combining(znak))


#: Wzorce sprawdzane po kolei. Pierwszy trafiony wygrywa, wiec kolejnosc
#: jest czescia zasady: "aneks do umowy najmu" to aneks, nie umowa.
_WZORCE: tuple[tuple[re.Pattern[str], TypDokumentu], ...] = (
    (re.compile(r"aneks"), TypDokumentu.ANEKS),
    (re.compile(r"wypowiedzeni|rozwiazani"), TypDokumentu.WYPOWIEDZENIE),
    (re.compile(r"polis|ubezpiecz|oc\b"), TypDokumentu.POLISA),
    (re.compile(r"przekazani|wydani|odbior lokalu"), TypDokumentu.PROTOKOL_PRZEKAZANIA),
    (re.compile(r"zdawcz|zwrot lokalu|zwrotu lokalu"), TypDokumentu.PROTOKOL_ZDAWCZY),
    (re.compile(r"przegl|serwis|konserwacj|pomiar"), TypDokumentu.PROTOKOL_PRZEGLADU),
    (re.compile(r"umow|najm|dzierzaw"), TypDokumentu.UMOWA),
)

#: Nazwy, ktore pasuja do dwoch typow naraz i zadne dopasowanie nie jest
#: uczciwe. "Protokol zdawczo-odbiorczy" bywa i przy wydaniu lokalu,
#: i przy jego zwrocie -- z samej nazwy nie da sie tego rozstrzygnac.
_DWUZNACZNE: tuple[re.Pattern[str], ...] = (re.compile(r"zdawczo[\s-]*odbior"),)


def _bez_rozszerzenia(nazwa_pliku: str) -> str:
    kropka = nazwa_pliku.rfind(".")
    return nazwa_pliku[:kropka] if kropka > 0 else nazwa_pliku


def rozpoznaj_typ_z_nazwy(nazwa_pliku: str) -> TypDokumentu | None:
    """Proponowany typ dokumentu albo None, gdy nazwa nic nie mowi.

    None znaczy "nie wiem", a nie "inne". Czlowiek wybiera typ sam,
    a interfejs ma go o to poprosic, zamiast podstawiac wartosc domyslna.
    """
    # Rozszerzenie odcinamy przed dopasowaniem, bo samo w sobie potrafi
    # trafic we wzorzec: w "umowa.doc" konczowka wyglada jak skrot "OC".
    tekst = bez_ogonkow(_bez_rozszerzenia(nazwa_pliku))

    for wzorzec in _DWUZNACZNE:
        if wzorzec.search(tekst):
            return None

    for wzorzec, typ in _WZORCE:
        if wzorzec.search(tekst):
            return typ
    return None


#: "Aneks nr 3", "aneks 3", "Aneks nr. 03", "aneks_2_do_umowy".
_NUMER_ANEKSU = re.compile(r"aneks\w*[\s_.-]*(?:nr\.?|numer)?[\s_.-]*(\d{1,3})\b")


def numer_z_nazwy(nazwa_pliku: str) -> str | None:
    """Numer aneksu wyciagniety z nazwy pliku albo None.

    Numeracja aneksow w nazwach jest u uzytkownika prowadzona rzetelnie,
    wiec warto ja podpowiedziec. Zera wiodace zdejmujemy, zeby "03" i "3"
    nie wygladaly w systemie na dwa rozne aneksy.
    """
    trafienie = _NUMER_ANEKSU.search(bez_ogonkow(nazwa_pliku))
    if trafienie is None:
        return None
    return str(int(trafienie.group(1)))


def czy_plik_dokumentu(nazwa_pliku: str) -> bool:
    """Czy plik o tej nazwie ma sens jako dokument do zaimportowania.

    Odsiewamy pliki ukryte i tymczasowe Worda ("~$umowa.docx"), bo one nie sa
    dokumentem, tylko sladem po otwartym edytorze.
    """
    if nazwa_pliku.startswith(".") or nazwa_pliku.startswith("~$"):
        return False
    kropka = nazwa_pliku.rfind(".")
    if kropka <= 0:
        return False
    return nazwa_pliku[kropka:].lower() in ROZSZERZENIA_DOKUMENTOW
