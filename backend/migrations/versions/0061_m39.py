"""M39: robotics and robotaxis (formulas.md 53). `robotics_record` holds every robotics record
(plant automation, humanoid designs, robotaxi zones and depots, zone months, incidents and the
game-wide `robotics_world`), one row each: `kind` names the collection and `data` the record's
fields (data-dictionary.md). Existing saves have none, and no robotics markets: like M38's
vehicles, robots come only with a new game.

Revision ID: 0061_m39
Revises: 0060_m37
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0061_m39"
down_revision: str | None = "0060_m37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "robotics_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 61")


def downgrade() -> None:
    op.drop_table("robotics_record")
    op.execute("UPDATE save_meta SET schema_version = 60")
