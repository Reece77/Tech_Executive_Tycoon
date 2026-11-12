"""M23a: v3 integration (formulas.md 31, 35, 38, 39). `production_month.fab_chips`: a chip
product's month of chips from the group's own fabs (the tariff's origin, Codex review 5 finding
5). The new records (counterparties' memory, foundry contracts) live in `geo_record` as new kinds
and the new fields of fabs, refinery supply lots and fab months in their JSON `data`: nothing
else changes. Existing saves get 0 (no own-fab chips recorded before).

Revision ID: 0048_m23a
Revises: 0047_m22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0048_m23a"
down_revision: str | None = "0047_m22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("production_month") as batch:
        batch.add_column(sa.Column("fab_chips", sa.Float(), nullable=False, server_default="0"))
    op.execute("UPDATE save_meta SET schema_version = 48")


def downgrade() -> None:
    with op.batch_alter_table("production_month") as batch:
        batch.drop_column("fab_chips")
    op.execute("UPDATE save_meta SET schema_version = 47")
