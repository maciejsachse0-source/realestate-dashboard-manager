"""Ustawienia systemu zmieniane z interfejsu

Revision ID: 006_ustawienia
Revises: 005_skan_folderow
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_ustawienia"
down_revision: str | None = "005_skan_folderow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Katalog z dokumentami przestaje byc ustawieniem z pliku .env.

    Wymaganie edycji pliku tekstowego od osoby, ktora ma obslugiwac umowy,
    bylo przerzucaniem na nia pracy administratora. Wartosc z .env zostaje
    jako zapasowa: pusta tabela znaczy "bierz to, co w pliku".

    Tabela jest celowo prosta i nie jest poczatkiem "systemu konfiguracji".
    """
    op.create_table(
        "ustawienie_systemu",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("klucz", sa.String(length=80), nullable=False),
        sa.Column("wartosc", sa.Text(), nullable=True),
        sa.Column("zmienil_uzytkownik_id", sa.BigInteger(), nullable=True),
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
        sa.Column("wersja", sa.BigInteger(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["usunal_uzytkownik_id"], ["uzytkownik.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["zmienil_uzytkownik_id"], ["uzytkownik.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ustawienie_systemu_usunieto_dnia"),
        "ustawienie_systemu",
        ["usunieto_dnia"],
        unique=False,
    )
    op.create_index(
        "uq_ustawienie_klucz",
        "ustawienie_systemu",
        ["klucz"],
        unique=True,
        postgresql_where=sa.text("usunieto_dnia IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ustawienie_klucz", table_name="ustawienie_systemu")
    op.drop_index(op.f("ix_ustawienie_systemu_usunieto_dnia"), table_name="ustawienie_systemu")
    op.drop_table("ustawienie_systemu")
