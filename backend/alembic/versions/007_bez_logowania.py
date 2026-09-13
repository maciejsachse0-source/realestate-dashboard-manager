"""Usuniecie logowania, rol i sladu autorstwa

Revision ID: 007_bez_logowania
Revises: 006_ustawienia
Create Date: 2026-08-28

Migracja jest NIEODWRACALNA w sensie danych. `downgrade` odtwarza sam schemat,
bo kto ktorej zmiany dokonal, nie da sie odzyskac po skasowaniu kolumn.
Powod i odrzucone warianty: docs/decyzje/009-usuniecie-logowania.md
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007_bez_logowania"
down_revision: str | None = "006_ustawienia"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Tabele z miekkim usuwaniem. Kazda niosla `usunal_uzytkownik_id` z miksinu.
TABELE_MIEKKIEGO_USUWANIA: tuple[str, ...] = (
    "budynek",
    "dokument",
    "lokal",
    "najemca",
    "obowiazek_przegladu",
    "okres_najmu",
    "osoba_kontaktowa",
    "parametr_wartosc",
    "pominiety_plik",
    "powiazanie_folderu",
    "skladnik_oplaty",
    "ustawienie_systemu",
    "zabezpieczenie",
    "zdarzenie",
)

#: Pozostale kolumny wskazujace autora operacji: (tabela, kolumna).
KOLUMNY_AUTORA: tuple[tuple[str, str], ...] = (
    ("dokument", "wgral_uzytkownik_id"),
    ("log_audytu", "uzytkownik_id"),
    ("parametr_wartosc", "zatwierdzil_uzytkownik_id"),
    ("pominiety_plik", "pominal_uzytkownik_id"),
    ("powiazanie_folderu", "powiazal_uzytkownik_id"),
    ("ustawienie_systemu", "zmienil_uzytkownik_id"),
    ("wskaznik_waloryzacji", "wprowadzil_uzytkownik_id"),
    ("zdarzenie", "obsluzyl_uzytkownik_id"),
    ("zdarzenie", "przypisany_uzytkownik_id"),
)


def upgrade() -> None:
    """Program przestaje miec pojecie uzytkownika.

    Kolejnosc ma znaczenie: najpierw indeksy i ograniczenia, ktore odwoluja sie
    do kolumn, potem kolumny, na koncu tabele, na ktore wskazywaly klucze obce.
    """
    op.drop_index("ix_zdarzenie_przypisany", table_name="zdarzenie")
    op.drop_index("ix_audyt_uzytkownik", table_name="log_audytu")

    # Ograniczenie pilnowalo pary "kto i kiedy" przy zatwierdzaniu wartosci.
    # Bez polowy "kto" nie ma czego pilnowac.
    op.drop_constraint("ck_parametr_slad_zatwierdzenia", "parametr_wartosc", type_="check")

    for tabela in TABELE_MIEKKIEGO_USUWANIA:
        op.drop_column(tabela, "usunal_uzytkownik_id")

    for tabela, kolumna in KOLUMNY_AUTORA:
        op.drop_column(tabela, kolumna)

    op.drop_table("sesja_uzytkownika")
    op.drop_table("uzytkownik")


def downgrade() -> None:
    """Odtwarza schemat, nie dane.

    Wszystkie kolumny wracaja jako NULL-owalne i puste. Historia autorstwa
    przepadla przy `upgrade` i zadna migracja jej nie przywroci.
    """
    # Slowniki sa VARCHAR-em z ograniczeniem CHECK, nie typem natywnym bazy
    # (modele/wspolne.slownik). Odtwarzamy je tak samo.
    rola = sa.Enum(
        "podglad",
        "operator",
        "zarzadca",
        "administrator",
        name="rola_uzytkownika",
        native_enum=False,
        length=48,
    )

    op.create_table(
        "uzytkownik",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("login", sa.String(length=64), nullable=False),
        sa.Column("imie_nazwisko", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("hash_hasla", sa.String(length=255), nullable=True),
        sa.Column("rola", rola, nullable=False),
        sa.Column("aktywny", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "wymaga_zmiany_hasla", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("nieudane_logowania", sa.Integer(), server_default="0", nullable=False),
        sa.Column("zablokowany_do", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ostatnie_logowanie", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wersja", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column(
            "utworzono", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "zmodyfikowano",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("login"),
    )

    op.create_table(
        "sesja_uzytkownika",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("uzytkownik_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("wygasa", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ostatnia_aktywnosc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uniewazniona_dnia", sa.DateTime(timezone=True), nullable=True),
        sa.Column("adres_ip", sa.String(length=45), nullable=True),
        sa.Column(
            "utworzono", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "zmodyfikowano",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["uzytkownik_id"], ["uzytkownik.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_sesja_uzytkownik", "sesja_uzytkownika", ["uzytkownik_id"])

    for tabela, kolumna in KOLUMNY_AUTORA:
        usuwanie = "SET NULL" if tabela == "zdarzenie" else "RESTRICT"
        op.add_column(tabela, sa.Column(kolumna, sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            f"fk_{tabela}_{kolumna}", tabela, "uzytkownik", [kolumna], ["id"], ondelete=usuwanie
        )

    for tabela in TABELE_MIEKKIEGO_USUWANIA:
        op.add_column(tabela, sa.Column("usunal_uzytkownik_id", sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            f"fk_{tabela}_usunal_uzytkownik_id",
            tabela,
            "uzytkownik",
            ["usunal_uzytkownik_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    # NOT VALID celowo. Wiersze zatwierdzone przed usunieciem logowania maja
    # `zatwierdzono_dnia` bez autora, wiec pary "kto i kiedy" nie da sie juz
    # domknac wstecz. Ograniczenie pilnuje wiec tylko nowych wierszy, a stare
    # zostaja takie, jakie sa. Zwykle ADD CONSTRAINT wywrocilby cofniecie.
    op.execute(
        "ALTER TABLE parametr_wartosc ADD CONSTRAINT ck_parametr_slad_zatwierdzenia "
        "CHECK ((zatwierdzil_uzytkownik_id IS NULL) = (zatwierdzono_dnia IS NULL)) NOT VALID"
    )
    op.create_index("ix_audyt_uzytkownik", "log_audytu", ["uzytkownik_id", "kiedy"])
    op.create_index("ix_zdarzenie_przypisany", "zdarzenie", ["przypisany_uzytkownik_id", "status"])
