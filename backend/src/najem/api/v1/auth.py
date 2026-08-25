"""Logowanie, wylogowanie i zmiana hasla."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from najem.auth.haslo import SlabeHaslo, zahaszuj, zweryfikuj
from najem.auth.sesje import (
    CZAS_ZYCIA,
    NAZWA_CIASTECZKA,
    BladLogowania,
    uniewaznij_wszystkie,
    wyloguj,
    zaloguj,
)
from najem.auth.sesje import teraz_utc as _teraz
from najem.auth.zaleznosci import Zalogowany
from najem.baza import SesjaBazy
from najem.config import ustawienia
from najem.domena.slowniki import OperacjaAudytu, RolaUzytkownika
from najem.uslugi.audyt import zapisz_zmiane

router = APIRouter(prefix="/auth", tags=["uwierzytelnianie"])


class DaneLogowania(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    haslo: str = Field(min_length=1, max_length=256)


class ZmianaHasla(BaseModel):
    haslo_biezace: str = Field(min_length=1, max_length=256)
    haslo_nowe: str = Field(min_length=1, max_length=256)


class ProfilUzytkownika(BaseModel):
    id: int
    login: str
    imie_nazwisko: str
    rola: RolaUzytkownika
    wymaga_zmiany_hasla: bool
    ostatnie_logowanie: datetime | None


def _adres(request: Request) -> str | None:
    return request.client.host if request.client else None


def _ustaw_ciasteczko(odpowiedz: Response, token: str) -> None:
    odpowiedz.set_cookie(
        key=NAZWA_CIASTECZKA,
        value=token,
        httponly=True,
        samesite="lax",
        # Aplikacja chodzi po HTTP na localhost, wiec w dev nie wymuszamy TLS.
        # Przy wdrozeniu za HTTPS ta flaga wlacza sie sama razem ze srodowiskiem.
        secure=ustawienia().czy_produkcja,
        max_age=int(CZAS_ZYCIA.total_seconds()),
        path="/",
    )


@router.post("/logowanie", response_model=ProfilUzytkownika, summary="Logowanie")
def logowanie(
    dane: DaneLogowania,
    request: Request,
    odpowiedz: Response,
    baza: SesjaBazy,
) -> ProfilUzytkownika:
    try:
        uzytkownik, token = zaloguj(
            baza,
            login=dane.login,
            haslo=dane.haslo,
            teraz=_teraz(),
            adres_ip=_adres(request),
        )
    except BladLogowania as blad:
        # Commit mimo bledu: licznik nieudanych prob i blokada konta musza
        # przetrwac odrzucone logowanie, inaczej limit prob nie dziala.
        baza.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(blad)) from blad

    baza.commit()
    _ustaw_ciasteczko(odpowiedz, token)
    return ProfilUzytkownika.model_validate(uzytkownik, from_attributes=True)


@router.post("/wylogowanie", status_code=status.HTTP_204_NO_CONTENT, summary="Wylogowanie")
def wylogowanie(request: Request, odpowiedz: Response, baza: SesjaBazy) -> None:
    token = request.cookies.get(NAZWA_CIASTECZKA)
    if token:
        wyloguj(baza, token, _teraz())
        baza.commit()
    odpowiedz.delete_cookie(NAZWA_CIASTECZKA, path="/")


@router.get("/ja", response_model=ProfilUzytkownika, summary="Kto jest zalogowany")
def ja(zalogowany: Zalogowany, baza: SesjaBazy) -> ProfilUzytkownika:
    baza.commit()  # zapisuje znacznik ostatniej aktywnosci sesji
    return ProfilUzytkownika.model_validate(zalogowany.uzytkownik, from_attributes=True)


@router.post(
    "/haslo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Zmiana własnego hasła",
)
def zmiana_hasla(dane: ZmianaHasla, zalogowany: Zalogowany, baza: SesjaBazy) -> None:
    uzytkownik = zalogowany.uzytkownik

    if not zweryfikuj(uzytkownik.hash_hasla, dane.haslo_biezace):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bieżące hasło jest nieprawidłowe.")
    if dane.haslo_nowe == dane.haslo_biezace:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nowe hasło musi różnić się od obecnego.")

    try:
        uzytkownik.hash_hasla = zahaszuj(dane.haslo_nowe)
    except SlabeHaslo as blad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(blad)) from blad

    uzytkownik.wymaga_zmiany_hasla = False
    zapisz_zmiane(
        baza,
        uzytkownik,
        operacja=OperacjaAudytu.ZMIANA,
        uzytkownik_id=uzytkownik.id,
        pola={"hash_hasla", "wymaga_zmiany_hasla"},
    )
    # Zmiana hasla wylogowuje ze wszystkich urzadzen. Jesli powodem zmiany bylo
    # podejrzenie przejecia konta, pozostawienie starych sesji czynnymi
    # niweczy caly sens operacji.
    uniewaznij_wszystkie(baza, uzytkownik.id, _teraz())
    baza.commit()
