"""Slad waloryzacji w parametr_wartosc

Revision ID: 4893c39505b0
Revises: 003_sesje
Create Date: 2026-08-25 19:47:14.921540
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "004_slad_waloryzacji"
down_revision: str | None = "003_sesje"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Slad po waloryzacji rocznej na wierszu parametru.

    Do tej pory waloryzacja rozpoznawala wlasny poprzedni przebieg po samej
    dacie wejscia. Aneks wchodzacy 1 stycznia byl wtedy nie do odroznienia
    od waloryzacji, a niezatwierdzona propozycja czynszu w tym dniu blokowala
    przebieg komunikatem, ze podwyzka juz byla.

    Wierszy sprzed tej migracji nie oznaczamy. Nie da sie z dolu ustalic,
    ktore powstaly z waloryzacji, a zgadywanie po dacie jest dokladnie tym
    bledem, ktory ta kolumna usuwa.
    """
    op.add_column("parametr_wartosc", sa.Column("waloryzacja_rok", sa.Integer(), nullable=True))
    op.add_column(
        "parametr_wartosc",
        sa.Column("waloryzacja_wskaznik_procent", sa.Numeric(precision=5, scale=2), nullable=True),
    )
    op.create_check_constraint(
        "ck_parametr_waloryzacja_komplet",
        "parametr_wartosc",
        "(waloryzacja_rok IS NULL) = (waloryzacja_wskaznik_procent IS NULL)",
    )
    # Eksport i wykrywanie powtorzonego przebiegu pytaja zawsze o konkretny rok.
    op.create_index(
        "ix_parametr_waloryzacja_rok",
        "parametr_wartosc",
        ["waloryzacja_rok"],
        postgresql_where=sa.text("waloryzacja_rok IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_parametr_waloryzacja_rok", table_name="parametr_wartosc")
    op.drop_constraint("ck_parametr_waloryzacja_komplet", "parametr_wartosc", type_="check")
    op.drop_column("parametr_wartosc", "waloryzacja_wskaznik_procent")
    op.drop_column("parametr_wartosc", "waloryzacja_rok")
