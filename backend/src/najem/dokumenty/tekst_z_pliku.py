"""Odczyt tekstu z pliku dokumentu. Jedyne miejsce, które zna formaty plików.

Warstwa infrastruktury: tu wolno mieć zależności i tu wolno dotykać dysku.
Wynikiem jest `TekstDokumentu` z warstwy domenowej, więc wszystko powyżej
pracuje na napisach i nie wie, czy przyszły z PDF-a, DOCX-a czy z OCR-a.

Granica jest celowa i pilnuje jej `tests/domena/test_granice_warstw.py`:
gdyby `pypdf` trafił do `domena/`, wzorców nie dałoby się testować bez pliku.

Czego tu nie ma i dlaczego:

* **OCR** — dochodzi jako kolejna implementacja `CzytnikTekstu`, dopiero gdy
  `narzedzia/sprawdz-dokumenty.py` pokaże, że w archiwum faktycznie są skany.
  Reszta systemu nie zauważy różnicy poza obniżoną pewnością propozycji.
* **stary `.doc`** — binarny format Worda sprzed 2007. Odczytanie go bez
  ciężkich narzędzi jest praktycznie niewykonalne, więc mówimy o tym wprost
  zamiast po cichu zwracać pustkę nie do odróżnienia od skanu.
"""

import zipfile
from pathlib import Path
from typing import Protocol
from xml.etree import ElementTree

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from najem.domena.ekstrakcja.tekst import (
    StronaTekstu,
    TekstDokumentu,
    WarstwaTekstu,
    normalizuj,
)

#: Przestrzeń nazw głównej treści dokumentu DOCX.
_PRZESTRZEN_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: Akapit, wiersz tekstu, złamanie wiersza i tabulator w DOCX.
_AKAPIT = f"{_PRZESTRZEN_WORD}p"
_TEKST = f"{_PRZESTRZEN_WORD}t"
_ZLAMANIE = f"{_PRZESTRZEN_WORD}br"
_TABULATOR = f"{_PRZESTRZEN_WORD}tab"


class BladOdczytuTekstu(Exception):
    """Pliku nie da się odczytać. Komunikat idzie do użytkownika, więc po polsku."""


class CzytnikTekstu(Protocol):
    """Wspólny kształt czytnika. Nowy format to nowa implementacja, nic więcej."""

    def obsluguje(self, sciezka: Path) -> bool: ...

    def czytaj(self, sciezka: Path) -> TekstDokumentu: ...


class CzytnikPdf:
    """Tekst z warstwy tekstowej PDF-a.

    Nie robi OCR-a. PDF ze skanera zwróci strony bez tekstu i taki wynik jest
    poprawny — `TekstDokumentu.pusty` mówi o tym wprost, a warstwa wyżej
    zamienia to na jawny status dokumentu zamiast na milczącą pustkę.

    Strony numerujemy od jedynki, bo tak numeruje je człowiek otwierający
    dokument, a numer trafia do `parametr_wartosc.zrodlo_strona` i ma
    prowadzić go do właściwej kartki.
    """

    def obsluguje(self, sciezka: Path) -> bool:
        return sciezka.suffix.lower() == ".pdf"

    def czytaj(self, sciezka: Path) -> TekstDokumentu:
        try:
            czytnik = PdfReader(sciezka)
            strony = tuple(
                StronaTekstu(numer, normalizuj(strona.extract_text() or ""))
                for numer, strona in enumerate(czytnik.pages, start=1)
            )
        except (PyPdfError, OSError, ValueError) as blad:
            raise BladOdczytuTekstu(f"Nie udało się odczytać pliku PDF: {blad}") from blad

        if not strony:
            raise BladOdczytuTekstu("Plik PDF nie zawiera żadnej strony.")
        return TekstDokumentu(strony=strony, warstwa=WarstwaTekstu.PDF_TEKST)


