"""Dokumenty z dysku: skan folderów, parowanie i import przez odnośnik.

Ekran zbudowany wokół jednej zasady: program pokazuje, co znalazł, a decyzję
podejmuje człowiek (decyzja D4). Nic nie importuje się samo, nic nie jest
kopiowane i nic nie jest zgadywane z nazwy folderu.
"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from najem.baza import SesjaBazy
from najem.dokumenty.przechowalnia import BladPliku
from najem.domena.slowniki import OperacjaAudytu, TrybPrzechowywania, TypDokumentu
from najem.modele import Dokument, OkresNajmu, PominietyPlik, PowiazanieFolderu
from najem.uslugi.audyt import zapisz_zmiane
from najem.uslugi.skan_folderow import BladSkanu, pomin_plik, skanuj, sprawdz_linki
from najem.uslugi.skan_folderow import zaimportuj_plik as usluga_importu
from najem.uslugi.ustawienia_systemu import (
    BladUstawienia,
    katalog_skanu,
    opis_katalogu_skanu,
    sprawdz_katalog,
    wyczysc_katalog_skanu,
    zapisz_katalog_skanu,
)

router = APIRouter(prefix="/skan", tags=["skan"])


def _adres(request: Request) -> str | None:
    return request.client.host if request.client else None


# ----------------------------------------------------------------- schematy


class KatalogWejscie(BaseModel):
    sciezka: str = Field(max_length=500)


class KatalogWyjscie(BaseModel):
    sciezka: str | None
    #: baza | plik | brak
    zrodlo: str
    istnieje: bool


class PlikWyjscie(BaseModel):
    nazwa: str
    sciezka_wzgledna: str
    rozmiar_bajty: int
    #: nowy | w_systemie | pominiety
    status: str
    #: None znaczy „nazwa pliku nic nie mówi o typie". Człowiek wybiera sam.
    typ_proponowany: TypDokumentu | None
    numer_proponowany: str | None
    dokument_id: int | None
    pominiecie_id: int | None


class FolderWyjscie(BaseModel):
    nazwa: str
    sciezka_wzgledna: str
    powiazanie_id: int | None
    okres_najmu_id: int | None
    opis_umowy: str | None
    nowych: int
    pliki: list[PlikWyjscie]


class BudynekWyjscie(BaseModel):
    nazwa_folderu: str
    budynek_id: int | None
    budynek_nazwa: str | None
    foldery: list[FolderWyjscie]


class SkanWyjscie(BaseModel):
    katalog: str | None
    dostepny: bool
    komunikat: str | None
    nowych: int
    obcietych: int
    #: Ile katalogow i plikow system odmowil udostepnic.
    niedostepnych: int
    budynki: list[BudynekWyjscie]


class PowiazanieWejscie(BaseModel):
    sciezka_wzgledna: str = Field(max_length=500)
    okres_najmu_id: int
    uwagi: str | None = None


class PowiazanieWyjscie(BaseModel):
    id: int
    sciezka_wzgledna: str
    okres_najmu_id: int


class ImportWejscie(BaseModel):
    sciezka_wzgledna: str = Field(max_length=500)
    typ: TypDokumentu
    okres_najmu_id: int | None = None
    dokument_nadrzedny_id: int | None = None
    numer: str | None = Field(default=None, max_length=80)
    #: Do etapu E9 system nie czyta treści dokumentów, więc datę wpisuje
    #: człowiek. Puste pole zostaje puste — zera ani „dziś" tu nie podstawiamy.
    data_dokumentu: date | None = None
    data_obowiazywania_od: date | None = None


class PominiecieWejscie(BaseModel):
    sciezka_wzgledna: str = Field(max_length=500)
    powod: str | None = None


class PominiecieWyjscie(BaseModel):
    id: int
    hash_sha256: str
    nazwa_pliku: str | None


class ZaimportowanyWyjscie(BaseModel):
    id: int
    typ: TypDokumentu
    numer: str | None
    okres_najmu_id: int | None
    plik_nazwa_oryginalna: str | None
    plik_sciezka: str | None
    rozmiar_bajty: int | None
    typ_mime: str | None


class ZerwanyLinkWyjscie(BaseModel):
    dokument_id: int
    nazwa: str | None
    sciezka_wzgledna: str
    okres_najmu_id: int | None
    powod: str


class PrzegladLinkowWyjscie(BaseModel):
    katalog: str | None
    sprawdzonych: int
    zerwane: list[ZerwanyLinkWyjscie]


# ---------------------------------------------------------------- endpointy


@router.get(
    "/katalog",
    response_model=KatalogWyjscie,
    summary="Który katalog jest przeszukiwany",
)
def katalog(baza: SesjaBazy) -> KatalogWyjscie:
    """Ścieżka razem z informacją, skąd pochodzi.

    Bez tej informacji zmiana ustawienia wygląda na nieskuteczną: człowiek
    wpisuje ścieżkę, a ekran dalej pokazuje tę z pliku `.env`.
    """
    opis = opis_katalogu_skanu(baza)
    return KatalogWyjscie(
        sciezka=str(opis.sciezka) if opis.sciezka else None,
        zrodlo=opis.zrodlo,
        istnieje=opis.istnieje,
    )


@router.put(
    "/katalog",
    response_model=KatalogWyjscie,
    summary="Ustawia katalog z dokumentami",
)
def ustaw_katalog(dane: KatalogWejscie, baza: SesjaBazy, request: Request) -> KatalogWyjscie:
    """Zmiana konfiguracji systemu, więc tylko administrator.

    Katalog musi istnieć w chwili zapisu. Literówka w ścieżce jest najczęstszym
    błędem przy tym polu, a wykryta od razu kosztuje poprawkę jednego znaku
    zamiast szukania, czemu skan nic nie znajduje.
    """
    try:
        sciezka = sprawdz_katalog(dane.sciezka)
    except BladUstawienia as blad:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(blad)) from blad

    wiersz = zapisz_katalog_skanu(baza, sciezka=sciezka)
    zapisz_zmiane(
        baza,
        wiersz,
        operacja=OperacjaAudytu.ZMIANA,
        adres_ip=_adres(request),
    )
    baza.commit()
    return KatalogWyjscie(sciezka=str(sciezka), zrodlo="baza", istnieje=True)


@router.delete(
    "/katalog",
    response_model=KatalogWyjscie,
    summary="Przywraca katalog z pliku .env",
)
def wyczysc_katalog(baza: SesjaBazy, request: Request) -> KatalogWyjscie:
    wiersz = wyczysc_katalog_skanu(baza)
    if wiersz is not None:
        zapisz_zmiane(
            baza,
            wiersz,
            operacja=OperacjaAudytu.USUNIECIE,
            adres_ip=_adres(request),
        )
    baza.commit()

    opis = opis_katalogu_skanu(baza)
    return KatalogWyjscie(
        sciezka=str(opis.sciezka) if opis.sciezka else None,
        zrodlo=opis.zrodlo,
        istnieje=opis.istnieje,
    )


@router.get("", response_model=SkanWyjscie, summary="Co leży w folderach na dysku")
def skan(baza: SesjaBazy) -> SkanWyjscie:
    """Przegląda drzewo katalogów i zestawia je z tym, co już jest w bazie.

    Niczego nie zapisuje. Skan pliku, którego jeszcze nie znamy, wymaga
    policzenia jego skrótu, więc przy pierwszym uruchomieniu na dużym
    archiwum potrafi chwilę potrwać.
    """
    wynik = skanuj(baza, katalog=katalog_skanu(baza))
    return SkanWyjscie(
        katalog=wynik.katalog,
        dostepny=wynik.dostepny,
        komunikat=wynik.komunikat,
        nowych=wynik.nowych,
        obcietych=wynik.obcietych,
        niedostepnych=wynik.niedostepnych,
        budynki=[
            BudynekWyjscie(
                nazwa_folderu=b.nazwa_folderu,
                budynek_id=b.budynek_id,
                budynek_nazwa=b.budynek_nazwa,
                foldery=[
                    FolderWyjscie(
                        nazwa=f.nazwa,
                        sciezka_wzgledna=f.sciezka_wzgledna,
                        powiazanie_id=f.powiazanie_id,
                        okres_najmu_id=f.okres_najmu_id,
                        opis_umowy=f.opis_umowy,
                        nowych=f.nowych,
                        pliki=[PlikWyjscie(**vars(p)) for p in f.pliki],
                    )
                    for f in b.foldery
                ],
            )
            for b in wynik.budynki
        ],
    )


@router.post(
    "/powiazania",
    response_model=PowiazanieWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Przypisuje folder do umowy",
)
def powiaz(dane: PowiazanieWejscie, baza: SesjaBazy, request: Request) -> PowiazanieWyjscie:
    """Jednorazowe sparowanie folderu z umową.

    Oznaczenia lokali w nazwach folderów są nieregularne, więc system ich nie
    parsuje — raz wskazuje je człowiek, a system to pamięta.
    """
    if baza.get(OkresNajmu, dane.okres_najmu_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wskazana umowa nie istnieje.")

    istniejace = baza.scalars(
        select(PowiazanieFolderu).where(
            PowiazanieFolderu.sciezka_wzgledna == dane.sciezka_wzgledna,
            PowiazanieFolderu.usunieto_dnia.is_(None),
        )
    ).one_or_none()
    if istniejace is not None:
        # Zmiana przypisania to poprawka pomyłki, a nie błąd. Stare powiązanie
        # zamykamy miękko, żeby ślad po niej został.
        istniejace.usunieto_dnia = datetime.now(UTC)
        zapisz_zmiane(
            baza,
            istniejace,
            operacja=OperacjaAudytu.USUNIECIE,
            adres_ip=_adres(request),
        )
        baza.flush()

    powiazanie = PowiazanieFolderu(
        sciezka_wzgledna=dane.sciezka_wzgledna,
        okres_najmu_id=dane.okres_najmu_id,
        uwagi=dane.uwagi,
    )
    baza.add(powiazanie)
    baza.flush()
    zapisz_zmiane(
        baza,
        powiazanie,
        operacja=OperacjaAudytu.UTWORZENIE,
        adres_ip=_adres(request),
    )
    baza.commit()
    return PowiazanieWyjscie(
        id=powiazanie.id,
        sciezka_wzgledna=powiazanie.sciezka_wzgledna,
        okres_najmu_id=powiazanie.okres_najmu_id,
    )


@router.delete(
    "/powiazania/{powiazanie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Odpina folder od umowy",
)
def odepnij(powiazanie_id: int, baza: SesjaBazy, request: Request) -> None:
    powiazanie = baza.get(PowiazanieFolderu, powiazanie_id)
    if powiazanie is None or powiazanie.usunieto_dnia is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Takiego powiązania nie ma.")

    powiazanie.usunieto_dnia = datetime.now(UTC)
    zapisz_zmiane(
        baza,
        powiazanie,
        operacja=OperacjaAudytu.USUNIECIE,
        adres_ip=_adres(request),
    )
    baza.commit()


@router.post(
    "/importuj",
    response_model=ZaimportowanyWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaje dokument jako odnośnik do pliku na dysku",
)
def zaimportuj(dane: ImportWejscie, baza: SesjaBazy, request: Request) -> ZaimportowanyWyjscie:
    """Plik zostaje tam, gdzie leży. W bazie ląduje ścieżka, skrót i rozmiar.

    Skutek uboczny, który trzeba znać: przeniesienie albo przemianowanie pliku
    w Eksploratorze zrywa odnośnik. Wykrywa to przegląd `/skan/sprawdz`.
    """
    if dane.okres_najmu_id is not None and baza.get(OkresNajmu, dane.okres_najmu_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wskazana umowa nie istnieje.")
    if (
        dane.dokument_nadrzedny_id is not None
        and baza.get(Dokument, dane.dokument_nadrzedny_id) is None
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Wskazany dokument nadrzędny nie istnieje."
        )

    try:
        dokument = usluga_importu(
            baza,
            sciezka_wzgledna=dane.sciezka_wzgledna,
            katalog=katalog_skanu(baza),
            typ=dane.typ,
            okres_najmu_id=dane.okres_najmu_id,
            dokument_nadrzedny_id=dane.dokument_nadrzedny_id,
            numer=dane.numer,
            data_dokumentu=dane.data_dokumentu,
            data_obowiazywania_od=dane.data_obowiazywania_od,
        )
    except BladSkanu as blad:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(blad)) from blad
    except BladPliku as blad:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(blad)) from blad

    zapisz_zmiane(
        baza,
        dokument,
        operacja=OperacjaAudytu.UTWORZENIE,
        adres_ip=_adres(request),
    )
    baza.commit()
    return ZaimportowanyWyjscie(
        id=dokument.id,
        typ=dokument.typ,
        numer=dokument.numer,
        okres_najmu_id=dokument.okres_najmu_id,
        plik_nazwa_oryginalna=dokument.plik_nazwa_oryginalna,
        plik_sciezka=dokument.plik_sciezka,
        rozmiar_bajty=dokument.rozmiar_bajty,
        typ_mime=dokument.typ_mime,
    )


@router.post(
    "/pominiecia",
    response_model=PominiecieWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Zapamiętuje, że tego pliku nie importujemy",
)
def pomin(dane: PominiecieWejscie, baza: SesjaBazy, request: Request) -> PominiecieWyjscie:
    try:
        pominiecie = pomin_plik(
            baza,
            sciezka_wzgledna=dane.sciezka_wzgledna,
            katalog=katalog_skanu(baza),
            powod=dane.powod,
        )
    except BladSkanu as blad:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(blad)) from blad

    zapisz_zmiane(
        baza,
        pominiecie,
        operacja=OperacjaAudytu.UTWORZENIE,
        adres_ip=_adres(request),
    )
    baza.commit()
    return PominiecieWyjscie(
        id=pominiecie.id,
        hash_sha256=pominiecie.hash_sha256,
        nazwa_pliku=pominiecie.nazwa_pliku,
    )


@router.delete(
    "/pominiecia/{pominiecie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cofa pominięcie pliku",
)
def cofnij_pominiecie(pominiecie_id: int, baza: SesjaBazy, request: Request) -> None:
    pominiecie = baza.get(PominietyPlik, pominiecie_id)
    if pominiecie is None or pominiecie.usunieto_dnia is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Takiego pominięcia nie ma.")

    pominiecie.usunieto_dnia = datetime.now(UTC)
    zapisz_zmiane(
        baza,
        pominiecie,
        operacja=OperacjaAudytu.USUNIECIE,
        adres_ip=_adres(request),
    )
    baza.commit()


@router.get(
    "/sprawdz",
    response_model=PrzegladLinkowWyjscie,
    summary="Sprawdza, czy zlinkowane pliki nadal są na miejscu",
)
def sprawdz(baza: SesjaBazy) -> PrzegladLinkowWyjscie:
    """Cena za brak kopiowania: plik przeniesiony w Eksploratorze zrywa odnośnik.

    Ten przegląd ma sprawić, że zerwanie widać od razu, a nie dopiero wtedy,
    gdy dokument jest potrzebny.
    """
    katalog = katalog_skanu(baza)
    zerwane = sprawdz_linki(baza, katalog=katalog)
    wszystkich = baza.scalar(
        select(func.count())
        .select_from(Dokument)
        .where(
            Dokument.usunieto_dnia.is_(None),
            Dokument.przechowywanie == TrybPrzechowywania.LINK,
        )
    )
    return PrzegladLinkowWyjscie(
        katalog=str(katalog) if katalog else None,
        sprawdzonych=wszystkich or 0,
        zerwane=[ZerwanyLinkWyjscie(**vars(z)) for z in zerwane],
    )
