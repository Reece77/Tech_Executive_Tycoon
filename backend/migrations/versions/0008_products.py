"""M3a products and markets: products, their segments, market demand and monthly history;
unit and root assignments; the ARR milestone; the product id counter.

A brand-new save (no save_meta row yet) gets its market from `new_game`. An existing save
gets the 2010 market from the current categories.yaml and incumbents.yaml, with addressable
demand grown to the save's turn and each incumbent holding its starting share of that demand
(ADR-0017). Incumbent companies take the ids after the highest existing company id.

Revision ID: 0008_products
Revises: 0007_plan_focus
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_products"
down_revision: str | None = "0007_plan_focus"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FIRST_PRODUCT_ID = 1


def upgrade() -> None:
    op.create_table(
        "product",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("quality", sa.Float(), nullable=False),
        sa.Column("feature_points", sa.Float(), nullable=False),
        sa.Column("brand", sa.Float(), nullable=False),
        sa.Column("marketing_budget_cents", sa.BigInteger(), nullable=False),
        sa.Column("created_turn", sa.Integer(), nullable=False),
        sa.Column("launched_turn", sa.Integer(), nullable=True),
        sa.Column("sunset_turn", sa.Integer(), nullable=True),
        sa.Column("retired_turn", sa.Integer(), nullable=True),
        sa.Column("held_feature", sa.Float(), nullable=True),
        sa.Column("first_customer_turn", sa.Integer(), nullable=True),
        sa.Column("rotting", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_company_status", "product", ["company_id", "status"])
    op.create_table(
        "product_segment",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("segment", sa.String(length=32), nullable=False),
        sa.Column("price_cents", sa.BigInteger(), nullable=True),
        sa.Column("customers", sa.Float(), nullable=False),
        sa.Column("capacity_limited", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("added_turn", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"]),
        sa.PrimaryKeyConstraint("product_id", "segment"),
    )
    op.create_table(
        "market_segment",
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("segment", sa.String(length=32), nullable=False),
        sa.Column("addressable", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("category", "segment"),
    )
    op.create_table(
        "product_month",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("segment", sa.String(length=32), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("quality", sa.Float(), nullable=False),
        sa.Column("feature_score", sa.Float(), nullable=False),
        sa.Column("brand", sa.Float(), nullable=False),
        sa.Column("appeal", sa.Float(), nullable=True),
        sa.Column("customers", sa.Float(), nullable=False),
        sa.Column("new", sa.Float(), nullable=False),
        sa.Column("churned", sa.Float(), nullable=False),
        sa.Column("revenue_cents", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"]),
        sa.PrimaryKeyConstraint("product_id", "segment", "turn"),
    )
    op.create_index("ix_product_month_turn", "product_month", ["turn"])

    # As in 0005_org: columns added to existing tables carry no REFERENCES clause.
    op.add_column("org_unit", sa.Column("product_id", sa.Integer(), nullable=True))
    op.add_column("company", sa.Column("root_product_id", sa.Integer(), nullable=True))
    op.add_column(
        "company",
        sa.Column("arr_milestone_cents", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "save_meta",
        sa.Column("next_product_id", sa.Integer(), nullable=False, server_default="1"),
    )
    _seed_market()
    op.execute("UPDATE save_meta SET schema_version = 8")


def _seed_market() -> None:
    """Incumbents and demand for a save that already exists (none for a brand-new file)."""
    conn = op.get_bind()
    turn = conn.execute(sa.text("SELECT current_turn FROM save_meta")).scalar()
    if turn is None:
        return
    # Imported here so creating a new save does not read the data files twice.
    from tst.config import Settings
    from tst.loader import load_all
    from tst.sim.products.setup import initial_market

    data = load_all(Settings().data_dir).game_data
    top = conn.execute(sa.text("SELECT MAX(id) FROM company")).scalar() or 0
    market = initial_market(
        data, turn=int(turn), first_company_id=int(top) + 1, first_product_id=FIRST_PRODUCT_ID
    )
    company = sa.table(
        "company",
        sa.column("id"),
        sa.column("name"),
        sa.column("is_player"),
        sa.column("stage"),
        sa.column("founded_turn"),
        sa.column("mission"),
        sa.column("work_policy"),
    )
    product = sa.table(
        "product",
        *(
            sa.column(c)
            for c in (
                "id",
                "company_id",
                "category",
                "name",
                "status",
                "quality",
                "feature_points",
                "brand",
                "marketing_budget_cents",
                "created_turn",
                "launched_turn",
                "held_feature",
                "rotting",
            )
        ),
    )
    segment = sa.table(
        "product_segment",
        *(
            sa.column(c)
            for c in ("product_id", "segment", "price_cents", "customers", "added_turn")
        ),
    )
    demand = sa.table(
        "market_segment", sa.column("category"), sa.column("segment"), sa.column("addressable")
    )
    conn.execute(
        company.insert(),
        [
            {
                "id": c.id,
                "name": c.name,
                "is_player": False,
                "stage": c.stage,
                "founded_turn": c.founded_turn,
                "mission": "[]",
                "work_policy": c.work_policy,
            }
            for c in market.companies
        ],
    )
    conn.execute(
        product.insert(),
        [
            {
                "id": p.id,
                "company_id": p.company_id,
                "category": p.category,
                "name": p.name,
                "status": p.status,
                "quality": p.quality,
                "feature_points": p.feature_points,
                "brand": p.brand,
                "marketing_budget_cents": p.marketing_budget_cents,
                "created_turn": p.created_turn,
                "launched_turn": p.launched_turn,
                "held_feature": p.held_feature,
                "rotting": False,
            }
            for p in market.products
        ],
    )
    conn.execute(
        segment.insert(),
        [
            {
                "product_id": s.product_id,
                "segment": s.segment,
                "price_cents": s.price_cents,
                "customers": s.customers,
                "added_turn": s.added_turn,
            }
            for s in market.product_segments
        ],
    )
    conn.execute(
        demand.insert(),
        [
            {"category": m.category, "segment": m.segment, "addressable": m.addressable}
            for m in market.markets
        ],
    )
    conn.execute(
        sa.text("UPDATE save_meta SET next_product_id = :n"), {"n": market.next_product_id}
    )


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 7")
    op.drop_index("ix_product_month_turn", table_name="product_month")
    op.drop_table("product_month")
    op.drop_table("market_segment")
    op.drop_table("product_segment")
    op.drop_index("ix_product_company_status", table_name="product")
    op.drop_table("product")
    # Incumbents have no people, ledger or decisions, so nothing else references them.
    op.execute("DELETE FROM company WHERE is_player = 0")
    for table, column in (
        ("save_meta", "next_product_id"),
        ("company", "arr_milestone_cents"),
        ("company", "root_product_id"),
        ("org_unit", "product_id"),
    ):
        op.drop_column(table, column)
