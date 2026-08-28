"""Czytanie dokumentow z folderow na dysku uzytkownika.

Zamiast wgrywac kazdy plik przez przegladarke, program zaglada do gotowego
drzewa katalogow i pokazuje, co w nim znalazl. Zaimportowany dokument
**zostaje na swoim miejscu** -- w bazie laduje sciezka wzgledna, skrot tresci
i rozmiar, a nie kopia pliku (TrybPrzechowywania.LINK).

Zakladana struktura:

    <katalog skanu>/
        Rycerska/
            Umowy najmu/
                Lokal nr 3_Kowalski/
                    Umowa najmu.pdf
                    Aneks nr 1.pdf

Trzy rzeczy, ktorych ten modul swiadomie NIE robi:

1. Nie parsuje oznaczen lokali z nazw folderow. Sa nieregularne (raz od zera,
   raz od jedynki, czasem "1.A" i "1.B"), a pomylka bylaby cicha. Folder
   z umowa paruje czlowiek raz, a system pamieta to w `powiazanie_folderu`.
2. Nie czyta tresci dokumentow. To wchodzi w etapie E9. Do tego czasu daty
   wpisuje czlowiek, a typ dokumentu jest wylacznie propozycja z nazwy pliku.
3. Nie importuje niczego samo z siebie. Kazdy plik przechodzi przez decyzje
   czlowieka: zaimportuj albo pomin (decyzja D4).
"""

import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from najem.dokumenty.przechowalnia import BladPliku, rozpoznaj_typ, sciezka_w_katalogu
from najem.domena.skan import czy_plik_dokumentu, numer_z_nazwy, rozpoznaj_typ_z_nazwy
from najem.domena.slowniki import StatusPrzetworzenia, TrybPrzechowywania, TypDokumentu
from najem.modele import Budynek, Dokument, OkresNajmu, PominietyPlik, PowiazanieFolderu

#: Ile plikow najwyzej pokazujemy w jednym skanie. Zabezpieczenie przed
#: wskazaniem katalogu w rodzaju "C:/", nie ograniczenie merytoryczne.
LIMIT_PLIKOW = 3000

#: Nazwa podkatalogu z folderami lokali. Szukamy po fragmencie, bo bywa
#: "Umowy najmu", "Umowy" albo "UMOWY NAJMU".
FRAGMENT_KATALOGU_UMOW = "umow"

#: Ile bajtow czytamy, zeby rozpoznac typ pliku. Sygnatura siedzi na poczatku,
#: a caly plik potrafi miec dziesiatki megabajtow.
DLUGOSC_PROBKI = 1024 * 1024


class BladSkanu(Exception):
    """Katalog skanu nie jest ustawiony albo pliku nie da sie odczytac."""


@dataclass(frozen=True)
class PlikKandydat:
    nazwa: str
    sciezka_wzgledna: str
    rozmiar_bajty: int
    #: nowy | w_systemie | pominiety
    status: str
    typ_proponowany: TypDokumentu | None
    numer_proponowany: str | None
    dokument_id: int | None = None
    pominiecie_id: int | None = None


@dataclass(frozen=True)
class FolderKandydat:
    nazwa: str
    sciezka_wzgledna: str
    powiazanie_id: int | None
    okres_najmu_id: int | None
    #: Opis umowy do pokazania czlowiekowi, np. "18A/12 - Kowalski sp. z o.o.".
    opis_umowy: str | None
    pliki: list[PlikKandydat] = field(default_factory=list)

    @property
    def nowych(self) -> int:
        return sum(1 for p in self.pliki if p.status == "nowy")


@dataclass(frozen=True)
class BudynekKandydat:
    nazwa_folderu: str
    budynek_id: int | None
    budynek_nazwa: str | None
    foldery: list[FolderKandydat] = field(default_factory=list)


@dataclass(frozen=True)
class WynikSkanu:
    katalog: str | None
    dostepny: bool
    komunikat: str | None
    budynki: list[BudynekKandydat] = field(default_factory=list)
    obcietych: int = 0
    #: Ile katalogow i plikow pominieto, bo system ich nie udostepnil.
    #: Liczba, a nie ciche pominiecie: brak dostepu to informacja (decyzja D5).
    niedostepnych: int = 0

    @property
    def nowych(self) -> int:
        return sum(f.nowych for b in self.budynki for f in b.foldery)


