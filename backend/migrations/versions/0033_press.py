"""M14b: the founder in public (formulas.md 29): press moments (`press_moment`), public promises
(`press_promise`), each company's credibility (`credibility`), the player's feuds with rival
CEOs (`feud`) and rival CEOs' statements (`rival_statement`), recent resignations and poaches (`departure`); and two side tables for the new
hiring fields (29.5): a search's interest filter (`search_interest`) and a plan's interest,
replaced leaver and level (`hiring_plan_detail`). Side tables, not new columns on `search` and
`hiring_plan`, because migration 0013 loads and writes those tables through the current models
(as `search_level` and `search_city` did). Existing saves start with none.

Revision ID: 0033_press
Revises: 0032_pitches
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_press"
down_revision: str | None = "0032_pitches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "press_moment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("trigger", sa.String(32), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("event_turn", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("rival_id", sa.Integer(), nullable=True),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("tone", sa.String(16), nullable=True),
        sa.Column("answered_turn", sa.Integer(), nullable=True),
        sa.Column("share_bp", sa.Integer(), nullable=True),
        sa.Column("backfired", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_press_moment_turn", "press_moment", ["turn"])
    op.create_table(
        "press_promise",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("made_turn", sa.Integer(), nullable=False),
        sa.Column("deadline_turn", sa.Integer(), nullable=False),
        sa.Column("moment_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("rival_product_id", sa.Integer(), nullable=True),
        sa.Column("domain", sa.String(32), nullable=True),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("baseline", sa.Integer(), nullable=False),
        sa.Column("prices", sa.JSON(), nullable=False),
        sa.Column("ambition", sa.Float(), nullable=False),
        sa.Column("audience", sa.Float(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("resolved_turn", sa.Integer(), nullable=True),
        sa.Column("reminder_turn", sa.Integer(), nullable=True),
    )
    op.create_table(
        "credibility",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.Column("fired_turn", sa.Integer(), nullable=True),
        sa.Column("fired", sa.Integer(), nullable=False),
        sa.Column("staff_start", sa.Integer(), nullable=False),
    )
    op.create_table(
        "feud",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("rival_id", sa.Integer(), primary_key=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("causes", sa.JSON(), nullable=False),
        sa.Column("rivalry_turn", sa.Integer(), nullable=True),
    )
    op.create_table(
        "rival_statement",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rival_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_rival_statement_turn", "rival_statement", ["turn"])
    op.create_table(
        "departure",
        sa.Column("person_id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
    )
    op.create_index("ix_departure_turn", "departure", ["turn"])
    op.create_table(
        "search_interest",
        sa.Column("search_id", sa.Integer(), sa.ForeignKey("search.id"), primary_key=True),
        sa.Column("interest", sa.String(32), nullable=False),
    )
    op.create_table(
        "hiring_plan_detail",
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("hiring_plan.id"), primary_key=True),
        sa.Column("interest", sa.String(32), nullable=True),
        sa.Column("replace_of", sa.Integer(), nullable=True),
        sa.Column("level", sa.String(16), nullable=True),
    )
    op.execute("UPDATE save_meta SET schema_version = 33")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 32")
    op.drop_table("hiring_plan_detail")
    op.drop_table("search_interest")
    op.drop_index("ix_departure_turn", table_name="departure")
    op.drop_table("departure")
    op.drop_index("ix_rival_statement_turn", table_name="rival_statement")
    op.drop_table("rival_statement")
    op.drop_table("feud")
    op.drop_table("credibility")
    op.drop_table("press_promise")
    op.drop_index("ix_press_moment_turn", table_name="press_moment")
    op.drop_table("press_moment")
