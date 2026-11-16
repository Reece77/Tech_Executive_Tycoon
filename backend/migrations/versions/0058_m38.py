"""M38: electric vehicles (formulas.md 49). `vehicle_record` holds every vehicle record (cars'
designs, cell plants, charging networks, the month's own-cell lots, product months, incidents and
the game-wide `vehicle_world`), one row each: `kind` names the collection and `data` the record's
fields (data-dictionary.md). Existing saves have none, and no vehicles market: like M12a's and
M12b's markets, cars come only with a new game.

Revision ID: 0058_m38
Revises: 0057_m32
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0058_m38"
down_revision: str | None = "0057_m32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicle_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 58")


def downgrade() -> None:
    op.drop_table("vehicle_record")
    op.execute("UPDATE save_meta SET schema_version = 57")