def skrot_pliku(sciezka: Path) -> str:
    """SHA-256 pliku, czytany kawalkami.

    Skan nie moze wciagac do pamieci kilkusetmegabajtowego katalogu naraz.
    """
    licznik = hashlib.sha256()
    with sciezka.open("rb") as plik:
        while kawalek := plik.read(1024 * 1024):
            licznik.update(kawalek)
    return licznik.hexdigest()


class _Licznik:
    """Ile razy system odmowil dostepu w trakcie jednego skanu."""

    def __init__(self) -> None:
        self.niedostepnych = 0


def _zawartosc(katalog: Path, licznik: _Licznik) -> list[Path]:
    """Zawartosc katalogu albo pusta lista, gdy nie da sie go odczytac.

    Skan chodzi po prawdziwym dysku uzytkownika, wiec trafi predzej czy pozniej
    na katalog bez uprawnien, na sciezke dluzsza niz limit Windowsa albo na
    odlaczony dysk sieciowy. Bez tego jeden taki katalog konczyl caly skan
    bledem 500 i uzytkownik nie widzial ani jednego swojego dokumentu.

    Pominiecia liczymy zamiast je przemilczec: brak dostepu to informacja.
    """
    try:
        return sorted(katalog.iterdir())
    except OSError:
        licznik.niedostepnych += 1
        return []


def _katalog_umow(folder_budynku: Path, licznik: _Licznik) -> Path:
    """Podkatalog z folderami lokali albo sam folder budynku.

    Gdy w folderze budynku jest katalog "Umowy najmu", to w nim leza foldery
    lokali i nic innego. Gdy go nie ma, bierzemy podkatalogi budynku wprost --
    lepiej pokazac czlowiekowi cos do sparowania niz pusty ekran.
    """
    for pozycja in _zawartosc(folder_budynku, licznik):
        if pozycja.is_dir() and FRAGMENT_KATALOGU_UMOW in pozycja.name.lower():
            return pozycja
    return folder_budynku


def _opis_umowy(okres: OkresNajmu) -> str:
    lokal = okres.lokal.oznaczenie if okres.lokal else "?"
    najemca = okres.najemca.nazwa_pelna if okres.najemca else "bez najemcy"
    return f"{lokal} - {najemca}"


