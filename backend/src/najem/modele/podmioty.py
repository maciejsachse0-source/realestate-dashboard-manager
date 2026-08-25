"""Uzytkownicy systemu i najemcy.

Najemca to tor B z decyzji D3: dane poufne wprowadzane recznie w programie,
nigdy nie przechodzace przez ekstrakcje z dokumentu.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from najem.baza import Baza
from najem.domena.slowniki import RolaUzytkownika
from najem.modele.wspolne import (
    KluczGlowny,
    MiekkieUsuwanie,
    Wersjonowanie,
    ZnacznikiCzasu,
    slownik,
)

if TYPE_CHECKING:
    from najem.modele.najem import OkresNajmu


class Uzytkownik(Baza, ZnacznikiCzasu, Wersjonowanie):
    """Logowanie imienne, bez kont wspoldzielonych (koncepcja, sekcja 8.1 punkt 5).

    Uwierzytelnianie wchodzi w etapie E4. Tu jest sam nosnik danych.
    """

    __tablename__ = "uzytkownik"

    id: Mapped[KluczGlowny]
    login: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    imie_nazwisko: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    hash_hasla: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rola: Mapped[RolaUzytkownika] = mapped_column(slownik(RolaUzytkownika), nullable=False)
    aktywny: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    # Wymuszona zmiana hasla przy pierwszym logowaniu (plan, sekcja 1.2 punkt K).
    wymaga_zmiany_hasla: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    nieudane_logowania: Mapped[int] = mapped_column(nullable=False, server_default="0")
    zablokowany_do: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ostatnie_logowanie: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Uzytkownik {self.login} ({self.rola})>"


class Najemca(Baza, ZnacznikiCzasu, MiekkieUsuwanie, Wersjonowanie):
    """Tor B: dane poufne. Nigdy nie trafiaja do pipeline'u ekstrakcji.

    Najemca jest osobnym bytem, a nie polem w umowie, bo ten sam podmiot moze
    wynajmowac kilka lokali w kilku budynkach (koncepcja, sekcja 3.2).
    """

    __tablename__ = "najemca"

    id: Mapped[KluczGlowny]
    nazwa_pelna: Mapped[str] = mapped_column(String(300), nullable=False)
    nip: Mapped[str | None] = mapped_column(String(10), nullable=True)
    regon: Mapped[str | None] = mapped_column(String(14), nullable=True)
    krs: Mapped[str | None] = mapped_column(String(10), nullable=True)

    adres_siedziby: Mapped[str | None] = mapped_column(Text, nullable=True)
    adres_korespondencyjny: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    telefon: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Czy najemca jest osoba fizyczna. Decyduje o tym, czy stosuje sie RODO
    # w pelnym zakresie (koncepcja, sekcja 8.1 punkt 8).
    osoba_fizyczna: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    notatki: Mapped[str | None] = mapped_column(Text, nullable=True)

    osoby_kontaktowe: Mapped[list["OsobaKontaktowa"]] = relationship(
        back_populates="najemca", cascade="all, delete-orphan"
    )
    okresy_najmu: Mapped[list["OkresNajmu"]] = relationship(back_populates="najemca")

    __table_args__ = (
        # NIP unikalny tylko wsrod nieusunietych. Po usunieciu podmiotu ten sam
        # NIP musi dac sie wprowadzic ponownie.
        Index(
            "uq_najemca_nip_aktywny",
            "nip",
            unique=True,
            postgresql_where=text("nip IS NOT NULL AND usunieto_dnia IS NULL"),
        ),
        # Wyszukiwanie po fragmencie nazwy. pg_trgm radzi sobie z polska odmiana
        # lepiej niz konfiguracja pelnotekstowa bez slownika (plan, punkt I).
        Index(
            "ix_najemca_nazwa_trgm",
            "nazwa_pelna",
            postgresql_using="gin",
            postgresql_ops={"nazwa_pelna": "gin_trgm_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<Najemca {self.nazwa_pelna!r}>"


class OsobaKontaktowa(Baza, ZnacznikiCzasu, MiekkieUsuwanie):
    """Tor B. Osobna tabela, bo najemca ma zwykle kilka osob do kontaktu."""

    __tablename__ = "osoba_kontaktowa"

    id: Mapped[KluczGlowny]
    najemca_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("najemca.id", ondelete="CASCADE"), nullable=False, index=True
    )
    imie_nazwisko: Mapped[str] = mapped_column(String(160), nullable=False)
    stanowisko: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    telefon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    uwagi: Mapped[str | None] = mapped_column(Text, nullable=True)

    najemca: Mapped[Najemca] = relationship(back_populates="osoby_kontaktowe")

    def __repr__(self) -> str:
        return f"<OsobaKontaktowa {self.imie_nazwisko!r}>"
