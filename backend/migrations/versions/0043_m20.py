"""M20: refining and wafers (formulas.md section 36). `refinery` holds each refinery's own
state beside its facility row (keyed by the facility id: recipe, the quoted capex, curbs,
incidents, its latest month and history), `refining_deal` refinery contracts, and
`refining_supply` the month's own-group supply lots, each record's fields in a JSON `data`
column (data-dictionary.md); account 4410. Existing saves have no refineries: nothing to fill.

Revision ID: 0043_m20
Revises: 0042_m18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043_m20"
down_revision: str | None = "0042_m18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNT = ("4410_materials_sales", "Materials sales", "revenue")


def upgrade() -> None:
    op.create_table(
        "refinery",
        sa.Column("facility_id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "refining_deal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "refining_supply",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    conn = op.get_bind()
    has_accounts = conn.execute(sa.text("SELECT COUNT(*) FROM account")).scalar()
    if has_accounts:  # a new save gets it from data
        code, name, kind = ACCOUNT
        conn.execute(
            sa.text(
                "INSERT INTO account (code, name, type) SELECT :c, :n, :t "
                "WHERE NOT EXISTS (SELECT 1 FROM account WHERE code = :c)"
            ),
            {"c": code, "n": name, "t": kind},
        )
    op.execute("UPDATE save_meta SET schema_version = 43")


def downgrade() -> None:
    for name in ("refining_supply", "refining_deal", "refinery"):
        op.drop_table(name)
    op.execute(
        "DELETE FROM account WHERE code = '4410_materials_sales' AND NOT EXISTS "
        "(SELECT 1 FROM ledger_line WHERE account_code = '4410_materials_sales')"
    )
    op.execute("UPDATE save_meta SET schema_version = 42")
