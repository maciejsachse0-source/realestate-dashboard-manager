"""Endpoint diagnostyczny. Przy wdrozeniu on-prem to pierwsze, co sprawdza administrator."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from najem.baza import SesjaBazy
from najem.config import ustawienia

router = APIRouter(tags=["diagnostyka"])


class StanBazy(BaseModel):
    polaczona: bool
    wersja: str | None = None
    blad: str | None = None


class Zdrowie(BaseModel):
    status: Literal["ok", "degradacja"]
    srodowisko: str
    baza: StanBazy


@router.get("/health", response_model=Zdrowie, summary="Stan aplikacji i polaczenia z baza")
def zdrowie(s: SesjaBazy) -> Zdrowie:
    try:
        wersja = s.execute(text("SELECT version()")).scalar_one()
        stan = StanBazy(polaczona=True, wersja=str(wersja).split(",")[0])
    # Lapiemy kazdy wyjatek celowo: diagnostyka ma zglosic awarie, nie wybrane jej rodzaje.
    except Exception as exc:
        stan = StanBazy(polaczona=False, blad=str(exc).splitlines()[0][:200])

    return Zdrowie(
        status="ok" if stan.polaczona else "degradacja",
        srodowisko=ustawienia().srodowisko,
        baza=stan,
    )
