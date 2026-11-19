"""M44: defence and government contracts (formulas.md 57). `government_record` holds every
government record (tenders, the player's bids, protests, contracts, staff and facility
clearances, controlled products, defence records and the game-wide `government_world`), one row
each: `kind` names the collection and `data` the record's fields (data-dictionary.md). Existing
saves have none; governments start tendering at their next month.

Revision ID: 0062_m44
Revises: 0061_m39
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062_m44"
down_revision: str | None = "0061_m39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "government_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 62")


def downgrade() -> None:
    op.drop_table("government_record")
    op.execute("UPDATE save_meta SET schema_version = 61")
