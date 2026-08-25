"""Endpoint administracyjny generatora zdarzen.

Przydatny w testach, przy diagnozowaniu i przy pierwszym uruchomieniu systemu,
gdy nikt nie chce czekac do 6:00 rano.

Uwierzytelnianie i role wchodza w etapie E4. Do tego czasu endpoint jest otwarty,
ale aplikacja slucha wylacznie na petli zwrotnej.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from najem.baza import SesjaBazy
from najem.uslugi.generator_zdarzen import uruchom_generator
from najem.zadania.harmonogram import dzis_lokalnie

router = APIRouter(prefix="/zdarzenia", tags=["zdarzenia"])


class WynikPrzebiegu(BaseModel):
    data_odniesienia: date
    umow_sprawdzonych: int = Field(description="Ile okresów najmu przeszło przez generator")
    zdarzen_wyliczonych: int = Field(description="Ile zdarzeń powinno istnieć na ten dzień")
    zdarzen_dodanych: int = Field(description="Ile faktycznie dopisano")
    zdarzen_pominietych: int = Field(description="Ile już było w bazie")


@router.post(
    "/generuj",
    response_model=WynikPrzebiegu,
    summary="Uruchamia generator zdarzeń ręcznie",
)
def generuj(
    sesja: SesjaBazy,
    na_dzien: Annotated[
        date | None,
        Query(description="Data odniesienia. Domyślnie dzisiaj w strefie prezentacji."),
    ] = None,
) -> WynikPrzebiegu:
    wynik = uruchom_generator(sesja, na_dzien or dzis_lokalnie())
    sesja.commit()
    return WynikPrzebiegu(
        data_odniesienia=wynik.data_odniesienia,
        umow_sprawdzonych=wynik.umow_sprawdzonych,
        zdarzen_wyliczonych=wynik.zdarzen_wyliczonych,
        zdarzen_dodanych=wynik.zdarzen_dodanych,
        zdarzen_pominietych=wynik.zdarzen_pominietych,
    )
