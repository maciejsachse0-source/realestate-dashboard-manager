"""Okres najmu i to, co do niego przypiete: oplaty, zabezpieczenia, przeglady."""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from najem.baza import Baza
from najem.domena.slowniki import (
    BazaOkresuNajmu,
    KtoObciazany,
    OkresRozliczeniowy,
    RodzajKwoty,
    RodzajWskaznika,
    RodzajZabezpieczenia,
    StatusOkresuNajmu,
    StatusPrzegladu,
    StatusZabezpieczenia,
)
from najem.modele.wspolne import (
    KluczGlowny,
    MiekkieUsuwanie,
    TypKwoty,
    TypStawkiVat,
    TypWaluty,
    Wersjonowanie,
    ZnacznikiCzasu,
    slownik,
)

if TYPE_CHECKING:
    from najem.modele.dokumenty import Dokument, ParametrWartosc
    from najem.modele.organizacja import Lokal
    from najem.modele.podmioty import Najemca


class OkresNajmu(Baza, ZnacznikiCzasu, MiekkieUsuwanie, Wersjonowanie):
    """Kluczowa encja posredniczaca: jeden najemca, jeden ciag umowny, jeden lokal.

    Relacja najemca-lokal jest wiele do wielu rozlozona w czasie, wiec nie da sie
    jej trzymac jako pola. Stad ta tabela (koncepcja, sekcja 3.3).
    """

    __tablename__ = "okres_najmu"

    id: Mapped[KluczGlowny]
    lokal_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("lokal.id", ondelete="RESTRICT"), nullable=False
    )
    najemca_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("najemca.id", ondelete="RESTRICT"), nullable=False
    )

    data_zawarcia: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_przekazania: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Regula R1: okres liczy sie od daty przekazania, nie od podpisania.
    # To pole mowi systemowi, ktora date wziac do wyliczenia konca umowy.
    bazuje_na_dacie: Mapped[BazaOkresuNajmu] = mapped_column(
        slownik(BazaOkresuNajmu),
        nullable=False,
        server_default=BazaOkresuNajmu.DATA_PRZEKAZANIA.value,
    )
    okres_zawarcia_miesiace: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Wyliczana z reguly R1. NULL znaczy "nieustalona" i jest poprawnym wynikiem,
    # a nie brakiem danych do uzupelnienia (decyzja D5).
    data_zakonczenia_planowana: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_zakonczenia_faktyczna: Mapped[date | None] = mapped_column(Date, nullable=True)

    okres_wypowiedzenia_miesiace: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[StatusOkresuNajmu] = mapped_column(
        slownik(StatusOkresuNajmu),
        nullable=False,
        server_default=StatusOkresuNajmu.PRZYGOTOWANIE.value,
    )

    # Regula R2. Wskaznik wprowadza sie raz w roku, efekt jest na wszystkich umowach.
    waloryzacja_podlega: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    waloryzacja_miesiac: Mapped[int | None] = mapped_column(Integer, nullable=True)
    waloryzacja_rodzaj_wskaznika: Mapped[RodzajWskaznika | None] = mapped_column(
        slownik(RodzajWskaznika), nullable=True
    )
    waloryzacja_stala_stawka: Mapped[TypStawkiVat | None] = mapped_column(nullable=True)
    waloryzacja_pierwsza_data: Mapped[date | None] = mapped_column(Date, nullable=True)

    uwagi: Mapped[str | None] = mapped_column(Text, nullable=True)

    lokal: Mapped["Lokal"] = relationship(back_populates="okresy_najmu")
    najemca: Mapped["Najemca"] = relationship(back_populates="okresy_najmu")
    dokumenty: Mapped[list["Dokument"]] = relationship(back_populates="okres_najmu")
    parametry: Mapped[list["ParametrWartosc"]] = relationship(
        back_populates="okres_najmu", cascade="all, delete-orphan"
    )
    skladniki_oplat: Mapped[list["SkladnikOplaty"]] = relationship(back_populates="okres_najmu")
    zabezpieczenia: Mapped[list["Zabezpieczenie"]] = relationship(back_populates="okres_najmu")

    __table_args__ = (
        CheckConstraint(
            "waloryzacja_miesiac IS NULL OR waloryzacja_miesiac BETWEEN 1 AND 12",
            name="ck_okres_najmu_miesiac_waloryzacji",
        ),
        CheckConstraint(
            "okres_zawarcia_miesiace IS NULL OR okres_zawarcia_miesiace > 0",
            name="ck_okres_najmu_dodatni_okres",
        ),
        # Dashboard: "pokaz umowy konczace sie w Q2 2027" (koncepcja, sekcja 1.1).
        Index("ix_okres_najmu_koniec", "data_zakonczenia_planowana", "status"),
        Index("ix_okres_najmu_lokal_status", "lokal_id", "status"),
        Index("ix_okres_najmu_najemca", "najemca_id"),
        # Widok "kto podlega waloryzacji w tym miesiacu" (regula R2).
        Index(
            "ix_okres_najmu_waloryzacja",
            "waloryzacja_miesiac",
            postgresql_where=text("waloryzacja_podlega AND usunieto_dnia IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<OkresNajmu lokal={self.lokal_id} najemca={self.najemca_id} {self.status}>"


class SkladnikOplaty(Baza, ZnacznikiCzasu, MiekkieUsuwanie, Wersjonowanie):
    """Czynsz, eksploatacja, media, parking. Kazdy z wlasnym dniem platnosci.

    Uwaga na brak kolumny z kwota. Decyzja D2 mowi wprost, ze kwot nie trzymamy
    w tabeli umowy, tylko w parametr_wartosc, bo aneks ma dokladac nowa wersje
    wartosci, a nie nadpisywac stara. Ta tabela definiuje wiec CO jest platne
    i KIEDY, a ILE mowi parametr wskazany przez klucz_parametru.
    """

    __tablename__ = "skladnik_oplaty"

    id: Mapped[KluczGlowny]
    okres_najmu_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("okres_najmu.id", ondelete="CASCADE"), nullable=False
    )
    nazwa: Mapped[str] = mapped_column(String(120), nullable=False)

    #: Klucz w parametr_wartosc, pod ktorym leza kwoty tego skladnika w czasie.
    klucz_parametru: Mapped[str] = mapped_column(String(80), nullable=False)

    #: Gdy kwoty nie da sie podac wprost, np. "wg zuzycia licznikowego".
    sposob_wyliczenia: Mapped[str | None] = mapped_column(Text, nullable=True)

    dzien_platnosci_miesiaca: Mapped[int | None] = mapped_column(Integer, nullable=True)
    okres_rozliczeniowy: Mapped[OkresRozliczeniowy] = mapped_column(
        slownik(OkresRozliczeniowy),
        nullable=False,
        server_default=OkresRozliczeniowy.MIESIECZNY.value,
    )
    czy_waloryzowany: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    uwagi: Mapped[str | None] = mapped_column(Text, nullable=True)

    okres_najmu: Mapped[OkresNajmu] = relationship(back_populates="skladniki_oplat")

    __table_args__ = (
        CheckConstraint(
            "dzien_platnosci_miesiaca IS NULL OR dzien_platnosci_miesiaca BETWEEN 1 AND 31",
            name="ck_skladnik_dzien_platnosci",
        ),
        Index(
            "uq_skladnik_klucz_w_okresie",
            "okres_najmu_id",
            "klucz_parametru",
            unique=True,
            postgresql_where=text("usunieto_dnia IS NULL"),
        ),
        # Widok "kto placi do 28-go" bez czytania umow (regula R3).
        Index("ix_skladnik_dzien_platnosci", "dzien_platnosci_miesiaca"),
    )

    def __repr__(self) -> str:
        return f"<SkladnikOplaty {self.nazwa!r}>"


class Zabezpieczenie(Baza, ZnacznikiCzasu, MiekkieUsuwanie, Wersjonowanie):
    """Kaucja, weksel, gwarancja bankowa, polisa. Reguly R4, R5, R6.

    Wartosc wymagana jest tu kolumna, a nie parametrem wersjonowanym, bo bywa
    wielkoscia pochodna ("czterokrotnosc czynszu"), przeliczana po kazdej
    waloryzacji. Slad zmian zostaje w log_audytu.
    """

    __tablename__ = "zabezpieczenie"

    id: Mapped[KluczGlowny]
    okres_najmu_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("okres_najmu.id", ondelete="CASCADE"), nullable=False
    )
    rodzaj: Mapped[RodzajZabezpieczenia] = mapped_column(
        slownik(RodzajZabezpieczenia), nullable=False
    )
    status: Mapped[StatusZabezpieczenia] = mapped_column(
        slownik(StatusZabezpieczenia),
        nullable=False,
        server_default=StatusZabezpieczenia.WYMAGANE.value,
    )

    wymagana_wartosc: Mapped[TypKwoty | None] = mapped_column(nullable=True)
    wymagana_waluta: Mapped[TypWaluty | None] = mapped_column(nullable=True)
    wymagana_rodzaj_kwoty: Mapped[RodzajKwoty | None] = mapped_column(
        slownik(RodzajKwoty), nullable=True
    )
    wymagana_stawka_vat: Mapped[TypStawkiVat | None] = mapped_column(nullable=True)

    #: Np. "czterokrotnosc czynszu podstawowego". Zrodlo przeliczen z reguly R5.
    sposob_wyliczenia: Mapped[str | None] = mapped_column(Text, nullable=True)

    data_wymagalnosci: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_dostarczenia: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Polisa wygasa co rok, wiec pilnujemy jej cyklicznie, a nie raz (regula R6).
    data_waznosci: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_zwrotu: Mapped[date | None] = mapped_column(Date, nullable=True)

    miejsce_przechowywania: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dokument_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("dokument.id", ondelete="SET NULL"), nullable=True
    )
    uwagi: Mapped[str | None] = mapped_column(Text, nullable=True)

    okres_najmu: Mapped[OkresNajmu] = relationship(back_populates="zabezpieczenia")

    __table_args__ = (
        # Kwoty netto bez stawki VAT nie da sie zbrutowac, wiec taki wiersz
        # bylby kwota nieokreslona. Plan budowy, sekcja 1.1 punkt A.
        CheckConstraint(
            "wymagana_wartosc IS NULL "
            "OR wymagana_rodzaj_kwoty <> 'netto' "
            "OR wymagana_stawka_vat IS NOT NULL",
            name="ck_zabezpieczenie_netto_ma_vat",
        ),
        CheckConstraint(
            "wymagana_wartosc IS NULL OR (wymagana_waluta IS NOT NULL "
            "AND wymagana_rodzaj_kwoty IS NOT NULL)",
            name="ck_zabezpieczenie_kwota_pelna",
        ),
        Index("ix_zabezpieczenie_okres_rodzaj", "okres_najmu_id", "rodzaj"),
        # "Ktore polisy wygasaja w ciagu 30 dni" (regula R6).
        Index(
            "ix_zabezpieczenie_waznosc",
            "data_waznosci",
            postgresql_where=text("usunieto_dnia IS NULL"),
        ),
        Index(
            "ix_zabezpieczenie_wymagalnosc",
            "data_wymagalnosci",
            postgresql_where=text("usunieto_dnia IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Zabezpieczenie {self.rodzaj} {self.status}>"


class ObowiazekPrzegladu(Baza, ZnacznikiCzasu, MiekkieUsuwanie, Wersjonowanie):
    """Regula R7. Element jest osobnym wierszem, a nie polem tekstowym.

    Dopiero wtedy da sie zrobic widok "wszystkie gasnice do przegladu
    w tym kwartale", a specyfikacja wprost wymaga wyodrebnienia elementow.
    """

    __tablename__ = "obowiazek_przegladu"

    id: Mapped[KluczGlowny]
    lokal_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("lokal.id", ondelete="RESTRICT"), nullable=False
    )
    #: NULL, gdy obowiazek jest przypisany do lokalu niezaleznie od najemcy.
    okres_najmu_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("okres_najmu.id", ondelete="SET NULL"), nullable=True
    )

    element: Mapped[str] = mapped_column(String(120), nullable=False)
    kto_obciazany: Mapped[KtoObciazany] = mapped_column(slownik(KtoObciazany), nullable=False)
    czestotliwosc_miesiace: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ostatni_przeglad_data: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Wyliczana z reguly R7. NULL znaczy "nie da sie ustalic", nie "brak".
    nastepny_przeglad_data: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[StatusPrzegladu] = mapped_column(
        slownik(StatusPrzegladu), nullable=False, server_default=StatusPrzegladu.NIEUSTALONY.value
    )
    protokol_dokument_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("dokument.id", ondelete="SET NULL"), nullable=True
    )
    uwagi: Mapped[str | None] = mapped_column(Text, nullable=True)

    lokal: Mapped["Lokal"] = relationship(back_populates="obowiazki_przegladu")

    __table_args__ = (
        CheckConstraint(
            "czestotliwosc_miesiace IS NULL OR czestotliwosc_miesiace > 0",
            name="ck_przeglad_dodatnia_czestotliwosc",
        ),
        # "Wszystkie przeglady w budynku 18A w tym kwartale" - zleca sie je hurtowo.
        Index(
            "ix_przeglad_nastepny_termin",
            "nastepny_przeglad_data",
            postgresql_where=text("usunieto_dnia IS NULL"),
        ),
        Index("ix_przeglad_lokal_element", "lokal_id", "element"),
    )

    def __repr__(self) -> str:
        return f"<ObowiazekPrzegladu {self.element!r} lokal={self.lokal_id}>"
