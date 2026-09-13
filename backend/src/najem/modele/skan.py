"""Skan folderow z dokumentami na dysku uzytkownika.

Dwie tabele, obie sluza jednemu celowi: zeby czlowiek nie odpowiadal drugi raz
na pytanie, na ktore juz odpowiedzial.

`PowiazanieFolderu` pamieta, ktora umowa kryje sie za ktorym folderem.
Oznaczenia lokali w nazwach folderow sa nieregularne (raz od zera, raz od
jedynki, czasem "1.A" i "1.B", czasem z podkresleniem), wiec system ich nie
parsuje. Parowanie robi czlowiek raz, a system je zapamietuje. Zgadywanie
dawaloby ciche pomylki, a to jest dokladnie to, czego zakazuje decyzja D5.

`PominietyPlik` pamieta pliki, ktorych czlowiek swiadomie nie zaimportowal.
Bez tego kazdy kolejny skan pokazywalby te same odrzucone pliki i lista
nigdy by sie nie wyczyscila.
"""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from najem.baza import Baza
from najem.modele.wspolne import KluczGlowny, MiekkieUsuwanie, ZnacznikiCzasu

if TYPE_CHECKING:
    from najem.modele.najem import OkresNajmu


class PowiazanieFolderu(Baza, ZnacznikiCzasu, MiekkieUsuwanie):
    """Jeden folder na dysku odpowiada jednej umowie.

    U uzytkownika nowy najemca oznacza nowy folder, wiec relacja jest jeden
    do jednego. Gdyby kiedys w jednym folderze znalazly sie dwie umowy,
    powiazanie wskazuje te, ktora czlowiek wybral przy parowaniu, a pozostale
    dokumenty da sie przy imporcie przypiac do innej umowy recznie.
    """

    __tablename__ = "powiazanie_folderu"

    id: Mapped[KluczGlowny]
    #: Sciezka wzgledna wzgledem katalogu skanowanego, z ukosnikami "/".
    #: Np. "Rycerska/Umowy najmu/Lokal nr 3_Kowalski".
    sciezka_wzgledna: Mapped[str] = mapped_column(String(500), nullable=False)
    okres_najmu_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("okres_najmu.id", ondelete="RESTRICT"), nullable=False
    )
    uwagi: Mapped[str | None] = mapped_column(Text, nullable=True)

    okres_najmu: Mapped["OkresNajmu"] = relationship()

    __table_args__ = (
        Index(
            "uq_powiazanie_folderu_sciezka",
            "sciezka_wzgledna",
            unique=True,
            postgresql_where=text("usunieto_dnia IS NULL"),
        ),
        Index("ix_powiazanie_folderu_okres", "okres_najmu_id"),
    )

    def __repr__(self) -> str:
        return f"<PowiazanieFolderu {self.sciezka_wzgledna!r} -> {self.okres_najmu_id}>"


class PominietyPlik(Baza, ZnacznikiCzasu, MiekkieUsuwanie):
    """Plik, ktorego czlowiek swiadomie nie zaimportowal.

    Pamietamy skrot tresci, a nie sciezke: plik przemianowany albo przeniesiony
    do innego folderu to nadal ten sam plik i nadal ma sie nie pokazywac.

    Cofniecie pominiecia jest miekkim usunieciem wiersza, a nie kasowaniem.
    Slad po decyzji zostaje, tak jak wszedzie indziej w tym systemie.
    """

    __tablename__ = "pominiety_plik"

    id: Mapped[KluczGlowny]
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Nazwa i sciezka z chwili pominiecia. Wylacznie po to, zeby czlowiek
    #: rozpoznal na liscie, co kiedys odrzucil. Do dopasowania sluzy skrot.
    nazwa_pliku: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sciezka_wzgledna: Mapped[str | None] = mapped_column(String(500), nullable=True)
    powod: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (
        CheckConstraint("char_length(hash_sha256) = 64", name="ck_pominiety_dlugosc_hasha"),
        Index(
            "uq_pominiety_plik_hash",
            "hash_sha256",
            unique=True,
            postgresql_where=text("usunieto_dnia IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<PominietyPlik {self.nazwa_pliku!r}>"
