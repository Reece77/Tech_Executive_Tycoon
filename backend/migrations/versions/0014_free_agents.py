"""M6 sub-task 0: a pool of free agents (`free_agent`): a failed rival's people who join the
player's later searches for their role for `rivals.free_agent_months`. Existing saves start
with an empty pool.

Revision ID: 0014_free_agents
Revises: 0013_rivals
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_free_agents"
down_revision: str | None = "0013_rivals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "free_agent",
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id"), primary_key=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("released_turn", sa.Integer(), nullable=False),
        sa.Column("until_turn", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 14")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 13")
    op.drop_table("free_agent")
