"""Mapowanie wyjatkow domenowych i bazodanowych na kody HTTP.

Jeden handler na rodzaj bledu, a nie try/except w kazdym endpoincie
(regula z .claude/rules/backend.md).
"""

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from najem.auth.haslo import SlabeHaslo
from najem.domena.stany import NiedozwolonePrzejscie

log = structlog.get_logger(__name__)


def zarejestruj_handlery(app: FastAPI) -> None:
    @app.exception_handler(StaleDataError)
    async def konflikt_wersji(_: Request, blad: StaleDataError) -> JSONResponse:
        """Optimistic locking: ktos zapisal zmiany, zanim my zdazylismy.

        Kod 409 wraz z komunikatem, ktory mowi uzytkownikowi, co zrobic.
        Front ma odswiezyc rekord i pokazac roznice, a nie nadpisac po cichu.
        """
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": (
                    "Ktoś zapisał zmiany w tym rekordzie, zanim zdążyłeś zapisać swoje. "
                    "Odśwież widok i wprowadź zmiany ponownie."
                )
            },
        )

    @app.exception_handler(NiedozwolonePrzejscie)
    async def zle_przejscie(_: Request, blad: NiedozwolonePrzejscie) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": str(blad)},
        )

    @app.exception_handler(SlabeHaslo)
    async def slabe_haslo(_: Request, blad: SlabeHaslo) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(blad)},
        )

    @app.exception_handler(ValueError)
    async def bledna_wartosc(_: Request, blad: ValueError) -> JSONResponse:
        """Reguly domenowe zglaszaja niepoprawne dane przez ValueError."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": str(blad)},
        )

    @app.exception_handler(IntegrityError)
    async def naruszenie_spojnosci(_: Request, blad: IntegrityError) -> JSONResponse:
        """Ograniczenia bazy sa ostatnia linia obrony, wiec ich naruszenie
        znaczy, ze walidacja wyzej czegos nie zlapala. Logujemy szczegoly,
        a uzytkownikowi pokazujemy komunikat bez wnetrznosci SQL.
        """
        log.warning("naruszenie_spojnosci", blad=str(blad.orig))
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": (
                    "Operacja narusza spójność danych. "
                    "Sprawdź, czy rekord o takich danych już nie istnieje."
                )
            },
        )
