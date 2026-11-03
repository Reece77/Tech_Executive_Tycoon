"""M13: going public and the Chair (formulas.md 25): each company's IPO chain (`listing`), its
life as a listed company (`public_company`), quarterly guidance (`guidance`), month-end share
prices (`share_month`), appointed CEOs (`ceo`) and their decisions (`ceo_decision`). Existing
saves start with none: every company is private and founder-led.

Revision ID: 0030_public_company
Revises: 0029_facilities
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_public_company"
down_revision: str | None = "0029_facilities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "listing",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("bank", sa.String(32), nullable=False),
        sa.Column("hired_turn", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("filed_late", sa.Boolean(), nullable=True),
        sa.Column("roadshow_turn", sa.Integer(), nullable=True),
        sa.Column("ambition", sa.String(8), nullable=True),
        sa.Column("share_choice", sa.String(8), nullable=True),
        sa.Column("dual_class", sa.Boolean(), nullable=True),
        sa.Column("demand", sa.Float(), nullable=True),
        sa.Column("price_choice", sa.String(8), nullable=True),
        sa.Column("shares_before", sa.BigInteger(), nullable=False),
        sa.Column("new_shares", sa.BigInteger(), nullable=False),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.Column("gross_cents", sa.BigInteger(), nullable=False),
        sa.Column("fee_cents", sa.BigInteger(), nullable=False),
        sa.Column("first_day_return", sa.Float(), nullable=True),
        sa.Column("close_cents", sa.BigInteger(), nullable=False),
        sa.Column("listed_turn", sa.Integer(), nullable=True),
        sa.Column("pulled_turn", sa.Integer(), nullable=True),
        sa.Column("ticker", sa.String(16), nullable=False),
    )
    op.create_table(
        "public_company",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("listed_turn", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("dual_class", sa.Boolean(), nullable=False),
        sa.Column("listing_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.Column("sentiment", sa.Float(), nullable=False),
        sa.Column("value_cents", sa.BigInteger(), nullable=False),
        sa.Column("analysts", sa.JSON(), nullable=False),
        sa.Column("below_value_months", sa.Integer(), nullable=False),
        sa.Column("below_takeover_months", sa.Integer(), nullable=False),
        sa.Column("last_activist_turn", sa.Integer(), nullable=True),
        sa.Column("last_takeover_turn", sa.Integer(), nullable=True),
        sa.Column("beat_streak", sa.Integer(), nullable=False),
        sa.Column("miss_streak", sa.Integer(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("quarter_revenue_cents", sa.BigInteger(), nullable=False),
        sa.Column("quarter_op_cents", sa.BigInteger(), nullable=False),
        sa.Column("dividend_cents", sa.BigInteger(), nullable=False),
        sa.Column("lapsed_seats", sa.Integer(), nullable=False),
        sa.Column("pending", sa.JSON(), nullable=False),
    )
    op.create_table(
        "guidance",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("quarter_turn", sa.Integer(), primary_key=True),
        sa.Column("revenue_cents", sa.BigInteger(), nullable=False),
        sa.Column("margin_bp", sa.Integer(), nullable=False),
        sa.Column("consensus_revenue_cents", sa.BigInteger(), nullable=False),
        sa.Column("consensus_margin_bp", sa.Integer(), nullable=False),
        sa.Column("by_player", sa.Boolean(), nullable=False),
        sa.Column("actual_revenue_cents", sa.BigInteger(), nullable=True),
        sa.Column("actual_margin_bp", sa.Integer(), nullable=True),
        sa.Column("result", sa.String(8), nullable=True),
        sa.Column("price_before_cents", sa.BigInteger(), nullable=True),
        sa.Column("price_after_cents", sa.BigInteger(), nullable=True),
    )
    op.create_table(
        "share_month",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("turn", sa.Integer(), primary_key=True),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.Column("shares", sa.BigInteger(), nullable=False),
        sa.Column("mark", sa.String(16), nullable=False),
    )
    op.create_table(
        "ceo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("since_turn", sa.Integer(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("ended_turn", sa.Integer(), nullable=True),
        sa.Column("end_reason", sa.String(16), nullable=True),
        sa.Column("low_months", sa.Integer(), nullable=False),
        sa.Column("price_anchors", sa.JSON(), nullable=False),
    )
    op.create_table(
        "ceo_decision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("mistake", sa.Boolean(), nullable=False),
        sa.Column("undo", sa.JSON(), nullable=False),
        sa.Column("overridden_turn", sa.Integer(), nullable=True),
    )
    op.create_index("ix_ceo_decision_turn", "ceo_decision", ["turn"])
    op.execute("UPDATE save_meta SET schema_version = 30")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 29")
    op.drop_index("ix_ceo_decision_turn", table_name="ceo_decision")
    op.drop_table("ceo_decision")
    op.drop_table("ceo")
    op.drop_table("share_month")
    op.drop_table("guidance")
    op.drop_table("public_company")
    op.drop_table("listing")
