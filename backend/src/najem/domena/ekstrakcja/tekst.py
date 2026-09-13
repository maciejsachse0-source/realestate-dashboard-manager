"""Tekst dokumentu: struktura i normalizacja. Czysty Python, zero I/O.

Czytniki plików mieszkają w `dokumenty/tekst_z_pliku.py` i podają tutaj gotowy
napis. Ten moduł nie wie, czy tekst przyszedł z PDF-a, z DOCX-a czy z OCR-a —
wie tylko, że przyszedł, i z której strony.

**Kontrakt offsetów.** Wzorce dostają tekst *po* normalizacji i zwracają
offsety liczone w tym tekście. Ten sam znormalizowany tekst zapisujemy
w tabeli `dokument_tekst`, więc ekran weryfikacji podświetla dokładnie ten
fragment, na którym pracował wzorzec. Gdyby w bazie leżał tekst surowy,
a wzorce działały na znormalizowanym, podświetlenie rozjeżdżałoby się
o kilkanaście znaków przy każdym przeniesieniu wyrazu — i nikt by nie wiedział,
dlaczego.

Znormalizowany tekst jest więc **tekstem źródłowym systemu**, a plik pozostaje
dowodem do wglądu. To ta sama relacja, co między bazą a dokumentem w całym
projekcie: dokument jest źródłem dowodu, nie źródłem prawdy (koncepcja, 1.2).
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class WarstwaTekstu(StrEnum):
    """Skąd wzięliśmy tekst. Wpływa na pewność propozycji, nie na jej treść.

    Rozróżnienie nie jest kosmetyczne. Tekst z warstwy PDF-a albo z DOCX-a
    jest dokładnie tym, co wpisał autor dokumentu. Tekst z OCR-a to odczyt
    obrazu, w którym 0 bywa literą O, a 6 ósemką — i akurat te znaki stoją
    w kwotach. Dlatego pewność propozycji opartej na OCR-ze jest mnożona
    przez współczynnik mniejszy od jedynki (plan E9, sekcja 5).
    """

    PDF_TEKST = "pdf_tekst"
    DOCX = "docx"
    OCR = "ocr"


#: Warstwy, którym ufamy co do znaku. OCR nie należy do tego zbioru.
WARSTWY_DOKLADNE: frozenset[WarstwaTekstu] = frozenset(
    {WarstwaTekstu.PDF_TEKST, WarstwaTekstu.DOCX}
)

#: Miękki dywiz. Word wstawia go jako podpowiedź podziału wyrazu, a w tekście
#: jest niewidoczny — i rozbija dopasowanie wzorca w środku słowa.
MIEKKI_DYWIZ = "­"

#: Ligatury, które PDF potrafi oddać jednym znakiem. „oﬁcjalny" z ligaturą
#: nie dopasuje się do wzorca szukającego „oficjalny".
LIGATURY: dict[str, str] = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
}

#: Wyraz przeniesiony na następny wiersz: „powierzch-\nni" to „powierzchni".
#: Wymagamy małej litery po łączniku, żeby nie skleić „Warszawa-\nMokotów",
#: gdzie łącznik jest częścią nazwy, a nie znakiem przeniesienia.
_PRZENIESIENIE = re.compile(r"(\w)-\s*\n\s*([a-ząćęłńóśźż])")

#: Ciągi spacji i tabulatorów w obrębie wiersza.
_ODSTEPY_W_WIERSZU = re.compile(r"[^\S\n]+")

#: Trzy i więcej złamań wiersza to nadal jeden akapit odstępu.
_NADMIAR_PUSTYCH_WIERSZY = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class StronaTekstu:
    """Jedna strona dokumentu. Numeracja od jedynki, tak jak widzi ją człowiek."""

    numer: int
    tekst: str

    def __post_init__(self) -> None:
        if self.numer < 1:
            raise ValueError(f"Numer strony liczymy od jedynki, otrzymano {self.numer}.")


@dataclass(frozen=True)
class TekstDokumentu:
    """Odczytany dokument w całości, strona po stronie.

    DOCX nie niesie podziału na strony — powstaje on dopiero przy składaniu
    dokumentu przez edytor. Taki dokument ma jedną stronę o numerze 1, i tak
    też jest raportowany. Podstawianie zmyślonego podziału byłoby wymyślaniem
    informacji, której w pliku nie ma (decyzja D5).
    """

    strony: tuple[StronaTekstu, ...]
    warstwa: WarstwaTekstu

    def __post_init__(self) -> None:
        numery = [s.numer for s in self.strony]
        if numery != sorted(numery) or len(set(numery)) != len(numery):
            raise ValueError(f"Strony muszą być kolejne i niepowtarzalne, otrzymano {numery}.")

    @property
    def pusty(self) -> bool:
        """Czy z dokumentu nie dało się wyciągnąć żadnego tekstu.

        Pusty wynik to informacja, nie awaria: tak wygląda skan bez warstwy
        tekstowej. Woła o OCR albo o wprowadzenie ręczne, a nie o wyjątek.
        """
        return all(not s.tekst.strip() for s in self.strony)

    @property
    def liczba_stron(self) -> int:
        return len(self.strony)

    def strona(self, numer: int) -> StronaTekstu | None:
        for s in self.strony:
            if s.numer == numer:
                return s
        return None


def polacz_przeniesienia(tekst: str) -> str:
    """Skleja wyrazy rozbite łącznikiem na granicy wiersza.

    „powierzch-\\nni" to „powierzchni". Bez tego wzorzec szukający słowa
    „powierzchni" nie znajdzie go w co którymś dokumencie, zależnie od tego,
    gdzie akurat wypadł koniec wiersza — czyli od szerokości marginesu.
    """
    return _PRZENIESIENIE.sub(r"\1\2", tekst)


def normalizuj(tekst: str) -> str:
    """Tekst sprowadzony do postaci, na której pracują wzorce.

    Kolejność kroków ma znaczenie: przeniesienia sklejamy przed zwijaniem
    odstępów, bo po zwinięciu złamania wiersza nie da się już rozpoznać.

    Czego ta funkcja **nie** robi: nie usuwa spacji niełamiących wewnątrz
    liczb ani nie zamienia przecinków na kropki. Interpretacja zapisu liczby
    należy do `liczby.py`, gdzie jest jawna i przetestowana. Normalizacja,
    która po drodze „poprawia" kwoty, to najprostszy sposób na zgubienie
    trzech rzędów wielkości.
    """
    # NFKC ujednolica warianty znaków. Dwa skutki, o których trzeba wiedzieć
    # pisząc wzorce, bo inaczej nie dopasują się do niczego:
    #
    #   * wszystkie odmiany spacji (niełamiąca, wąska, cienka) stają się
    #     zwykłą spacją, więc „6 960,00" z Worda i z PDF-a wygląda tak samo;
    #   * „m²" staje się „m2", a „¼" ułamkiem zwykłym.
    #
    # Wzorzec powierzchni ma więc szukać „m2", nie „m²". Ligatury dokładamy
    # osobno, bo NFKC rozwija tylko część z nich.
    tekst = unicodedata.normalize("NFKC", tekst)
    for ligatura, rozwiniecie in LIGATURY.items():
        tekst = tekst.replace(ligatura, rozwiniecie)
    tekst = tekst.replace(MIEKKI_DYWIZ, "")
    tekst = tekst.replace("\r\n", "\n").replace("\r", "\n")
    tekst = polacz_przeniesienia(tekst)
    tekst = _ODSTEPY_W_WIERSZU.sub(" ", tekst)
    tekst = _NADMIAR_PUSTYCH_WIERSZY.sub("\n\n", tekst)
    return "\n".join(wiersz.strip() for wiersz in tekst.split("\n")).strip()
