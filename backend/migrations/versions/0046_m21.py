"""M21: fabs and process nodes (formulas.md section 38). `fab` holds each fab's own state beside
its facility row (keyed by the facility id: node, the quoted capex, EUV tools, yield, capex
parts, a conversion, its latest month and history) in a JSON `data` column; a wafer contract
may name a node (`production_contract.node`, nullable: M12b's wafers); account 4420. Existing
saves have no fabs and no node contracts: nothing to fill.

Revision ID: 0046_m21
Revises: 0045_m20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046_m21"
down_revision: str | None = "0045_m20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNT = ("4420_foundry_sales", "Foundry sales", "revenue")


def upgrade() -> None:
    op.create_table(
        "fab",
        sa.Column("facility_id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    with op.batch_alter_table("production_contract") as batch:
        batch.add_column(sa.Column("node", sa.String(16), nullable=True))
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
    op.execute("UPDATE save_meta SET schema_version = 46")


def downgrade() -> None:
    with op.batch_alter_table("production_contract") as batch:
        batch.drop_column("node")
    op.drop_table("fab")
    op.execute(
        "DELETE FROM account WHERE code = '4420_foundry_sales' AND NOT EXISTS "
        "(SELECT 1 FROM ledger_line WHERE account_code = '4420_foundry_sales')"
    )
    op.execute("UPDATE save_meta SET schema_version = 45")
