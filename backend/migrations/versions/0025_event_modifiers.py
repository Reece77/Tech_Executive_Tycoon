"""M10b: event modifiers (`event_modifier`, formulas.md 23.2): an event choice's lasting percent
change to one stat (brand target, quality cap, builder output, seller capacity, awareness,
churn, morale target or the founder's monthly energy) for a number of months. Existing saves
start with none.

Revision ID: 0025_event_modifiers
Revises: 0024_inbox_bookmark
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_event_modifiers"
down_revision: str | None = "0024_inbox_bookmark"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_modifier",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("event.id"), nullable=True),
        sa.Column("target", sa.String(32), nullable=False),
        sa.Column("stat", sa.String(32), nullable=False),
        sa.Column("value_pct", sa.Float(), nullable=False),
        sa.Column("start_turn", sa.Integer(), nullable=False),
        sa.Column("end_turn", sa.Integer(), nullable=False),
    )
    op.create_index("ix_event_modifier_end_turn", "event_modifier", ["end_turn"])
    op.execute("UPDATE save_meta SET schema_version = 25")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 24")
    op.drop_index("ix_event_modifier_end_turn", table_name="event_modifier")
    op.drop_table("event_modifier")