def skanuj(baza: Session, *, katalog: Path | None) -> WynikSkanu:
    """Przechodzi drzewo katalogow i mowi, co w nim jest, a czego jeszcze nie ma
    w systemie. Niczego nie zapisuje.
    """
    if katalog is None:
        return WynikSkanu(
            katalog=None,
            dostepny=False,
            komunikat=(
                "Nie wskazano katalogu z dokumentami. Ustaw KATALOG_SKANU w pliku .env "
                "i uruchom program ponownie."
            ),
        )

    korzen = Path(katalog)
    if not korzen.is_dir():
        return WynikSkanu(
            katalog=str(korzen),
            dostepny=False,
            komunikat=f"Katalog {korzen} nie istnieje albo jest niedostępny.",
        )

    budynki = baza.scalars(
        select(Budynek).where(Budynek.usunieto_dnia.is_(None)).order_by(Budynek.nazwa)
    ).all()
    # Dopasowanie po nazwie folderu, a gdy jej nie ustawiono -- po nazwie
    # budynku. Dzieki temu pierwszy skan cos znajduje, zanim ktokolwiek
    # cokolwiek skonfiguruje.
    po_folderze = {b.nazwa_folderu.lower(): b for b in budynki if b.nazwa_folderu}
    po_nazwie = {b.nazwa.lower(): b for b in budynki}

    powiazania = {
        p.sciezka_wzgledna: p
        for p in baza.scalars(
            select(PowiazanieFolderu)
            .where(PowiazanieFolderu.usunieto_dnia.is_(None))
            .options(
                selectinload(PowiazanieFolderu.okres_najmu).selectinload(OkresNajmu.lokal),
                selectinload(PowiazanieFolderu.okres_najmu).selectinload(OkresNajmu.najemca),
            )
        ).all()
    }

    pominiete = baza.scalars(
        select(PominietyPlik).where(PominietyPlik.usunieto_dnia.is_(None))
    ).all()
    pominiete_po_hashu = {p.hash_sha256: p for p in pominiete}
    pominiete_po_sciezce = {p.sciezka_wzgledna: p for p in pominiete if p.sciezka_wzgledna}

    dokumenty = baza.execute(
        select(
            Dokument.id, Dokument.plik_sciezka, Dokument.hash_sha256, Dokument.przechowywanie
        ).where(Dokument.usunieto_dnia.is_(None))
    ).all()
    linki_po_sciezce = {
        d.plik_sciezka: d.id
        for d in dokumenty
        if d.przechowywanie == TrybPrzechowywania.LINK and d.plik_sciezka
    }
    dokumenty_po_hashu = {d.hash_sha256: d.id for d in dokumenty if d.hash_sha256}

    wynik: list[BudynekKandydat] = []
    licznik = _Licznik()
    policzone = 0
    obcietych = 0

    for folder_budynku in (p for p in _zawartosc(korzen, licznik) if p.is_dir()):
        nazwa_male = folder_budynku.name.lower()
        budynek = po_folderze.get(nazwa_male) or po_nazwie.get(nazwa_male)
        foldery: list[FolderKandydat] = []
        katalog_umow = _katalog_umow(folder_budynku, licznik)

        for folder_lokalu in (p for p in _zawartosc(katalog_umow, licznik) if p.is_dir()):
            wzgledna_folderu = folder_lokalu.relative_to(korzen).as_posix()
            powiazanie = powiazania.get(wzgledna_folderu)

            pliki: list[PlikKandydat] = []
            for plik in (p for p in _zawartosc(folder_lokalu, licznik) if p.is_file()):
                if not czy_plik_dokumentu(plik.name):
                    continue
                if policzone >= LIMIT_PLIKOW:
                    obcietych += 1
                    continue
                policzone += 1
                opis = _opisz_plik(
                    plik,
                    korzen=korzen,
                    linki_po_sciezce=linki_po_sciezce,
                    dokumenty_po_hashu=dokumenty_po_hashu,
                    pominiete_po_sciezce=pominiete_po_sciezce,
                    pominiete_po_hashu=pominiete_po_hashu,
                )
                if opis is None:
                    # Plik zniknal albo system odmowil odczytu miedzy
                    # wylistowaniem katalogu a policzeniem skrotu.
                    licznik.niedostepnych += 1
                    policzone -= 1
                    continue
                pliki.append(opis)

            foldery.append(
                FolderKandydat(
                    nazwa=folder_lokalu.name,
                    sciezka_wzgledna=wzgledna_folderu,
                    powiazanie_id=powiazanie.id if powiazanie else None,
                    okres_najmu_id=powiazanie.okres_najmu_id if powiazanie else None,
                    opis_umowy=_opis_umowy(powiazanie.okres_najmu) if powiazanie else None,
                    pliki=pliki,
                )
            )

        wynik.append(
            BudynekKandydat(
                nazwa_folderu=folder_budynku.name,
                budynek_id=budynek.id if budynek else None,
                budynek_nazwa=budynek.nazwa if budynek else None,
                foldery=foldery,
            )
        )

    return WynikSkanu(
        katalog=str(korzen),
        dostepny=True,
        komunikat=None,
        budynki=wynik,
        obcietych=obcietych,
        niedostepnych=licznik.niedostepnych,
    )


