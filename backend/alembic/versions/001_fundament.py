"""Fundament: rozszerzenia PostgreSQL potrzebne przez caly projekt.

Bez tabel domenowych. Te przychodza w etapie E1.
pg_trgm i unaccent obsluguja wyszukiwanie po polsku (plan, sekcja 1.2 punkt I).

Revision ID: 001_fundament
Revises:
Create Date: 2026-08-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "001_fundament"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    # Rozszerzen nie usuwamy: moga byc uzywane przez inne obiekty w bazie.
    pass
