"""M8 divisions, executives and new markets (docs/formulas.md 18).

- `ledger_line.division_id`: the division a line reports to; existing lines stay null
  (corporate), which is what they were.
- Side tables `unit_services` (a division's shared services), `product_division` (a
  product's division), `search_level` (exec-level searches), `exec_seat` (executive seats) and
  `division_month` (headcount per division at each payroll, for the shared-services
  allocation). They are tables of their own because migration 0013 loads and syncs
  org_unit, product and search through the current models on older saves.
- An existing save gets market rows for categories added since it was made (Fintech, AI
  models and inference), with demand grown to its turn. Their incumbents and scheduled
  entrants come only with new games (M8 brief, "Decisions made").

Revision ID: 0020_divisions
Revises: 0019_coo_answer
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_divisions"
down_revision: str | None = "0019_coo_answer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ledger_line") as batch:
        batch.add_column(
            sa.Column("division_id", sa.Integer(), nullable=True, server_default=sa.text("NULL"))
        )
    op.create_table(
        "unit_services",
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("org_unit.id"), primary_key=True),
        sa.Column("services", sa.String(16), nullable=False),
    )
    op.create_table(
        "product_division",
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("product.id"), primary_key=True),
        sa.Column("division_id", sa.Integer(), nullable=True),
    )
    op.create_table(
        "search_level",
        sa.Column("search_id", sa.Integer(), sa.ForeignKey("search.id"), primary_key=True),
        sa.Column("level", sa.String(16), nullable=False),
    )
    op.create_table(
        "exec_seat",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("seat", sa.String(8), primary_key=True),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("since_turn", sa.Integer(), nullable=False),
    )
    op.create_table(
        "division_month",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("division_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("headcount", sa.Integer(), nullable=False),
        sa.Column("embedded", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_division_month_company_turn", "division_month", ["company_id", "turn"])
    _add_markets()
    op.execute("UPDATE save_meta SET schema_version = 20")


def _add_markets() -> None:
    """Market rows for categories the save does not have yet, grown to its turn (11.1)."""
    conn = op.get_bind()
    meta = conn.execute(sa.text("SELECT current_turn FROM save_meta")).first()
    if meta is None:
        return  # a brand-new save: new_game makes every market
    from tst.config import Settings
    from tst.loader import load_all
    from tst.sim.products.setup import addressable_at

    data = load_all(Settings().data_dir).game_data
    have = {
        (row[0], row[1])
        for row in conn.execute(sa.text("SELECT category, segment FROM market_segment"))
    }
    for cat in data.categories:
        for market in cat.markets:
            if (cat.key, market.segment) in have:
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO market_segment (category, segment, addressable) "
                    "VALUES (:c, :s, :a)"
                ),
                {
                    "c": cat.key,
                    "s": market.segment,
                    "a": addressable_at(data, cat.key, market.segment, int(meta[0])),
                },
            )


def downgrade() -> None:
    op.drop_index("ix_division_month_company_turn", "division_month")
    for table in ("division_month", "exec_seat", "search_level", "product_division"):
        op.drop_table(table)
    op.drop_table("unit_services")
    with op.batch_alter_table("ledger_line") as batch:
        batch.drop_column("division_id")
    op.execute("UPDATE save_meta SET schema_version = 19")
