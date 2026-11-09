"""M19: mining operations (formulas.md section 35). `mine` holds each mine by its facility's id
(its hidden overrun and the deposit's truth in the hidden_* fields: ADR-0007), `mine_deal` the
contracts and offtakes mines sign as sellers, `mine_rival_bid` rivals' bids for the group's
projects and mines, each record's fields in a JSON `data` column (data-dictionary.md); accounts
1520, 2610, 4400, 6750 and 6960.

Revision ID: 0043_m19
Revises: 0042_m18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043_m19"
down_revision: str | None = "0042_m18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNTS = (
    ("1520_mineral_properties", "Mineral properties", "asset"),
    ("2610_asset_retirement_obligation", "Asset retirement obligation", "liability"),
    ("4400_revenue_commodities", "Commodity sales", "revenue"),
    ("6750_depletion", "Depletion", "expense"),
    ("6960_royalties", "Royalties and state shares", "expense"),
)
TABLES = (("mine", "company_id"), ("mine_deal", "mine_id"), ("mine_rival_bid", "company_id"))


def upgrade() -> None:
    for name, key in TABLES:
        op.create_table(
            name,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(key, sa.Integer(), nullable=False),
            sa.Column("data", sa.JSON(), nullable=False),
        )
    conn = op.get_bind()
    has_accounts = conn.execute(sa.text("SELECT COUNT(*) FROM account")).scalar()
    if has_accounts:  # a new save gets them from data
        for code, name, kind in ACCOUNTS:
            conn.execute(
                sa.text(
                    "INSERT INTO account (code, name, type) SELECT :c, :n, :t "
                    "WHERE NOT EXISTS (SELECT 1 FROM account WHERE code = :c)"
                ),
                {"c": code, "n": name, "t": kind},
            )
    op.execute("UPDATE save_meta SET schema_version = 43")


def downgrade() -> None:
    for name, _ in reversed(TABLES):
        op.drop_table(name)
    for code, _, _ in ACCOUNTS:
        op.execute(
            f"DELETE FROM account WHERE code = '{code}' AND NOT EXISTS "
            f"(SELECT 1 FROM ledger_line WHERE account_code = '{code}')"
        )
    op.execute("UPDATE save_meta SET schema_version = 42")
