"""M28: a living world (formulas.md 41). `world_record` holds every living-world record (chain
companies, their facilities, goods' world months, regional cycles, World news, rival-on-rival
deals and mandates, rivals' offtakes, bids for the player and Chinese foundries' lags), one row
each: `kind` names the collection and `data` the record's fields (data-dictionary.md). Chain
companies are rows of `company` with a `company_rival_key` of (7, position). Existing saves have
none: the world starts in January 2026 and a save past it starts its world at its next month.

Revision ID: 0049_m28
Revises: 0048_m23a
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049_m28"
down_revision: str | None = "0048_m23a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "world_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 49")


def downgrade() -> None:
    op.drop_table("world_record")
    op.execute("UPDATE save_meta SET schema_version = 48")
