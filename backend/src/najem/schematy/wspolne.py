"""Wspolne ksztalty odpowiedzi API."""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

#: Domyslny i maksymalny rozmiar strony (regula z .claude/rules/backend.md).
LIMIT_DOMYSLNY = 50
LIMIT_MAKSYMALNY = 500


class Paginacja(BaseModel):
    """Parametry stronicowania. Kazdy endpoint listujacy je przyjmuje."""

    limit: Annotated[int, Query(ge=1, le=LIMIT_MAKSYMALNY)] = LIMIT_DOMYSLNY
    offset: Annotated[int, Query(ge=0)] = 0


class Strona[T](BaseModel):
    """Strona wynikow wraz z liczba wszystkich pasujacych rekordow.

    `wszystkich` jest potrzebne tabeli na froncie do pokazania, ile jeszcze
    zostalo. Bez tego uzytkownik nie wie, czy filtr zawezil wynik do trzech
    pozycji, czy tylko pokazal pierwsze trzy z tysiaca.
    """

    pozycje: list[T]
    wszystkich: int
    limit: int
    offset: int


class Blad(BaseModel):
    """Ksztalt odpowiedzi bledu. Komunikat jest po polsku i dla czlowieka."""

    detail: str = Field(description="Co poszło nie tak, w języku użytkownika")


class KonfliktWersji(BaseModel):
    """Odpowiedz 409: ktos zapisal zmiany w miedzyczasie."""

    detail: str
    wersja_biezaca: int = Field(description="Wersja, która jest teraz w bazie")
