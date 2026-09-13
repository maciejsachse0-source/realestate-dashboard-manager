"""Co jest w archiwum dokumentów: statystyka formatów i warstw tekstowych.

Etap E9.0 z `docs/plan-e9-ekstrakcja.md`. Odpowiada na jedno pytanie, od którego
zależy zakres całej ekstrakcji i rozmiar paczki wydania:

    czy PDF-y w archiwum mają warstwę tekstową, czy to skany?

PDF wygenerowany z Worda niesie tekst i czyta się go od razu. PDF ze skanera
to obrazek — bez OCR-a jest bezużyteczny, a OCR to kilkaset megabajtów
w instalatorze i osobny etap prac. Zgadywanie tego z góry byłoby kosztowną
pomyłką w obie strony.

**Ten skrypt nie wypisuje treści dokumentów.** Podaje liczby: ile plików,
w jakich formatach, ile stron, ile ma warstwę tekstową. Nazwy plików pokazuje
wyłącznie z jawnym przełącznikiem `--pliki`, bo w nazwie umowy zwykle siedzi
nazwa najemcy, a to tor B (decyzja D3).

Zero zależności zewnętrznych — sam `zipfile`, `zlib` i `re` ze standardowej
biblioteki. Narzędzie diagnostyczne nie ma prawa wymagać instalowania czegoś,
co dopiero rozważamy.

Uruchomienie:

    python narzedzia/sprawdz-dokumenty.py                # katalog z .env
    python narzedzia/sprawdz-dokumenty.py D:/Umowy       # katalog wskazany
    python narzedzia/sprawdz-dokumenty.py D:/Umowy --pliki
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
import zlib
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

#: Rozszerzenia, które w ogóle mogą być dokumentem umowy.
#: Zgodne z `domena/skan.py`, żeby statystyka opisywała to, co program widzi.
ROZSZERZENIA = frozenset({".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"})

#: Ile operatorów tekstu na stronę uznajemy za dowód warstwy tekstowej.
#: Skan bywa opatrzony samą stopką albo numerem strony wstawionym cyfrowo,
#: więc pojedyncze trafienie nie wystarcza. Strona umowy ma ich setki.
PROG_OPERATOROW_NA_STRONE = 5

#: Operatory pokazujące tekst w strumieniu treści PDF: (tekst) Tj, [..] TJ,
#: oraz ' i " dla tekstu z przejściem do nowej linii.
_OPERATORY_TEKSTU = re.compile(rb"(?:Tj|TJ|'|\")[\s]")

#: Węzły stron w drzewie dokumentu. Wykluczamy /Pages, stąd granica słowa.
_WEZEL_STRONY = re.compile(rb"/Type\s*/Page[^s]")

#: Strumienie danych. Nagłówek słownika trzymamy, bo mówi, czy jest FlateDecode.
_STRUMIEN = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)


class Wynik(Enum):
    """Klasyfikacja pliku. Wartość trafia wprost do raportu.

    Zwykły `Enum`, a nie `StrEnum` z reszty projektu, bo ten skrypt ma się
    uruchomić także na komputerze użytkownika, gdzie Python bywa starszy niż
    3.12. Narzędzie diagnostyczne, które samo wymaga aktualizacji Pythona,
    nie zdiagnozuje niczego.
    """

    TEKST = "ma warstwę tekstową"
    SKAN = "skan bez tekstu (wymaga OCR)"
    OBRAZ = "obraz (wymaga OCR)"
    STARY_DOC = "stary .doc (nieobsługiwany)"
    USZKODZONY = "nie da się otworzyć"


#: Klasyfikacje, dla których bez rozpoznawania obrazu nie ma żadnego tekstu.
WYMAGAJA_OCR: frozenset[Wynik] = frozenset({Wynik.SKAN, Wynik.OBRAZ})


@dataclass
class Statystyka:
    """Zliczenia dla całego przebiegu. Bez treści, bez nazw."""

    rozszerzenia: Counter[str] = field(default_factory=Counter)
    klasyfikacja: Counter[Wynik] = field(default_factory=Counter)
    strony_lacznie: int = 0
    strony_z_tekstem: int = 0
    bajty_lacznie: int = 0
    #: Ścieżki zbierane tylko po to, żeby móc je pokazać na żądanie.
    do_ocr: list[Path] = field(default_factory=list)
    katalogi: Counter[str] = field(default_factory=Counter)


def _rozpakuj_strumienie(dane: bytes) -> bytes:
    """Skleja rozpakowaną treść wszystkich strumieni PDF-a.

    Strumienie w PDF-ie są prawie zawsze spakowane FlateDecode, czyli zlib.
    Te, których nie umiemy rozpakować (inne filtry, obrazy), pomijamy —
    szukamy operatorów tekstu, a te siedzą w strumieniach treści, nie w JPEG-ach.
    """
    czesci: list[bytes] = []
    for dopasowanie in _STRUMIEN.finditer(dane):
        surowe = dopasowanie.group(1)
        try:
            czesci.append(zlib.decompress(surowe))
        except zlib.error:
            # Strumień nieskompresowany albo w formacie, którego nie ruszamy.
            # Nieskompresowany też niesie operatory, więc bierzemy go jak jest.
            czesci.append(surowe)
    return b"".join(czesci)


def zbadaj_pdf(sciezka: Path) -> tuple[Wynik, int]:
    """Klasyfikacja PDF-a i liczba stron.

    Nie parsujemy PDF-a porządnie — to zadanie biblioteki, której jeszcze nie
    mamy. Tu wystarczy odpowiedź „tekst czy obrazek", a ta jest widoczna
    z samego zliczenia operatorów tekstu.
    """
    try:
        dane = sciezka.read_bytes()
    except OSError:
        return Wynik.USZKODZONY, 0

    strony = len(_WEZEL_STRONY.findall(dane))
    if strony == 0:
        # PDF 1.5+ potrafi schować drzewo stron w strumieniu obiektów.
        # Wtedy licznik jest w /Count, a jak i tego nie ma — zakładamy jedną.
        licznik = re.search(rb"/Count\s+(\d+)", dane)
        strony = int(licznik.group(1)) if licznik else 1

    tresc = _rozpakuj_strumienie(dane)
    operatory = len(_OPERATORY_TEKSTU.findall(tresc))

    if operatory >= PROG_OPERATOROW_NA_STRONE * strony:
        return Wynik.TEKST, strony
    return Wynik.SKAN, strony


def zbadaj_docx(sciezka: Path) -> tuple[Wynik, int]:
    """DOCX to archiwum ZIP z `word/document.xml`. Tekst jest tam zawsze.

    Liczby stron nie da się stąd wziąć — podział na strony powstaje dopiero
    przy składaniu dokumentu przez Worda i nie ma go w pliku. Zwracamy 0
    i tak samo będzie to raportowane, zamiast podstawiać zmyśloną jedynkę.
    """
    try:
        with zipfile.ZipFile(sciezka) as archiwum:
            if "word/document.xml" in archiwum.namelist():
                return Wynik.TEKST, 0
    except (OSError, zipfile.BadZipFile):
        return Wynik.USZKODZONY, 0
    return Wynik.USZKODZONY, 0


def zbadaj(sciezka: Path) -> tuple[Wynik, int]:
    rozszerzenie = sciezka.suffix.lower()
    if rozszerzenie == ".pdf":
        return zbadaj_pdf(sciezka)
    if rozszerzenie == ".docx":
        return zbadaj_docx(sciezka)
    if rozszerzenie == ".doc":
        return Wynik.STARY_DOC, 0
    return Wynik.OBRAZ, 0


def _pomijany(sciezka: Path) -> bool:
    """Pliki ukryte i tymczasowe Worda („~$umowa.docx"). Tak samo jak w `domena/skan.py`."""
    nazwa = sciezka.name
    return nazwa.startswith(".") or nazwa.startswith("~$")


def przejdz(katalog: Path) -> Statystyka:
    staty = Statystyka()

    for sciezka in sorted(katalog.rglob("*")):
        if not sciezka.is_file() or _pomijany(sciezka):
            continue
        rozszerzenie = sciezka.suffix.lower()
        if rozszerzenie not in ROZSZERZENIA:
            continue

        wynik, strony = zbadaj(sciezka)

        staty.rozszerzenia[rozszerzenie] += 1
        staty.klasyfikacja[wynik] += 1
        staty.strony_lacznie += strony
        if wynik is Wynik.TEKST:
            staty.strony_z_tekstem += strony
        if wynik in WYMAGAJA_OCR:
            staty.do_ocr.append(sciezka)
        # Rozmiar to dodatek do raportu. Plik, którego nie da się zbadać,
        # ma zostać policzony w statystyce, a nie przerwać cały przebieg.
        with suppress(OSError):
            staty.bajty_lacznie += sciezka.stat().st_size

        wzgledna = sciezka.relative_to(katalog)
        korzen = wzgledna.parts[0] if len(wzgledna.parts) > 1 else "(katalog główny)"
        staty.katalogi[korzen] += 1

    return staty


def _katalog_z_env() -> Path | None:
    """KATALOG_SKANU z pliku .env. Baza wygrywa z plikiem, ale skrypt nie
    zagląda do bazy — to narzędzie diagnostyczne, ma działać bez uruchomionego
    Postgresa."""
    for kandydat in (Path(".env"), Path("dane/.env"), Path("../dane/.env")):
        if not kandydat.is_file():
            continue
        for linia in kandydat.read_text(encoding="utf-8", errors="replace").splitlines():
            linia = linia.strip()
            if linia.startswith("KATALOG_SKANU"):
                _, _, wartosc = linia.partition("=")
                wartosc = wartosc.strip().strip('"').strip("'")
                if wartosc:
                    return Path(wartosc)
    return None


def _plikow(ile: int) -> str:
    """„1 plik", „3 pliki", „7 plików". Polska odmiana przez liczebnik."""
    if ile == 1:
        return "1 plik"
    ostatnia, dwie_ostatnie = ile % 10, ile % 100
    if 2 <= ostatnia <= 4 and not 12 <= dwie_ostatnie <= 14:
        return f"{ile} pliki"
    return f"{ile} plików"


def _megabajty(bajty: int) -> str:
    return f"{bajty / 1024 / 1024:.1f} MB"


def raport(staty: Statystyka, katalog: Path, pokaz_pliki: bool) -> None:
    plikow = sum(staty.rozszerzenia.values())

    print()
    print(f"Katalog: {katalog}")
    print("=" * 70)

    if plikow == 0:
        print("Nie znaleziono żadnego pliku o rozszerzeniu dokumentu.")
        print(f"Szukane rozszerzenia: {', '.join(sorted(ROZSZERZENIA))}")
        return

    print(f"Znaleziono: {_plikow(plikow)}   ({_megabajty(staty.bajty_lacznie)})")
    print()

    print("Formaty")
    print("-" * 70)
    for rozszerzenie, ile in staty.rozszerzenia.most_common():
        print(f"  {rozszerzenie:<8} {ile:>5}   {ile * 100 // plikow:>3}%")
    print()

    print("Czy da się odczytać tekst")
    print("-" * 70)
    for opis, ile in staty.klasyfikacja.most_common():
        print(f"  {opis.value:<34} {ile:>5}   {ile * 100 // plikow:>3}%")
    print()

    if staty.strony_lacznie:
        print(f"Stron w PDF-ach: {staty.strony_lacznie}, "
              f"z czego z warstwą tekstową: {staty.strony_z_tekstem}")
        print("(DOCX nie niesie podziału na strony, więc go tu nie ma)")
        print()

    if len(staty.katalogi) > 1:
        print("Rozkład po katalogach najwyższego poziomu")
        print("-" * 70)
        for nazwa, ile in staty.katalogi.most_common():
            print(f"  {nazwa:<40} {ile:>5}")
        print()

    do_ocr = len(staty.do_ocr)
    print("Wniosek")
    print("=" * 70)
    if do_ocr == 0:
        print("  OCR NIE JEST POTRZEBNY.")
        print("  Każdy plik niesie tekst, który da się odczytać bez rozpoznawania")
        print("  obrazu. Etap E9.7 odpada, paczka wydania nie rośnie.")
    elif do_ocr * 100 // plikow < 15:
        print(f"  OCR potrzebny dla {do_ocr} z {plikow} ({do_ocr * 100 // plikow}%).")
        print("  Na tyle mało, że warto zacząć bez OCR-a, a te pliki obsłużyć")
        print("  ręcznie albo dołożyć OCR później jako osobny etap.")
    else:
        print(f"  OCR POTRZEBNY: {do_ocr} z {plikow} ({do_ocr * 100 // plikow}%)")
        print("  nie ma warstwy tekstowej. Bez rozpoznawania obrazu ekstrakcja")
        print("  pominie znaczną część archiwum. E9.7 wchodzi do zakresu.")

    if staty.klasyfikacja.get(Wynik.STARY_DOC):
        print()
        print(f"  Uwaga: {_plikow(staty.klasyfikacja[Wynik.STARY_DOC])} w starym formacie .doc.")
        print("  Propozycja z planu: nieobsługiwane, z komunikatem „zapisz jako PDF”.")

    if pokaz_pliki and staty.do_ocr:
        print()
        print("Pliki wymagające OCR")
        print("-" * 70)
        for sciezka in staty.do_ocr:
            print(f"  {sciezka.relative_to(katalog)}")
    elif staty.do_ocr:
        print()
        print("  (listę tych plików pokaże przełącznik --pliki)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Statystyka archiwum dokumentów: formaty i warstwy tekstowe.",
    )
    parser.add_argument(
        "katalog",
        nargs="?",
        help="Katalog do przejrzenia. Domyślnie KATALOG_SKANU z pliku .env.",
    )
    parser.add_argument(
        "--pliki",
        action="store_true",
        help="Wypisz ścieżki plików wymagających OCR. Uwaga: nazwy plików "
        "zwykle zawierają nazwy najemców.",
    )
    argumenty = parser.parse_args()

    katalog = Path(argumenty.katalog) if argumenty.katalog else _katalog_z_env()
    if katalog is None:
        print("Nie podano katalogu i nie ma KATALOG_SKANU w pliku .env.", file=sys.stderr)
        print("Użycie: python narzedzia/sprawdz-dokumenty.py <katalog>", file=sys.stderr)
        return 2
    if not katalog.is_dir():
        print(f"To nie jest katalog: {katalog}", file=sys.stderr)
        return 2

    raport(przejdz(katalog), katalog, argumenty.pliki)
    return 0


if __name__ == "__main__":
    # Konsola Windows domyślnie nie jest w UTF-8, a raport jest po polsku.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
