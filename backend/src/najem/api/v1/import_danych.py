"""Import startowy z arkusza: podgląd i wykonanie.

Kreator ma dwa kroki i to jest celowe. Pierwszy pokazuje, co system zrozumiał
i co go zatrzymuje. Drugi zapisuje. Nikt nie zapisuje danych, których wcześniej
nie zobaczył.
"""

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from najem.auth.zaleznosci import Zarzadca
from najem.baza import SesjaBazy
from najem.dokumenty.arkusz import (
    WIERSZE_PODGLADU,
    BladArkusza,
    nazwy_arkuszy,
    wczytaj_arkusz,
)
from najem.domena.import_arkusza import PoleImportu, sprawdz_arkusz
from najem.uslugi.import_danych import ImportPrzerwany, zaimportuj

router = APIRouter(prefix="/import", tags=["import"])

#: Mapowanie kolumn: nazwa nagłówka w arkuszu → pole systemu.
Mapowanie = dict[str, PoleImportu]


class BladWierszaWyjscie(BaseModel):
    wiersz: int
    pole: str | None
    komunikat: str
    opis: str = Field(description="Gotowe zdanie do pokazania użytkownikowi")


class PodgladArkusza(BaseModel):
    """Co system znalazł w pliku, zanim cokolwiek zapisze."""

    naglowki: list[str]
    arkusze: list[str]
    wierszy_w_pliku: int
    wierszy_poprawnych: int
    bledy: list[BladWierszaWyjscie]
    podglad: list[dict[str, str]] = Field(
        description="Pierwsze wiersze po zmapowaniu, do obejrzenia przed importem"
    )
    pola_dostepne: list[str] = Field(description="Na co można zmapować kolumnę")


class WynikImportuWyjscie(BaseModel):
    budynkow_dodanych: int
    lokali_dodanych: int
    najemcow_dodanych: int
    umow_dodanych: int
    warunkow_dodanych: int
    skladnikow_dodanych: int
    wierszy_pominietych: int
    pominiecia: list[str]


def _mapowanie_z_tekstu(surowe: str) -> Mapowanie:
    """Mapowanie przychodzi jako JSON w polu formularza, obok pliku."""
    try:
        dane = json.loads(surowe)
    except json.JSONDecodeError as blad:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Mapowanie kolumn nie jest poprawnym JSON-em."
        ) from blad

    if not isinstance(dane, dict):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Mapowanie kolumn ma być obiektem: nazwa kolumny na pole systemu.",
        )

    mapowanie: Mapowanie = {}
    for kolumna, pole in dane.items():
        if pole in (None, ""):
            continue
        try:
            mapowanie[str(kolumna)] = PoleImportu(str(pole))
        except ValueError as blad:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Nieznane pole systemu: „{pole}”. Dostępne: "
                + ", ".join(p.value for p in PoleImportu),
            ) from blad
    return mapowanie


def _na_slowniki(
    naglowki: list[str], wiersze: list[list[object]], mapowanie: Mapowanie
) -> list[dict[PoleImportu, object]]:
    """Zamienia wiersze arkusza na słowniki pól systemu."""
    indeksy = {
        indeks: mapowanie[naglowek]
        for indeks, naglowek in enumerate(naglowki)
        if naglowek in mapowanie
    }
    wynik: list[dict[PoleImportu, object]] = []
    for wiersz in wiersze:
        komorki: dict[PoleImportu, object] = {}
        for indeks, pole in indeksy.items():
            if indeks < len(wiersz):
                komorki[pole] = wiersz[indeks]
        wynik.append(komorki)
    return wynik


@router.post("/podglad", response_model=PodgladArkusza, summary="Krok 1: co jest w pliku")
async def podglad(
    baza: SesjaBazy,
    _: Zarzadca,
    plik: Annotated[UploadFile, File(description="Arkusz XLSX")],
    mapowanie: Annotated[str, Form(description='JSON: {"Nazwa kolumny": "pole_systemu"}')] = "{}",
    nazwa_arkusza: Annotated[str | None, Form()] = None,
) -> PodgladArkusza:
    """Odczytuje plik, sprawdza wiersze i pokazuje wynik. Niczego nie zapisuje."""
    zawartosc = await plik.read()

    try:
        arkusze = nazwy_arkuszy(zawartosc)
        odczytany = wczytaj_arkusz(zawartosc, nazwa_arkusza=nazwa_arkusza)
    except BladArkusza as blad:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(blad)) from blad

    mapa = _mapowanie_z_tekstu(mapowanie)
    komorki = _na_slowniki(odczytany.naglowki, odczytany.wiersze, mapa)
    wynik = sprawdz_arkusz(komorki)

    podglad_wierszy = [
        {pole.value: str(wartosc) for pole, wartosc in komplet.items() if wartosc is not None}
        for komplet in komorki[:WIERSZE_PODGLADU]
    ]

    return PodgladArkusza(
        naglowki=odczytany.naglowki,
        arkusze=arkusze,
        wierszy_w_pliku=odczytany.liczba_wierszy,
        wierszy_poprawnych=len(wynik.wiersze),
        bledy=[
            BladWierszaWyjscie(wiersz=b.wiersz, pole=b.pole, komunikat=b.komunikat, opis=str(b))
            for b in wynik.bledy
        ],
        podglad=podglad_wierszy,
        pola_dostepne=[p.value for p in PoleImportu],
    )


@router.post("/wykonaj", response_model=WynikImportuWyjscie, summary="Krok 2: zapisz")
async def wykonaj(
    baza: SesjaBazy,
    kto: Zarzadca,
    request: Request,
    plik: Annotated[UploadFile, File(description="Arkusz XLSX")],
    mapowanie: Annotated[str, Form(description='JSON: {"Nazwa kolumny": "pole_systemu"}')],
    nazwa_arkusza: Annotated[str | None, Form()] = None,
) -> WynikImportuWyjscie:
    """Zapisuje cały arkusz albo nic.

    Przy jakimkolwiek błędzie zwraca 422 z listą problemów i numerami wierszy,
    a baza zostaje nietknięta.
    """
    zawartosc = await plik.read()

    try:
        odczytany = wczytaj_arkusz(zawartosc, nazwa_arkusza=nazwa_arkusza)
    except BladArkusza as blad:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(blad)) from blad

    mapa = _mapowanie_z_tekstu(mapowanie)
    komorki = _na_slowniki(odczytany.naglowki, odczytany.wiersze, mapa)
    sprawdzenie = sprawdz_arkusz(komorki)

    try:
        wynik = zaimportuj(
            baza,
            sprawdzenie.wiersze,
            sprawdzenie.bledy,
            uzytkownik_id=kto.uzytkownik.id,
        )
    except ImportPrzerwany as blad:
        # Rollback jest jawny, żeby nie zależeć od tego, co zrobi zależność sesji.
        baza.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "komunikat": f"Arkusz ma {len(blad.bledy)} błędów. Nie zapisano niczego.",
                "bledy": [str(b) for b in blad.bledy],
            },
        ) from blad

    baza.commit()
    return WynikImportuWyjscie(
        budynkow_dodanych=wynik.budynkow_dodanych,
        lokali_dodanych=wynik.lokali_dodanych,
        najemcow_dodanych=wynik.najemcow_dodanych,
        umow_dodanych=wynik.umow_dodanych,
        warunkow_dodanych=wynik.warunkow_dodanych,
        skladnikow_dodanych=wynik.skladnikow_dodanych,
        wierszy_pominietych=wynik.wierszy_pominietych,
        pominiecia=wynik.pominiecia,
    )
