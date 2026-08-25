"""Fundamenty wspolne dla wszystkich modeli: kwoty, czas, usuwanie, wersjonowanie."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


def slownik(typ: type[StrEnum], *, dlugosc: int = 48) -> Enum:
    """Slownik jako VARCHAR z ograniczeniem CHECK, nie jako typ natywny bazy.

    Dwa powody. Po pierwsze rozszerzenie listy wartosci to zmiana ograniczenia,
    a nie ALTER TYPE, ktory w Postgresie nie cofa sie w migracji. Po drugie
    values_callable sprawia, ze w bazie leza wartosci ("aktywna"), a nie nazwy
    skladowych ("AKTYWNA") - SQLAlchemy domyslnie zapisuje te drugie.
    """
    return Enum(
        typ,
        native_enum=False,
        length=dlugosc,
        values_callable=lambda skladowe: [s.value for s in skladowe],
        validate_strings=True,
    )


# --------------------------------------------------------------------- typy pol

#: Klucz glowny. Wybor uzasadniony w docs/decyzje/003-klucze-bigserial.md.
KluczGlowny = Annotated[int, mapped_column(BigInteger, primary_key=True, autoincrement=True)]

#: Kwota pieniezna. NIGDY float. Plan budowy, sekcja 1.1 punkt C.
TypKwoty = Annotated[Decimal, mapped_column(Numeric(12, 2))]

#: Stawka VAT w procentach, np. 23.00. Osobna od kwoty, bo bywa inna niz 23.
TypStawkiVat = Annotated[Decimal, mapped_column(Numeric(5, 2))]

#: Kod waluty ISO 4217. Bez wartosci domyslnej celowo: czynsz bywa w EUR
#: (plan budowy, punkt B), a baza, ktora sama dopisuje "PLN", zamienia brak
#: danych w fakt. Decyzja D5. Podpowiedz PLN nalezy do formularza, nie do bazy.
TypWaluty = Annotated[str, mapped_column(String(3))]

#: Powierzchnia w metrach kwadratowych.
TypPowierzchni = Annotated[Decimal, mapped_column(Numeric(10, 2))]


# ------------------------------------------------------------------- domieszki


class ZnacznikiCzasu:
    """Kiedy rekord powstal i kiedy byl ostatnio zmieniany. Zawsze w UTC."""

    utworzono: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    zmodyfikowano: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MiekkieUsuwanie:
    """Nic nie kasujemy fizycznie. W systemie, ktory ma rozstrzygac spory
    z najemcami, twarde usuniecie rekordu to problem prawny, nie techniczny.

    Zapytania domyslnie filtruja `usunieto_dnia IS NULL`, a indeksy unikalne
    sa czesciowe, zeby po usunieciu dalo sie zalozyc rekord o tym samym kluczu.
    """

    usunieto_dnia: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    @declared_attr
    def usunal_uzytkownik_id(cls) -> Mapped[int | None]:  # noqa: N805
        return mapped_column(
            BigInteger, ForeignKey("uzytkownik.id", ondelete="RESTRICT"), nullable=True
        )

    @property
    def czy_usuniety(self) -> bool:
        return self.usunieto_dnia is not None


class Wersjonowanie:
    """Optimistic locking. Dwie osoby otwieraja ten sam profil lokalu i zapisuja:
    druga dostaje konflikt, zamiast po cichu nadpisac zmiany pierwszej.

    SQLAlchemy podbija `wersja` sam i rzuca StaleDataError, gdy UPDATE nie trafil
    w zaden wiersz. Warstwa API mapuje to na kod 409.
    """

    wersja: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="1")

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, Any]:  # noqa: N805
        return {"version_id_col": cls.__dict__["wersja"]}
