"""M50: the 2008 start (ADR-0024, formulas.md 60). `save_meta.start_turn` records the month the
save's game began: 0 for a game begun in January 2010 (every existing save), -24 for one begun
in January 2008, the start month for a Sandbox or scenario. Turn columns already accept
negative turns (SQLite integers, no checks), so nothing else widens.

Revision ID: 0066_m50
Revises: 0065_m47
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0066_m50"
down_revision: str | None = "0065_m47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("save_meta") as batch:
        batch.add_column(sa.Column("start_turn", sa.Integer(), nullable=False, server_default="0"))
    op.execute("UPDATE save_meta SET schema_version = 66")


def downgrade() -> None:
    with op.batch_alter_table("save_meta") as batch:
        batch.drop_column("start_turn")
