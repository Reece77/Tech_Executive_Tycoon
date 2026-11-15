"""M32: power and owned plants (formulas.md 46, ADR-0022). `power_record` holds every power
record (plants, PPAs, grid-queue entries, companies' monthly power books, grid outages, regions'
seeded paths and the game-wide draws), one row each: `kind` names the collection and `data` the
record's fields (data-dictionary.md). Existing saves have none: a company meters its energy from
the next month, and nothing else exists until it signs, builds or queues.

Revision ID: 0057_m32
Revises: 0056_m33
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0057_m32"
down_revision: str | None = "0056_m33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "power_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 57")


def downgrade() -> None:
    op.drop_table("power_record")
    op.execute("UPDATE save_meta SET schema_version = 56")
