"""M27b: automation for the chain (formulas.md 40.7). An area owner's yearly budget and its
guardrails (`area_owner.budget_cents`, `area_owner.guardrails`, a JSON object of key -> value;
existing rows: 0 and none), and per-unit headcount targets the Hiring owner fills
(`headcount_target`). Area owners of subsidiaries are rows of `area_owner` with the
subsidiary's company id (no schema change).

Revision ID: 0051_m27b
Revises: 0050_m28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0051_m27b"
down_revision: str | None = "0050_m28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("area_owner") as batch:
        batch.add_column(
            sa.Column("budget_cents", sa.BigInteger(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("guardrails", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table(
        "headcount_target",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("unit_id", sa.Integer(), primary_key=True),
        sa.Column("role", sa.String(32), primary_key=True),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("set_turn", sa.Integer(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 51")


def downgrade() -> None:
    op.drop_table("headcount_target")
    with op.batch_alter_table("area_owner") as batch:
        batch.drop_column("guardrails")
        batch.drop_column("budget_cents")
    op.execute("UPDATE save_meta SET schema_version = 50")
