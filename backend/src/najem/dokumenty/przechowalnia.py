"""Przyjmowanie i przechowywanie plików dokumentów.

Wymagania z sekcji 1.2 punkt L planu budowy, wszystkie realizowane tutaj:

* limit rozmiaru,
* biała lista typów sprawdzana **po zawartości pliku**, nie po rozszerzeniu,
* nazwa generowana, nigdy z uploadu,
* katalog poza obszarem serwowanym przez serwer WWW,
* deduplikacja po SHA-256.

Rozszerzenie nazwy pliku jest deklaracją nadawcy, a nie faktem. `umowa.pdf`
bywa plikiem wykonywalnym, a skan bez rozszerzenia bywa poprawnym PDF-em.
Dlatego typ rozpoznajemy z pierwszych bajtów.
"""

import hashlib
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path

#: Domyślny limit rozmiaru pojedynczego pliku.
LIMIT_BAJTOW = 50 * 1024 * 1024

#: Ile bajtów wystarczy, żeby rozpoznać typ.
DLUGOSC_SYGNATURY = 8

#: Ile początkowych bajtów przeszukujemy w archiwum OLE. Katalog strumieni
#: leży blisko początku pliku, a przeszukiwanie całego kilkumegabajtowego
#: dokumentu byłoby marnotrawstwem przy każdym skanie folderu.
LIMIT_PRZESZUKANIA_OLE = 512 * 1024


#: Sygnatura formatu OLE2: stary Office (.doc, .xls, .ppt) i kilkanascie
#: innych formatow. Sama w sobie nie mowi, ktory to z nich.
SYGNATURA_OLE = bytes.fromhex("d0cf11e0a1b11ae1")

#: Nazwa strumienia w archiwum OLE, po ktorej poznajemy dokument Worda.
#: W pliku lezy jako UTF-16LE, stad zera miedzy literami.
STRUMIEN_WORDA = "WordDocument".encode("utf-16-le")


class TypPliku(StrEnum):
    PDF = "application/pdf"
    DOC = "application/msword"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    JPEG = "image/jpeg"
    PNG = "image/png"


#: Rozszerzenie nadawane plikowi w przechowalni. Nazwa z uploadu nie jest używana.
ROZSZERZENIA: dict[TypPliku, str] = {
    TypPliku.PDF: ".pdf",
    TypPliku.DOC: ".doc",
    TypPliku.DOCX: ".docx",
    TypPliku.XLSX: ".xlsx",
    TypPliku.JPEG: ".jpg",
    TypPliku.PNG: ".png",
}

#: Co wolno wgrać jako dokument umowy. Arkusze idą osobną ścieżką importu.
DOZWOLONE_DOKUMENTY: frozenset[TypPliku] = frozenset(
    {TypPliku.PDF, TypPliku.DOC, TypPliku.DOCX, TypPliku.JPEG, TypPliku.PNG}
)


class BladPliku(Exception):
    """Plik odrzucony: za duży, pusty albo nieobsługiwanego typu."""


@dataclass(frozen=True)
class ZapisanyPlik:
    """Co wiemy o pliku po jego przyjęciu."""

    hash_sha256: str
    rozmiar_bajty: int
    typ: TypPliku
    #: Ścieżka względna do katalogu dokumentów. W bazie trzymamy tylko ją.
    sciezka_wzgledna: str


def rozpoznaj_typ(zawartosc: bytes) -> TypPliku:
    """Typ pliku odczytany z jego pierwszych bajtów.

    Rozszerzenie i nagłówek `Content-Type` z żądania są deklaracją nadawcy.
    Sprawdzamy to, co faktycznie jest w pliku.
    """
    if len(zawartosc) < DLUGOSC_SYGNATURY:
        raise BladPliku("Plik jest pusty albo uszkodzony.")

    if zawartosc.startswith(b"%PDF-"):
        return TypPliku.PDF
    if zawartosc.startswith(b"\xff\xd8\xff"):
        return TypPliku.JPEG
    if zawartosc.startswith(b"\x89PNG\r\n\x1a\n"):
        return TypPliku.PNG

    # DOCX i XLSX to archiwa ZIP. Rozróżniamy je po zawartości archiwum,
    # bo sygnatura ZIP jest wspólna dla obu i dla setki innych formatów.
    if zawartosc.startswith(b"PK\x03\x04"):
        return _typ_archiwum(zawartosc)

    # Stary format Office. Umowy sprzed lat bywają zapisane właśnie tak.
    if zawartosc.startswith(SYGNATURA_OLE):
        return _typ_ole(zawartosc)

    raise BladPliku(
        "Nieobsługiwany typ pliku. Przyjmujemy PDF, DOC, DOCX, JPEG i PNG. "
        "Liczy się zawartość pliku, nie jego rozszerzenie."
    )


