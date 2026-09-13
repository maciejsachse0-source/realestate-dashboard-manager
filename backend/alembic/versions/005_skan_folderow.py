"""Skan folderow z dokumentami na dysku uzytkownika

Revision ID: 005_skan_folderow
Revises: 004_slad_waloryzacji
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_skan_folderow"
down_revision: str | None = "004_slad_waloryzacji"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Dokumenty wczytywane z folderow na dysku, bez kopiowania plikow.

    Cztery zmiany, kazda z jednego powodu:

    * `budynek.nazwa_folderu` -- katalog budynku na dysku bywa nazwany inaczej
      niz budynek w programie, a jego przemianowanie nie moze zrywac powiazan;
    * `dokument.przechowywanie` -- dotad kazdy plik lezal w przechowalni
      systemu. Teraz dokument moze byc odnosnikiem do pliku uzytkownika,
      ktory zostaje tam, gdzie lezy. Wszystkie dotychczasowe wiersze sa
      kopiami, stad wartosc domyslna;
    * `powiazanie_folderu` -- czlowiek raz wskazuje, ktora umowa kryje sie
      za ktorym folderem. Oznaczen lokali z nazw folderow nie parsujemy;
    * `pominiety_plik` -- swiadomie odrzucony plik ma sie nie pokazywac przy
      kazdym kolejnym skanie.
    """
    op.add_column("budynek", sa.Column("nazwa_folderu", sa.String(length=200), nullable=True))
    op.create_index(
        "uq_budynek_folder",
        "budynek",
        ["nazwa_folderu"],
        unique=True,
        postgresql_where=sa.text("nazwa_folderu IS NOT NULL AND usunieto_dnia IS NULL"),
    )

    op.add_column(
        "dokument",
        sa.Column(
            "przechowywanie",
            sa.Enum("kopia", "link", name="trybprzechowywania", native_enum=False, length=48),
            server_default="kopia",
            nullable=False,
        ),
    )
    # Skan pyta o kazdy znaleziony plik, czy juz jest w systemie. Indeks
    # czesciowy, bo odnosniki beda ulamkiem tabeli dokumentow.
    op.create_index(
        "ix_dokument_sciezka_linku",
        "dokument",
        ["plik_sciezka"],
        unique=False,
        postgresql_where=sa.text("przechowywanie = 'link' AND usunieto_dnia IS NULL"),
    )

    op.create_table(
        "powiazanie_folderu",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sciezka_wzgledna", sa.String(length=500), nullable=False),
        sa.Column("okres_najmu_id", sa.BigInteger(), nullable=False),
        sa.Column("powiazal_uzytkownik_id", sa.BigInteger(), nullable=True),
        sa.Column("uwagi", sa.Text(), nullable=True),
        sa.Column(
            "utworzono",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "zmodyfikowano",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("usunieto_dnia", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usunal_uzytkownik_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["okres_najmu_id"], ["okres_najmu.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["powiazal_uzytkownik_id"], ["uzytkownik.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["usunal_uzytkownik_id"], ["uzytkownik.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_powiazanie_folderu_okres", "powiazanie_folderu", ["okres_najmu_id"], unique=False
    )
    op.create_index(
        op.f("ix_powiazanie_folderu_usunieto_dnia"),
        "powiazanie_folderu",
        ["usunieto_dnia"],
        unique=False,
    )
    op.create_index(
        "uq_powiazanie_folderu_sciezka",
        "powiazanie_folderu",
        ["sciezka_wzgledna"],
        unique=True,
        postgresql_where=sa.text("usunieto_dnia IS NULL"),
    )

    op.create_table(
        "pominiety_plik",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("nazwa_pliku", sa.String(length=300), nullable=True),
        sa.Column("sciezka_wzgledna", sa.String(length=500), nullable=True),
        sa.Column("powod", sa.Text(), nullable=True),
        sa.Column("pominal_uzytkownik_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "utworzono",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "zmodyfikowano",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("usunieto_dnia", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usunal_uzytkownik_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("char_length(hash_sha256) = 64", name="ck_pominiety_dlugosc_hasha"),
        sa.ForeignKeyConstraint(["pominal_uzytkownik_id"], ["uzytkownik.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["usunal_uzytkownik_id"], ["uzytkownik.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pominiety_plik_usunieto_dnia"), "pominiety_plik", ["usunieto_dnia"], unique=False
    )
    op.create_index(
        "uq_pominiety_plik_hash",
        "pominiety_plik",
        ["hash_sha256"],
        unique=True,
        postgresql_where=sa.text("usunieto_dnia IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_pominiety_plik_hash", table_name="pominiety_plik")
    op.drop_index(op.f("ix_pominiety_plik_usunieto_dnia"), table_name="pominiety_plik")
    op.drop_table("pominiety_plik")
    op.drop_index("uq_powiazanie_folderu_sciezka", table_name="powiazanie_folderu")
    op.drop_index(op.f("ix_powiazanie_folderu_usunieto_dnia"), table_name="powiazanie_folderu")
    op.drop_index("ix_powiazanie_folderu_okres", table_name="powiazanie_folderu")
    op.drop_table("powiazanie_folderu")
    op.drop_index("ix_dokument_sciezka_linku", table_name="dokument")
    op.drop_column("dokument", "przechowywanie")
    op.drop_index("uq_budynek_folder", table_name="budynek")
    op.drop_column("budynek", "nazwa_folderu")
