"""M40: space and satellites (formulas.md 56). `space_record` holds every space record (launch
vehicle designs, constellations with their cohorts, licences, launches flown, constellation months,
terminal prices, carrier partners and the game-wide `space_world`), one row each: `kind` names the
collection and `data` the record's fields (data-dictionary.md). Existing saves have none, and no
space markets: like M38's vehicles and M39's robots, space comes only with a new game.

Revision ID: 0063_m40
Revises: 0062_m42 (re-parented from 0061_m39 at the merge with M42)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0063_m40"
down_revision: str | None = "0062_m42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "space_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 63")


def downgrade() -> None:
    op.drop_table("space_record")
    op.execute("UPDATE save_meta SET schema_version = 62")
