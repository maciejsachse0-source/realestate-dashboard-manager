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


class TypPliku(StrEnum):
    PDF = "application/pdf"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    JPEG = "image/jpeg"
    PNG = "image/png"


#: Rozszerzenie nadawane plikowi w przechowalni. Nazwa z uploadu nie jest używana.
ROZSZERZENIA: dict[TypPliku, str] = {
    TypPliku.PDF: ".pdf",
    TypPliku.DOCX: ".docx",
    TypPliku.XLSX: ".xlsx",
    TypPliku.JPEG: ".jpg",
    TypPliku.PNG: ".png",
}

#: Co wolno wgrać jako dokument umowy. Arkusze idą osobną ścieżką importu.
DOZWOLONE_DOKUMENTY: frozenset[TypPliku] = frozenset(
    {TypPliku.PDF, TypPliku.DOCX, TypPliku.JPEG, TypPliku.PNG}
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

    raise BladPliku(
        "Nieobsługiwany typ pliku. Przyjmujemy PDF, DOCX, JPEG i PNG. "
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


def wczytaj_plik(sciezka_wzgledna: str, *, katalog: Path) -> bytes:
    """Treść pliku z przechowalni.

    Ścieżka pochodzi z bazy, ale i tak sprawdzamy, czy nie wychodzi poza katalog:
    jedna pomyłka przy imporcie danych nie może pozwolić na czytanie
    dowolnego pliku z dysku.
    """
    docelowa = (katalog / sciezka_wzgledna).resolve()
    if not docelowa.is_relative_to(katalog.resolve()):
        raise BladPliku("Ścieżka pliku wychodzi poza katalog dokumentów.")
    if not docelowa.is_file():
        raise BladPliku("Pliku nie ma w przechowalni. Mógł zostać usunięty ręcznie.")
    return docelowa.read_bytes()
