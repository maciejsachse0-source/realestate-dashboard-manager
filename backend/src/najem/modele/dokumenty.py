"""Dokumenty i wersjonowane wartosci parametrow.

ParametrWartosc to mechanizm z decyzji D2 i najwazniejsza tabela w tym projekcie.
Aneks nie nadpisuje wartosci, tylko doklada nowa wersje z data obowiazywania.
Bez tego obsluga aneksow zawsze bedzie zlepkiem hackow.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from najem.baza import Baza
from najem.domena.slowniki import (
    RodzajKwoty,
    StatusPrzetworzenia,
    StatusWeryfikacji,
    TypDokumentu,
    TypWartosci,
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
    from najem.modele.najem import OkresNajmu


class Dokument(Baza, ZnacznikiCzasu, MiekkieUsuwanie, Wersjonowanie):
    """Dokument to zrodlo dowodu, nie zrodlo prawdy. Prawda jest w bazie
    i linkuje do fragmentu dokumentu (koncepcja, sekcja 1.2).

    Sam plik lezy poza katalogiem serwowanym przez serwer WWW, a w bazie
    jest tylko sciezka wzgledna i skrot SHA-256.
    """

    __tablename__ = "dokument"

    id: Mapped[KluczGlowny]
    #: NULL dopuszczalny, bo protokol przegladu bywa przypisany do lokalu,
    #: a nie do konkretnego okresu najmu.
    okres_najmu_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("okres_najmu.id", ondelete="RESTRICT"), nullable=True
    )
    typ: Mapped[TypDokumentu] = mapped_column(slownik(TypDokumentu), nullable=False)
    numer: Mapped[str | None] = mapped_column(String(80), nullable=True)

    data_dokumentu: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Od kiedy postanowienia dokumentu obowiazuja. Aneks potrafi dzialac wstecz.
    data_obowiazywania_od: Mapped[date | None] = mapped_column(Date, nullable=True)

    plik_sciezka: Mapped[str | None] = mapped_column(String(500), nullable=True)
    plik_nazwa_oryginalna: Mapped[str | None] = mapped_column(String(300), nullable=True)
    #: Skrot pliku. Sluzy deduplikacji przy wgrywaniu i dowodowi, ze dokument
    #: sie nie zmienil (plan budowy, sekcja 1.3).
    hash_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rozmiar_bajty: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    typ_mime: Mapped[str | None] = mapped_column(String(120), nullable=True)
    liczba_stron: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Hierarchia dokumentow: aneks nr 2 wskazuje na umowe (koncepcja, sekcja 3.2).
    dokument_nadrzedny_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("dokument.id", ondelete="RESTRICT"), nullable=True
    )

    status_przetworzenia: Mapped[StatusPrzetworzenia] = mapped_column(
        slownik(StatusPrzetworzenia),
        nullable=False,
        server_default=StatusPrzetworzenia.WGRANY.value,
    )
    blad_przetwarzania: Mapped[str | None] = mapped_column(Text, nullable=True)
    wgral_uzytkownik_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("uzytkownik.id", ondelete="RESTRICT"), nullable=True
    )
    uwagi: Mapped[str | None] = mapped_column(Text, nullable=True)

    okres_najmu: Mapped["OkresNajmu | None"] = relationship(back_populates="dokumenty")
    aneksy: Mapped[list["Dokument"]] = relationship(back_populates="dokument_nadrzedny")
    dokument_nadrzedny: Mapped["Dokument | None"] = relationship(
        back_populates="aneksy", remote_side="Dokument.id"
    )
    parametry: Mapped[list["ParametrWartosc"]] = relationship(back_populates="dokument_zrodlowy")

    __table_args__ = (
        CheckConstraint(
            "dokument_nadrzedny_id IS NULL OR dokument_nadrzedny_id <> id",
            name="ck_dokument_nie_jest_wlasnym_rodzicem",
        ),
        CheckConstraint(
            "hash_sha256 IS NULL OR char_length(hash_sha256) = 64",
            name="ck_dokument_dlugosc_hasha",
        ),
        # Ten sam plik wgrany drugi raz ma zostac rozpoznany, a nie zdublowany.
        Index(
            "uq_dokument_hash",
            "hash_sha256",
            unique=True,
            postgresql_where=text("hash_sha256 IS NOT NULL AND usunieto_dnia IS NULL"),
        ),
        Index("ix_dokument_okres_typ", "okres_najmu_id", "typ"),
        Index("ix_dokument_nadrzedny", "dokument_nadrzedny_id"),
        Index(
            "ix_dokument_do_weryfikacji",
            "status_przetworzenia",
            postgresql_where=text("usunieto_dnia IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Dokument {self.typ} {self.numer!r}>"


class ParametrWartosc(Baza, ZnacznikiCzasu, MiekkieUsuwanie, Wersjonowanie):
    """Wartosc parametru umowy obowiazujaca w okreslonym czasie (decyzja D2).

    Zapytanie o stan na dany dzien to zawsze: wez dla kazdego klucza wiersz,
    gdzie obowiazuje_od <= dzien i (obowiazuje_do IS NULL lub >= dzien),
    o najpozniejszym obowiazuje_od, i tylko o statusie obowiazujacym (decyzja D4).

    Wartosc trzymamy w kolumnach typowanych, a nie w jednym polu tekstowym.
    Kwota w kolumnie tekstowej to zaproszenie do bledu groszowego, a data
    w tekscie uniemozliwia sortowanie i porownania w SQL.
    """

    __tablename__ = "parametr_wartosc"

    id: Mapped[KluczGlowny]
    okres_najmu_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("okres_najmu.id", ondelete="CASCADE"), nullable=False
    )
    #: Np. czynsz_podstawowy, stawka_m2, powierzchnia, data_zakonczenia.
    klucz: Mapped[str] = mapped_column(String(80), nullable=False)
    typ_wartosci: Mapped[TypWartosci] = mapped_column(slownik(TypWartosci), nullable=False)

    # --- wartosc: dokladnie jedna z ponizszych kolumn jest wypelniona ---
    wartosc_kwota: Mapped[TypKwoty | None] = mapped_column(nullable=True)
    wartosc_waluta: Mapped[TypWaluty | None] = mapped_column(nullable=True)
    wartosc_rodzaj_kwoty: Mapped[RodzajKwoty | None] = mapped_column(
        slownik(RodzajKwoty), nullable=True
    )
    wartosc_stawka_vat: Mapped[TypStawkiVat | None] = mapped_column(nullable=True)
    wartosc_liczba: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    wartosc_data: Mapped[date | None] = mapped_column(Date, nullable=True)
    wartosc_flaga: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    wartosc_tekst: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- okres obowiazywania ---
    obowiazuje_od: Mapped[date] = mapped_column(Date, nullable=False)
    #: NULL znaczy "do odwolania".
    obowiazuje_do: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- skad ta liczba ---
    dokument_zrodlowy_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("dokument.id", ondelete="RESTRICT"), nullable=True
    )
    zrodlo_strona: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zrodlo_paragraf: Mapped[str | None] = mapped_column(String(80), nullable=True)
    zrodlo_offset_od: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zrodlo_offset_do: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Pewnosc ekstrakcji, 0 do 1. NULL dla wartosci wprowadzonych recznie.
    pewnosc: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    # --- slad decyzji czlowieka (decyzja D4) ---
    status_weryfikacji: Mapped[StatusWeryfikacji] = mapped_column(
        slownik(StatusWeryfikacji),
        nullable=False,
        server_default=StatusWeryfikacji.ZAPROPONOWANA.value,
    )
    zatwierdzil_uzytkownik_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("uzytkownik.id", ondelete="RESTRICT"), nullable=True
    )
    zatwierdzono_dnia: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uwagi: Mapped[str | None] = mapped_column(Text, nullable=True)

    okres_najmu: Mapped["OkresNajmu"] = relationship(back_populates="parametry")
    dokument_zrodlowy: Mapped[Dokument | None] = relationship(back_populates="parametry")

    __table_args__ = (
        # Dokladnie jedna kolumna wartosci wypelniona i zgodna z typ_wartosci.
        # Bez tego ograniczenia da sie zapisac parametr, ktory jest jednoczesnie
        # kwota i data, a odczyt zwroci co innego niz zapis.
        CheckConstraint(
            """
            (typ_wartosci = 'kwota'  AND wartosc_kwota  IS NOT NULL
                AND wartosc_liczba IS NULL AND wartosc_data IS NULL
                AND wartosc_flaga IS NULL AND wartosc_tekst IS NULL)
         OR (typ_wartosci = 'liczba' AND wartosc_liczba IS NOT NULL
                AND wartosc_kwota IS NULL AND wartosc_data IS NULL
                AND wartosc_flaga IS NULL AND wartosc_tekst IS NULL)
         OR (typ_wartosci = 'data'   AND wartosc_data   IS NOT NULL
                AND wartosc_kwota IS NULL AND wartosc_liczba IS NULL
                AND wartosc_flaga IS NULL AND wartosc_tekst IS NULL)
         OR (typ_wartosci = 'flaga'  AND wartosc_flaga  IS NOT NULL
                AND wartosc_kwota IS NULL AND wartosc_liczba IS NULL
                AND wartosc_data IS NULL AND wartosc_tekst IS NULL)
         OR (typ_wartosci = 'tekst'  AND wartosc_tekst  IS NOT NULL
                AND wartosc_kwota IS NULL AND wartosc_liczba IS NULL
                AND wartosc_data IS NULL AND wartosc_flaga IS NULL)
            """,
            name="ck_parametr_jedna_wartosc",
        ),
        # Kwota bez waluty i bez informacji netto/brutto jest kwota nieokreslona.
        CheckConstraint(
            "typ_wartosci <> 'kwota' "
            "OR (wartosc_waluta IS NOT NULL AND wartosc_rodzaj_kwoty IS NOT NULL)",
            name="ck_parametr_kwota_pelna",
        ),
        # Kwoty netto nie da sie zbrutowac bez stawki VAT (plan, punkt A).
        CheckConstraint(
            "wartosc_rodzaj_kwoty <> 'netto' OR wartosc_stawka_vat IS NOT NULL",
            name="ck_parametr_netto_ma_vat",
        ),
        CheckConstraint(
            "obowiazuje_do IS NULL OR obowiazuje_do >= obowiazuje_od",
            name="ck_parametr_okres_niepusty",
        ),
        CheckConstraint(
            "pewnosc IS NULL OR (pewnosc >= 0 AND pewnosc <= 1)",
            name="ck_parametr_pewnosc_zakres",
        ),
        # Zatwierdzenie to para: kto i kiedy. Jedno bez drugiego to slad polowiczny.
        CheckConstraint(
            "(zatwierdzil_uzytkownik_id IS NULL) = (zatwierdzono_dnia IS NULL)",
            name="ck_parametr_slad_zatwierdzenia",
        ),
        # Najwazniejszy indeks w systemie: stan efektywny na dzien.
        # Czesciowy, bo do stanu wchodza wylacznie wartosci obowiazujace (D4).
        Index(
            "ix_parametr_stan_efektywny",
            "okres_najmu_id",
            "klucz",
            text("obowiazuje_od DESC"),
            postgresql_where=text(
                "usunieto_dnia IS NULL AND status_weryfikacji IN ('zatwierdzona', 'poprawiona')"
            ),
        ),
        # Ekran weryfikacji: "co czeka na czlowieka w tym dokumencie".
        Index(
            "ix_parametr_do_weryfikacji",
            "dokument_zrodlowy_id",
            "status_weryfikacji",
            postgresql_where=text("usunieto_dnia IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<ParametrWartosc {self.klucz!r} od {self.obowiazuje_od}>"
