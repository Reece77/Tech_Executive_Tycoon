"""M15r (Codex review 4 finding 8): `production_contract.price_cents` (0031, FLOAT) becomes
`price_millicents`, the unit fee or wafer price in exact integer thousandths of a cent.
Existing rows convert once, rounded to the nearest millicent.

Revision ID: 0038_m15r
Revises: 0037_founder
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038_m15r"
down_revision: str | None = "0037_founder"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("production_contract") as batch:
        batch.add_column(sa.Column("price_millicents", sa.BigInteger(), nullable=True))
    op.execute("UPDATE production_contract SET price_millicents = CAST(ROUND(price_cents * 1000) AS INTEGER)")
    with op.batch_alter_table("production_contract") as batch:
        batch.alter_column("price_millicents", existing_type=sa.BigInteger(), nullable=False)
        batch.drop_column("price_cents")
    op.execute("UPDATE save_meta SET schema_version = 38")


def downgrade() -> None:
    with op.batch_alter_table("production_contract") as batch:
        batch.add_column(sa.Column("price_cents", sa.Float(), nullable=True))
    op.execute("UPDATE production_contract SET price_cents = price_millicents / 1000.0")
    with op.batch_alter_table("production_contract") as batch:
        batch.alter_column("price_cents", existing_type=sa.Float(), nullable=False)
        batch.drop_column("price_millicents")
    op.execute("UPDATE save_meta SET schema_version = 37")