def _typ_archiwum(zawartosc: bytes) -> TypPliku:
    try:
        with zipfile.ZipFile(BytesIO(zawartosc)) as archiwum:
            nazwy = set(archiwum.namelist())
    except zipfile.BadZipFile as blad:
        raise BladPliku("Plik wygląda na archiwum, ale jest uszkodzony.") from blad

    if "word/document.xml" in nazwy:
        return TypPliku.DOCX
    if any(nazwa.startswith("xl/") for nazwa in nazwy):
        return TypPliku.XLSX
    raise BladPliku("Archiwum nie jest dokumentem Worda ani arkuszem Excela.")


def _typ_ole(zawartosc: bytes) -> TypPliku:
    """Rozroznienie .doc od .xls i .ppt wewnatrz wspolnej sygnatury OLE.

    Pelne parsowanie struktury OLE byloby tu przerostem formy: wystarczy,
    ze w katalogu archiwum stoi nazwa strumienia "WordDocument". Arkusz ma
    w tym miejscu "Workbook", a prezentacja "PowerPoint Document".
    """
    if STRUMIEN_WORDA in zawartosc[:LIMIT_PRZESZUKANIA_OLE]:
        return TypPliku.DOC
    raise BladPliku(
        "Plik jest dokumentem starego pakietu Office, ale nie dokumentem Worda. "
        "Arkusze wgrywa się przez import z arkusza."
    )


def przyjmij_plik(
    zawartosc: bytes,
    *,
    katalog: Path,
    dozwolone: frozenset[TypPliku] = DOZWOLONE_DOKUMENTY,
    limit_bajtow: int = LIMIT_BAJTOW,
) -> ZapisanyPlik:
    """Sprawdza plik i zapisuje go w przechowalni. Zwraca metadane.

    Nazwa w przechowalni pochodzi ze skrótu treści, nie z uploadu. Dwa skutki:
    ten sam plik wgrany dwa razy zajmuje miejsce raz, a nadawca nie ma wpływu
    na to, gdzie plik wyląduje ani jak się nazwie.
    """
    if not zawartosc:
        raise BladPliku("Plik jest pusty.")
    if len(zawartosc) > limit_bajtow:
        raise BladPliku(
            f"Plik ma {len(zawartosc) // 1024 // 1024} MB, "
            f"a limit to {limit_bajtow // 1024 // 1024} MB."
        )

    typ = rozpoznaj_typ(zawartosc)
    if typ not in dozwolone:
        raise BladPliku(f"Pliki typu {typ.value} nie są przyjmowane w tym miejscu.")

    skrot = hashlib.sha256(zawartosc).hexdigest()
    # Dwa poziomy katalogów po dwa znaki skrótu: bez tego kilka tysięcy plików
    # w jednym katalogu spowalnia system plików na Windowsie.
    wzgledna = f"{skrot[:2]}/{skrot[2:4]}/{skrot}{ROZSZERZENIA[typ]}"
    docelowa = katalog / wzgledna

    docelowa.parent.mkdir(parents=True, exist_ok=True)
    if not docelowa.exists():
        # Zapis przez plik tymczasowy: przerwanie w połowie nie zostawia
        # obciętego pliku pod właściwą nazwą.
        tymczasowa = docelowa.with_suffix(docelowa.suffix + ".czesciowy")
        tymczasowa.write_bytes(zawartosc)
        tymczasowa.replace(docelowa)

    return ZapisanyPlik(
        hash_sha256=skrot,
        rozmiar_bajty=len(zawartosc),
        typ=typ,
        sciezka_wzgledna=wzgledna,
    )


def sciezka_w_katalogu(sciezka_wzgledna: str, *, katalog: Path) -> Path:
    """Ścieżka bezwzględna do pliku, sprawdzona, że nie wychodzi poza katalog.

    Ścieżka pochodzi z bazy, ale i tak ją sprawdzamy: jedna pomyłka przy
    imporcie danych nie może pozwolić na czytanie dowolnego pliku z dysku.
    """
    try:
        docelowa = (katalog / sciezka_wzgledna).resolve()
    except OSError as blad:
        # Ścieżka sieciowa albo zbyt długa dla systemu plików. `resolve()`
        # próbuje wtedy sięgnąć do zasobu i podnosi OSError, który bez tego
        # przechwycenia wychodzi z API jako 500 zamiast czytelnej odmowy.
        raise BladPliku("Tej ścieżki nie da się odczytać w tym systemie.") from blad

    if not docelowa.is_relative_to(katalog.resolve()):
        raise BladPliku("Ścieżka pliku wychodzi poza dozwolony katalog.")
    return docelowa


def wczytaj_plik(
    sciezka_wzgledna: str,
    *,
    katalog: Path,
    brak: str = "Pliku nie ma w przechowalni. Mógł zostać usunięty ręcznie.",
) -> bytes:
    """Treść pliku z katalogu dokumentów albo z katalogu skanowanego.

    Komunikat o braku pliku jest parametrem, bo znaczy co innego w każdym
    z tych dwóch miejsc. Zniknięcie pliku z przechowalni to awaria, a
    zniknięcie zlinkowanego pliku to zwykłe przeniesienie go w Eksploratorze.
    """
    docelowa = sciezka_w_katalogu(sciezka_wzgledna, katalog=katalog)
    if not docelowa.is_file():
        raise BladPliku(brak)
    return docelowa.read_bytes()
