"""M33: semiconductor equipment (formulas.md 47). `equipment_record` holds every equipment
record (ASML's queue of orders, deliveries, each generation's capacity a year from 2026, tools
in stock, the lithography programme's stages, own tool lines and fabs' tools), one row each:
`kind` names the collection and `data` the record's fields (data-dictionary.md). Existing saves
have none: the next month rebuilds rivals' order book and their recent deliveries from
equipment.yaml (tst.sim.equipment.phase.catch_up).

Revision ID: 0055_m33
Revises: 0054_m30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0055_m33"
down_revision: str | None = "0054_m30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "equipment_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 55")


def downgrade() -> None:
    op.drop_table("equipment_record")
    op.execute("UPDATE save_meta SET schema_version = 54")
