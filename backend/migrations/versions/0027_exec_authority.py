"""M10c: executives with authority (formulas.md 24): each seat's authority and guardrails
(`exec_authority`), what executives did (`exec_decision`) and their proposals waiting for the
player (`exec_proposal`). Existing saves start with none.

Revision ID: 0027_exec_authority
Revises: 0026_marketing_split
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_exec_authority"
down_revision: str | None = "0026_marketing_split"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exec_authority",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("seat", sa.String(8), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("guardrails", sa.JSON(), nullable=False),
        sa.Column("since_turn", sa.Integer(), nullable=False),
        sa.Column("price_anchors", sa.JSON(), nullable=False),
    )
    op.create_table(
        "exec_decision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("seat", sa.String(8), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("mistake", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_exec_decision_turn", "exec_decision", ["turn"])
    op.create_table(
        "exec_proposal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("seat", sa.String(8), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("resolved_turn", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE save_meta SET schema_version = 27")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 26")
    op.drop_table("exec_proposal")
    op.drop_index("ix_exec_decision_turn", table_name="exec_decision")
    op.drop_table("exec_decision")
    op.drop_table("exec_authority")