def _opisz_plik(
    plik: Path,
    *,
    korzen: Path,
    linki_po_sciezce: dict[str, int],
    dokumenty_po_hashu: dict[str, int],
    pominiete_po_sciezce: dict[str, PominietyPlik],
    pominiete_po_hashu: dict[str, PominietyPlik],
) -> PlikKandydat | None:
    """Jeden plik z folderu wraz z propozycja typu i informacja, czy juz go znamy.

    Kolejnosc sprawdzen jest optymalizacja, a nie kaprysem: dopasowanie po
    sciezce jest darmowe, a liczenie skrotu wymaga przeczytania calego pliku.
    Dlatego skrot liczymy dopiero wtedy, gdy sciezka nic nie powiedziala.
    """
    wzgledna = plik.relative_to(korzen).as_posix()
    try:
        rozmiar = plik.stat().st_size
    except OSError:
        return None
    typ = rozpoznaj_typ_z_nazwy(plik.name)
    numer = numer_z_nazwy(plik.name) if typ == TypDokumentu.ANEKS else None

    def kandydat(status: str, dokument_id: int | None, pominiecie_id: int | None) -> PlikKandydat:
        return PlikKandydat(
            nazwa=plik.name,
            sciezka_wzgledna=wzgledna,
            rozmiar_bajty=rozmiar,
            status=status,
            typ_proponowany=typ,
            numer_proponowany=numer,
            dokument_id=dokument_id,
            pominiecie_id=pominiecie_id,
        )

    if (dokument_id := linki_po_sciezce.get(wzgledna)) is not None:
        return kandydat("w_systemie", dokument_id, None)
    if (pominiecie := pominiete_po_sciezce.get(wzgledna)) is not None:
        return kandydat("pominiety", None, pominiecie.id)

    try:
        skrot = skrot_pliku(plik)
    except OSError:
        # Plik zajety przez inny program albo skasowany w trakcie skanu.
        return None

    if (dokument_id := dokumenty_po_hashu.get(skrot)) is not None:
        # Ten sam plik moze juz byc w systemie pod inna sciezka albo jako
        # kopia wgrana kiedys przez przegladarke. To nadal ten sam dokument.
        return kandydat("w_systemie", dokument_id, None)
    if (pominiecie := pominiete_po_hashu.get(skrot)) is not None:
        return kandydat("pominiety", None, pominiecie.id)

    return kandydat("nowy", None, None)


def zaimportuj_plik(
    baza: Session,
    *,
    sciezka_wzgledna: str,
    katalog: Path | None,
    typ: TypDokumentu,
    okres_najmu_id: int | None,
    dokument_nadrzedny_id: int | None,
    numer: str | None,
    data_dokumentu: date | None,
    data_obowiazywania_od: date | None,
    uzytkownik_id: int,
) -> Dokument:
    """Zaklada dokument wskazujacy na plik lezacy na dysku uzytkownika.

    Plik nie jest kopiowany ani przenoszony. Typ i tak sprawdzamy po zawartosci,
    tak samo jak przy wgrywaniu przez przegladarke: rozszerzenie jest
    deklaracja, a nie faktem.
    """
    plik = _plik_ze_skanu(sciezka_wzgledna, katalog=katalog)

    rozmiar = plik.stat().st_size
    with plik.open("rb") as uchwyt:
        poczatek = uchwyt.read(DLUGOSC_PROBKI)
    typ_pliku = rozpoznaj_typ(poczatek)

    skrot = skrot_pliku(plik)
    istniejacy = baza.scalars(
        select(Dokument).where(Dokument.hash_sha256 == skrot, Dokument.usunieto_dnia.is_(None))
    ).one_or_none()
    if istniejacy is not None:
        raise BladPliku(
            f"Ten plik jest już w systemie (pozycja {istniejacy.id}). "
            "Ten sam dokument nie może wejść dwa razy."
        )

    dokument = Dokument(
        okres_najmu_id=okres_najmu_id,
        typ=typ,
        numer=numer,
        data_dokumentu=data_dokumentu,
        data_obowiazywania_od=data_obowiazywania_od,
        plik_sciezka=sciezka_wzgledna,
        plik_nazwa_oryginalna=plik.name[:300],
        hash_sha256=skrot,
        rozmiar_bajty=rozmiar,
        typ_mime=typ_pliku.value,
        dokument_nadrzedny_id=dokument_nadrzedny_id,
        status_przetworzenia=StatusPrzetworzenia.WGRANY,
        przechowywanie=TrybPrzechowywania.LINK,
        wgral_uzytkownik_id=uzytkownik_id,
    )
    baza.add(dokument)
    baza.flush()
    return dokument


