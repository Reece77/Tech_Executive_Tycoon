"""M12a: facilities, market goods and component contracts (formulas.md 22): data centres
(`facility`), each good's month (`supply_month`), contracts (`supply_contract`) and outages
(`facility_outage`). Existing saves start with none; their goods follow history.

Revision ID: 0028_facilities
Revises: 0027_exec_authority
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_facilities"
down_revision: str | None = "0027_exec_authority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "facility",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("region", sa.String(32), nullable=False),
        sa.Column("city", sa.String(32), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("on_time", sa.Integer(), nullable=False),
        sa.Column("ordered_turn", sa.Integer(), nullable=False),
        sa.Column("ready_turn", sa.Integer(), nullable=False),
        sa.Column("late_turn", sa.Integer(), nullable=False),
        sa.Column("capex_cents", sa.BigInteger(), nullable=False),
        sa.Column("input_index", sa.Float(), nullable=False),
        sa.Column("capex_paid_cents", sa.BigInteger(), nullable=False),
        sa.Column("depreciated_cents", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("contract_id", sa.Integer(), nullable=True),
        sa.Column("closed_turn", sa.Integer(), nullable=True),
    )
    op.create_table(
        "supply_month",
        sa.Column("good", sa.String(32), primary_key=True),
        sa.Column("turn", sa.Integer(), primary_key=True),
        sa.Column("price_index", sa.Float(), nullable=False),
        sa.Column("allocation", sa.Float(), nullable=False),
        sa.Column("base", sa.Float(), nullable=False),
        sa.Column("change", sa.Float(), nullable=False),
        sa.Column("shock_turn", sa.Integer(), nullable=True),
        sa.Column("shock_months", sa.Integer(), nullable=False),
        sa.Column("shock_rise", sa.Float(), nullable=False),
        sa.Column("shock_allocation", sa.Float(), nullable=False),
    )
    op.create_table(
        "supply_contract",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("good", sa.String(32), nullable=False),
        sa.Column("price_index", sa.Float(), nullable=False),
        sa.Column("signed_turn", sa.Integer(), nullable=False),
        sa.Column("end_turn", sa.Integer(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("unit_value_cents", sa.BigInteger(), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("settled_cents", sa.BigInteger(), nullable=False),
    )
    op.create_table(
        "facility_outage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("customers_lost", sa.Float(), nullable=False),
    )
    op.create_index("ix_facility_outage_turn", "facility_outage", ["turn"])
    op.execute("UPDATE save_meta SET schema_version = 28")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 27")
    op.drop_index("ix_facility_outage_turn", table_name="facility_outage")
    op.drop_table("facility_outage")
    op.drop_table("supply_contract")
    op.drop_table("supply_month")
    op.drop_table("facility")
