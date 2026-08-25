"""Silnik i sesje SQLAlchemy. Warstwa domenowa nigdy tego nie importuje."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from najem.config import ustawienia


class Baza(DeclarativeBase):
    """Wspolna baza deklaratywna dla wszystkich modeli."""


# connect_timeout: bez niego /health wisi w nieskonczonosc, gdy baza nie stoi.
# Diagnostyka ma raportowac awarie, nie zawieszac sie razem z nia.
silnik = create_engine(
    ustawienia().baza_url,
    pool_pre_ping=True,
    future=True,
    connect_args={"connect_timeout": 3},
)
TworzSesje = sessionmaker(bind=silnik, autoflush=False, expire_on_commit=False)


def sesja() -> Iterator[Session]:
    """Zaleznosc FastAPI: jedna sesja na zadanie."""
    with TworzSesje() as s:
        yield s


# Idiom FastAPI: zaleznosc w typie, nie w wartosci domyslnej argumentu.
SesjaBazy = Annotated[Session, Depends(sesja)]
