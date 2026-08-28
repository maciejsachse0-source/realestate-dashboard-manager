"""Budynki i lokale. Lokal jest bytem centralnym systemu (decyzja D1)."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from najem.baza import Baza
from najem.domena.slowniki import StatusLokalu, TypLokalu
from najem.modele.wspolne import (
    KluczGlowny,
    MiekkieUsuwanie,
    TypPowierzchni,
    Wersjonowanie,
    ZnacznikiCzasu,
    slownik,
)

if TYPE_CHECKING:
    from najem.modele.najem import ObowiazekPrzegladu, OkresNajmu


class Budynek(Baza, ZnacznikiCzasu, MiekkieUsuwanie, Wersjonowanie):
    """Model zaklada dowolna liczbe budynkow, w tym budynek w budowie
    z lokalami jeszcze niewynajetymi (koncepcja, sekcja 3.2).
    """

    __tablename__ = "budynek"

    id: Mapped[KluczGlowny]
    nazwa: Mapped[str] = mapped_column(String(80), nullable=False)
    #: Nazwa katalogu tego budynku w skanowanym drzewie folderow.
    #: Osobna od nazwy, bo folder na dysku bywa nazwany inaczej niz budynek
    #: w programie, a przemianowanie go nie moze zrywac powiazan dokumentow.
    #: NULL znaczy "ten budynek nie ma jeszcze wskazanego folderu" -- to stan
    #: normalny, a nie brak danych do uzupelnienia.
    nazwa_folderu: Mapped[str | None] = mapped_column(String(200), nullable=True)
    adres: Mapped[str | None] = mapped_column(Text, nullable=True)
    aktywny: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    uwagi: Mapped[str | None] = mapped_column(Text, nullable=True)

    lokale: Mapped[list["Lokal"]] = relationship(back_populates="budynek")

    __table_args__ = (
        Index(
            "uq_budynek_nazwa_aktywny",
            "nazwa",
            unique=True,
            postgresql_where=text("usunieto_dnia IS NULL"),
        ),
        # Dwa budynki wskazujace na ten sam folder oznaczalyby, ze skan nie wie,
        # do ktorego z nich przypisac znalezione tam umowy.
        Index(
            "uq_budynek_folder",
            "nazwa_folderu",
            unique=True,
            postgresql_where=text("nazwa_folderu IS NOT NULL AND usunieto_dnia IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Budynek {self.nazwa!r}>"


class Lokal(Baza, ZnacznikiCzasu, MiekkieUsuwanie, Wersjonowanie):
    """Jedyna rzecz, ktora trwa. Najemcy sie zmieniaja, umowy wygasaja,
    lokal 18A/12 istnieje zawsze (decyzja D1).
    """

    __tablename__ = "lokal"

    id: Mapped[KluczGlowny]
    budynek_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("budynek.id", ondelete="RESTRICT"), nullable=False
    )
    oznaczenie: Mapped[str] = mapped_column(String(60), nullable=False)
    typ: Mapped[TypLokalu] = mapped_column(slownik(TypLokalu), nullable=False)
    status: Mapped[StatusLokalu] = mapped_column(
        slownik(StatusLokalu), nullable=False, server_default=StatusLokalu.WOLNY.value
    )
    kondygnacja: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Powierzchnia z ewidencji i powierzchnia z umowy potrafia sie roznic.
    # Trzymamy obie, a roznice sygnalizuje warstwa domenowa (koncepcja 3.2).
    # Powierzchnia umowna nie jest tu kolumna: wynika z parametru "powierzchnia"
    # i moze zmienic sie aneksem, wiec zyje w parametr_wartosc (decyzja D2).
    powierzchnia_ewidencyjna: Mapped[TypPowierzchni | None] = mapped_column(nullable=True)
    uwagi: Mapped[str | None] = mapped_column(Text, nullable=True)

    budynek: Mapped[Budynek] = relationship(back_populates="lokale")
    okresy_najmu: Mapped[list["OkresNajmu"]] = relationship(back_populates="lokal")
    obowiazki_przegladu: Mapped[list["ObowiazekPrzegladu"]] = relationship(back_populates="lokal")

    __table_args__ = (
        Index(
            "uq_lokal_oznaczenie_w_budynku",
            "budynek_id",
            "oznaczenie",
            unique=True,
            postgresql_where=text("usunieto_dnia IS NULL"),
        ),
        # Dashboard filtruje lokale po budynku i statusie (koncepcja, sekcja 7.1).
        Index("ix_lokal_budynek_status", "budynek_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Lokal {self.oznaczenie!r}>"