class CzytnikDocx:
    """Tekst z DOCX-a, samą standardową biblioteką.

    DOCX to archiwum ZIP, w którym treść leży w `word/document.xml`. Program
    już dziś zagląda do tego archiwum przy rozpoznawaniu typu pliku
    (`dokumenty/przechowalnia.py`), więc nie dokładamy zależności po to,
    żeby przeczytać z niego tekst.

    Dokument ma jedną stronę o numerze 1, bo DOCX **nie niesie podziału
    na strony** — powstaje on dopiero przy składaniu przez edytor i zależy
    od zainstalowanych czcionek. Zmyślony podział byłby informacją, której
    w pliku nie ma (decyzja D5).
    """

    def obsluguje(self, sciezka: Path) -> bool:
        return sciezka.suffix.lower() == ".docx"

    def czytaj(self, sciezka: Path) -> TekstDokumentu:
        try:
            with zipfile.ZipFile(sciezka) as archiwum:
                surowy_xml = archiwum.read("word/document.xml")
        except (OSError, zipfile.BadZipFile) as blad:
            raise BladOdczytuTekstu(f"Nie udało się otworzyć pliku DOCX: {blad}") from blad
        except KeyError as blad:
            raise BladOdczytuTekstu(
                "Plik DOCX nie zawiera treści dokumentu (brak word/document.xml)."
            ) from blad

        try:
            drzewo = ElementTree.fromstring(surowy_xml)
        except ElementTree.ParseError as blad:
            raise BladOdczytuTekstu(f"Treść pliku DOCX jest uszkodzona: {blad}") from blad

        akapity = [self._akapit_na_tekst(akapit) for akapit in drzewo.iter(_AKAPIT)]
        tekst = normalizuj("\n".join(akapity))
        return TekstDokumentu(strony=(StronaTekstu(1, tekst),), warstwa=WarstwaTekstu.DOCX)

    @staticmethod
    def _akapit_na_tekst(akapit: ElementTree.Element) -> str:
        """Jeden akapit sklejony z fragmentów.

        Word tnie akapit na fragmenty przy każdej zmianie formatowania, więc
        pogrubienie jednego słowa rozbija zdanie na trzy elementy. Bez sklejenia
        „czynsz **6 960,00 zł** netto" rozpadłoby się na kawałki i żaden wzorzec
        nie zobaczyłby całego zapisu.
        """
        czesci: list[str] = []
        for element in akapit.iter():
            if element.tag == _TEKST and element.text:
                czesci.append(element.text)
            elif element.tag in (_ZLAMANIE, _TABULATOR):
                czesci.append(" ")
        return "".join(czesci)


class CzytnikStaregoDoc:
    """Stary binarny `.doc`. Nie czytamy go i mówimy o tym wprost.

    Format OLE2 sprzed 2007 roku trzyma tekst w strumieniu binarnym wymieszanym
    z formatowaniem. Wyciągnięcie go bez ciężkiej biblioteki daje wynik, któremu
    nie można ufać przy kwotach — a milczące zwrócenie pustki byłoby nie do
    odróżnienia od skanu i wysłałoby człowieka szukać OCR-a zamiast kazać mu
    zapisać plik ponownie.
    """

    def obsluguje(self, sciezka: Path) -> bool:
        return sciezka.suffix.lower() == ".doc"

    def czytaj(self, sciezka: Path) -> TekstDokumentu:
        raise BladOdczytuTekstu(
            "Stary format .doc nie jest obsługiwany. Otwórz dokument w Wordzie "
            "i zapisz go jako PDF albo DOCX, potem wczytaj ponownie."
        )


#: Kolejność nie ma znaczenia — czytniki rozpoznają się po rozszerzeniu
#: i nie zachodzą na siebie.
CZYTNIKI: tuple[CzytnikTekstu, ...] = (CzytnikPdf(), CzytnikDocx(), CzytnikStaregoDoc())


def czytaj_tekst(sciezka: Path, czytniki: tuple[CzytnikTekstu, ...] = CZYTNIKI) -> TekstDokumentu:
    """Tekst dokumentu spod wskazanej ścieżki.

    Format rozpoznajemy po rozszerzeniu, nie po zawartości — inaczej niż przy
    wgrywaniu pliku, gdzie rozszerzenie jest deklaracją nadawcy i sprawdzamy
    sygnaturę. Tutaj plik jest już w systemie i jego typ został potwierdzony
    przy przyjęciu (`dokumenty/przechowalnia.py`).
    """
    for czytnik in czytniki:
        if czytnik.obsluguje(sciezka):
            return czytnik.czytaj(sciezka)
    raise BladOdczytuTekstu(
        f"Nie umiemy odczytać tekstu z pliku o rozszerzeniu {sciezka.suffix!r}. "
        "Obsługiwane formaty to PDF i DOCX."
    )
