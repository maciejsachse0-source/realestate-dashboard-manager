"""Sesje zalogowanych uzytkownikow.

Sesja w bazie, a nie w samym ciasteczku. Powody sa dwa i oba wynikaja
z sekcji 8 koncepcji: administrator musi moc uniewaznic dostep natychmiast,
a kazdy odczyt danych wrazliwych ma zostawiac slad, ktory da sie powiazac
z konkretnym logowaniem.

W ciasteczku leci sam token. W bazie lezy jego skrot, wiec wyciek zawartosci
tabeli nie pozwala sie nikim podszyc.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from najem.baza import Baza
from najem.modele.wspolne import KluczGlowny, ZnacznikiCzasu


class SesjaUzytkownika(Baza, ZnacznikiCzasu):
    __tablename__ = "sesja_uzytkownika"

    id: Mapped[KluczGlowny]
    uzytkownik_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("uzytkownik.id", ondelete="CASCADE"), nullable=False
    )
    #: SHA-256 tokena. Samego tokena nie zapisujemy nigdzie.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    wygasa: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uniewazniona_dnia: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ostatnia_aktywnosc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    adres_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    __table_args__ = (
        Index("ix_sesja_uzytkownik", "uzytkownik_id"),
        Index("ix_sesja_wygasa", "wygasa"),
    )

    def __repr__(self) -> str:
        return f"<SesjaUzytkownika uzytkownik={self.uzytkownik_id}>"
