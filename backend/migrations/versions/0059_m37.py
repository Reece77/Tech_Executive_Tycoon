"""M37: dynasty mode (formulas.md 52). `dynasty_record` holds the game's dynasty-years records
(rival leaders' successions, deaths and relaunched brands) as one JSON row, written only from
January 2040; the campaign length is in `game_mode`'s JSON (`length`, default standard), so
existing saves need no change and are standard campaigns.

Revision ID: 0059_m37
Revises: 0058_m38
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0059_m37"
down_revision: str | None = "0058_m38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dynasty_record",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 59")


def downgrade() -> None:
    op.drop_table("dynasty_record")
    op.execute("UPDATE save_meta SET schema_version = 58")
