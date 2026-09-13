"""Zdarzenia terminowe i log audytu.

Zdarzenia sa produktem regul z sekcji 5 koncepcji. Nikt ich nie tworzy recznie,
poza wyjatkiem "zadanie wlasne". Generator powstaje w etapie E3.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from najem.baza import Baza
from najem.domena.slowniki import (
    OperacjaAudytu,
    RodzajWskaznika,
    StatusZdarzenia,
    TypZdarzenia,
    WagaZdarzenia,
)
from najem.modele.wspolne import (
    KluczGlowny,
    MiekkieUsuwanie,
    TypStawkiVat,
    Wersjonowanie,
    ZnacznikiCzasu,
    slownik,
)


class Zdarzenie(Baza, ZnacznikiCzasu, MiekkieUsuwanie, Wersjonowanie):
    """Alert terminowy. Katalog typow w sekcji 6 koncepcji.

    Klucz naturalny (typ, encja, data) jest unikalny, zeby generator uruchomiony
    trzy razy tego samego dnia dal ten sam efekt co jedno uruchomienie
    (plan budowy, sekcja 1.2 punkt M). Idempotencja jest wymuszona w bazie,
    a nie tylko w kodzie, bo to jedyne miejsce, ktore nie zapomni.
    """

    __tablename__ = "zdarzenie"

    id: Mapped[KluczGlowny]
    typ: Mapped[TypZdarzenia] = mapped_column(slownik(TypZdarzenia, dlugosc=64), nullable=False)

    #: Nazwa tabeli encji zrodlowej, np. okres_najmu, zabezpieczenie.
    encja_typ: Mapped[str] = mapped_column(String(40), nullable=False)
    encja_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: Powielone z encji zrodlowej, zeby kokpit terminow mogl filtrowac po lokalu
    #: i budynku bez laczenia czterech tabel przy kazdym odswiezeniu listy.
    lokal_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("lokal.id", ondelete="CASCADE"), nullable=True
    )

    data_zdarzenia: Mapped[date] = mapped_column(Date, nullable=False)
    waga: Mapped[WagaZdarzenia] = mapped_column(slownik(WagaZdarzenia), nullable=False)
    status: Mapped[StatusZdarzenia] = mapped_column(
        slownik(StatusZdarzenia), nullable=False, server_default=StatusZdarzenia.OTWARTE.value
    )
    tresc: Mapped[str] = mapped_column(String(500), nullable=False)

    odroczone_do: Mapped[date | None] = mapped_column(Date, nullable=True)
    obsluzone_dnia: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notatka: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status <> 'odroczone' OR odroczone_do IS NOT NULL",
            name="ck_zdarzenie_odroczenie_ma_termin",
        ),
        # Klucz naturalny idempotencji. Bez WHERE na usunieto_dnia, bo zdarzenie
        # usuniete miekko nadal ma blokowac ponowne wygenerowanie tego samego.
        Index(
            "uq_zdarzenie_klucz_naturalny",
            "typ",
            "encja_typ",
            "encja_id",
            "data_zdarzenia",
            unique=True,
        ),
        # Kokpit terminow: otwarte zdarzenia wedlug pilnosci (koncepcja, 7.3).
        Index(
            "ix_zdarzenie_otwarte",
            "data_zdarzenia",
            "waga",
            postgresql_where=text("status = 'otwarte' AND usunieto_dnia IS NULL"),
        ),
        Index("ix_zdarzenie_lokal_status", "lokal_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Zdarzenie {self.typ} {self.data_zdarzenia} {self.status}>"


class WskaznikWaloryzacji(Baza, ZnacznikiCzasu, Wersjonowanie):
    """Wskaznik wprowadzany raz w roku, dzialajacy na wszystkich umowach (regula R2).

    Osobna tabela, bo administrator wpisuje wartosc jeden raz, a system znajduje
    umowy do przeliczenia. Dzis to kilkanascie godzin pracy recznej rocznie.
    """

    __tablename__ = "wskaznik_waloryzacji"

    id: Mapped[KluczGlowny]
    rok: Mapped[int] = mapped_column(Integer, nullable=False)
    rodzaj: Mapped[RodzajWskaznika] = mapped_column(slownik(RodzajWskaznika), nullable=False)
    #: Wartosc w procentach, np. 3.70 dla wskaznika 3,7 procent.
    wartosc_procent: Mapped[TypStawkiVat] = mapped_column(nullable=False)
    data_publikacji: Mapped[date | None] = mapped_column(Date, nullable=True)
    uwagi: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("uq_wskaznik_rok_rodzaj", "rok", "rodzaj", unique=True),
        CheckConstraint("rok BETWEEN 2000 AND 2200", name="ck_wskaznik_rozsadny_rok"),
    )

    def __repr__(self) -> str:
        return f"<WskaznikWaloryzacji {self.rok} {self.rodzaj} {self.wartosc_procent}%>"


class LogAudytu(Baza):
    """Tabela tylko do zapisu. Kto, kiedy, co zmienil, z jakiej wartosci na jaka.

    Nie dziedziczy po MiekkieUsuwanie ani Wersjonowanie celowo: log audytu
    nie jest edytowalny i nie jest usuwalny. Wymusza to wyzwalacz zalozony
    w migracji, a nie sama konwencja w kodzie.
    """

    __tablename__ = "log_audytu"

    id: Mapped[KluczGlowny]
    kiedy: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    operacja: Mapped[OperacjaAudytu] = mapped_column(slownik(OperacjaAudytu), nullable=False)

    tabela: Mapped[str] = mapped_column(String(60), nullable=False)
    rekord_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pole: Mapped[str | None] = mapped_column(String(80), nullable=True)
    wartosc_stara: Mapped[str | None] = mapped_column(Text, nullable=True)
    wartosc_nowa: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Identyfikator zadania HTTP, przechodzacy przez caly stos.
    #: Przy wdrozeniu on-prem bez monitoringu to jedyne narzedzie diagnostyczne
    #: (plan budowy, sekcja 1.2 punkt P).
    id_zadania: Mapped[str | None] = mapped_column(String(64), nullable=True)
    adres_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    __table_args__ = (
        Index("ix_audyt_rekord", "tabela", "rekord_id", "kiedy"),
        Index("ix_audyt_kiedy", "kiedy"),
    )

    def __repr__(self) -> str:
        return f"<LogAudytu {self.operacja} {self.tabela}#{self.rekord_id}>"
