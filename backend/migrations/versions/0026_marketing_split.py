"""M10b: a product's marketing budget split by region (`product_marketing_split`, formulas.md
23.5). No rows means the default: the budget follows revenue by region. Existing saves start
with none.

Revision ID: 0026_marketing_split
Revises: 0025_event_modifiers
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_marketing_split"
down_revision: str | None = "0025_event_modifiers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_marketing_split",
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("product.id"), primary_key=True),
        sa.Column("region", sa.String(32), primary_key=True),
        sa.Column("share_bp", sa.Integer(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 26")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 25")
    op.drop_table("product_marketing_split")
