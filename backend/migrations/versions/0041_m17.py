"""M17: commodities, offtake and regional power (formulas.md section 33). `supply_month` gains
`shock_kind` (a commodity shock's kind, 33.1): commodity and power months share M12a's table,
keyed by good. `commodity_deal` holds companies' commodity contracts and offtake agreements
(33.3), each record's fields in a JSON `data` column (data-dictionary.md). Prepayments use the
existing 1200_prepaid account.

Existing saves: no deals; commodity and power months start from history at the next turn
(a save past 2025 steps from December 2025's history, as M12a's goods do).

Revision ID: 0041_m17
Revises: 0040_m25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041_m17"
down_revision: str | None = "0040_m25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("supply_month") as batch:
        batch.add_column(sa.Column("shock_kind", sa.String(32), nullable=True))
    op.create_table(
        "commodity_deal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_index("ix_commodity_deal_company", "commodity_deal", ["company_id"])
    op.execute("UPDATE save_meta SET schema_version = 41")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 40")
    op.drop_index("ix_commodity_deal_company", table_name="commodity_deal")
    op.drop_table("commodity_deal")
    with op.batch_alter_table("supply_month") as batch:
        batch.drop_column("shock_kind")