def pomin_plik(
    baza: Session,
    *,
    sciezka_wzgledna: str,
    katalog: Path | None,
    powod: str | None,
    uzytkownik_id: int,
) -> PominietyPlik:
    """Zapamietuje, ze tego pliku nie importujemy.

    Pamietamy skrot tresci, nie sciezke: plik przemianowany albo przeniesiony
    do innego folderu to nadal ten sam plik i nadal ma sie nie pokazywac.
    """
    plik = _plik_ze_skanu(sciezka_wzgledna, katalog=katalog)
    skrot = skrot_pliku(plik)

    istniejacy = baza.scalars(
        select(PominietyPlik).where(
            PominietyPlik.hash_sha256 == skrot, PominietyPlik.usunieto_dnia.is_(None)
        )
    ).one_or_none()
    if istniejacy is not None:
        return istniejacy

    pominiecie = PominietyPlik(
        hash_sha256=skrot,
        nazwa_pliku=plik.name[:300],
        sciezka_wzgledna=sciezka_wzgledna[:500],
        powod=powod,
        pominal_uzytkownik_id=uzytkownik_id,
    )
    baza.add(pominiecie)
    baza.flush()
    return pominiecie


def _plik_ze_skanu(sciezka_wzgledna: str, *, katalog: Path | None) -> Path:
    if katalog is None:
        raise BladSkanu("Nie wskazano katalogu z dokumentami.")
    plik = sciezka_w_katalogu(sciezka_wzgledna, katalog=katalog)
    if not plik.is_file():
        raise BladSkanu(f"Pliku {sciezka_wzgledna} już nie ma w tym miejscu.")
    return plik


@dataclass(frozen=True)
class ZerwanyLink:
    dokument_id: int
    nazwa: str | None
    sciezka_wzgledna: str
    okres_najmu_id: int | None
    powod: str


def sprawdz_linki(baza: Session, *, katalog: Path | None) -> list[ZerwanyLink]:
    """Przechodzi po wszystkich zlinkowanych dokumentach i szuka takich,
    ktorych pliku juz nie ma albo zmienila sie jego tresc.

    To jest cena za to, ze dokumenty nie sa kopiowane: przeniesienie albo
    przemianowanie pliku w Eksploratorze zrywa odnosnik. Ten przeglad ma
    sprawic, ze zerwanie bedzie widoczne od razu, a nie odkryte przy sporze.
    """
    dokumenty = baza.scalars(
        select(Dokument)
        .where(
            Dokument.usunieto_dnia.is_(None),
            Dokument.przechowywanie == TrybPrzechowywania.LINK,
            Dokument.plik_sciezka.is_not(None),
        )
        .order_by(Dokument.id)
    ).all()

    zerwane: list[ZerwanyLink] = []
    for dokument in dokumenty:
        powod = _powod_zerwania(dokument, katalog=katalog)
        if powod is None:
            continue
        zerwane.append(
            ZerwanyLink(
                dokument_id=dokument.id,
                nazwa=dokument.plik_nazwa_oryginalna,
                sciezka_wzgledna=dokument.plik_sciezka or "",
                okres_najmu_id=dokument.okres_najmu_id,
                powod=powod,
            )
        )
    return zerwane


def _powod_zerwania(dokument: Dokument, *, katalog: Path | None) -> str | None:
    """Co jest nie tak z odnosnikiem albo None, gdy wszystko gra."""
    if katalog is None:
        return "Nie wskazano katalogu z dokumentami."
    try:
        plik = sciezka_w_katalogu(dokument.plik_sciezka or "", katalog=katalog)
    except BladPliku as blad:
        return str(blad)

    if not plik.is_file():
        return (
            "Pliku nie ma pod zapisaną ścieżką. Został przeniesiony, przemianowany albo usunięty."
        )
    if dokument.hash_sha256 and skrot_pliku(plik) != dokument.hash_sha256:
        return "Plik pod tą ścieżką ma inną treść niż w chwili importu."
    return None
