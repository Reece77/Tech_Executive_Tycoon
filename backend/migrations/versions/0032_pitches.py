"""M13b: executives' pitches (formulas.md 27.1): each pitch with its numbers, the founder's
answer and its follow-through (`exec_pitch`), and the player's Holiday spend limit and big-
pitch stop (`pitch_policy`); a player first mover's era window with its report baseline
(`era_window`, 27.3). Existing saves start with none (the default limit applies).

Revision ID: 0032_pitches
Revises: 0031_hardware
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_pitches"
down_revision: str | None = "0031_hardware"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exec_pitch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("seat", sa.String(8), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("why", sa.Text(), nullable=False),
        sa.Column("cost_cents", sa.BigInteger(), nullable=False),
        sa.Column("capex_cents", sa.BigInteger(), nullable=False),
        sa.Column("monthly_cents", sa.BigInteger(), nullable=False),
        sa.Column("hires", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("low", sa.BigInteger(), nullable=False),
        sa.Column("high", sa.BigInteger(), nullable=False),
        sa.Column("risk", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("resolved_turn", sa.Integer(), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("baseline", sa.BigInteger(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=True),
        sa.Column("outcome_turn", sa.Integer(), nullable=True),
        sa.Column("measured", sa.BigInteger(), nullable=True),
    )
    op.create_table(
        "pitch_policy",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("auto_approve_cents", sa.BigInteger(), nullable=True),
        sa.Column("stop_for_big", sa.Boolean(), nullable=False),
    )
    op.create_table(  # 27.3: a player first mover's window and its report's baseline
        "era_window",
        sa.Column("era_key", sa.String(32), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("start_turn", sa.Integer(), nullable=False),
        sa.Column("products", sa.JSON(), nullable=False),
        sa.Column("trend", sa.Float(), nullable=False),
        sa.Column("demand", sa.JSON(), nullable=False),
        sa.Column("reported", sa.Boolean(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 32")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 31")
    op.drop_table("era_window")
    op.drop_table("pitch_policy")
    op.drop_table("exec_pitch")
