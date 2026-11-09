"""M25: a save's data-editor mod (M25 section 3). `save_meta.mod_name` names the mod the
game was started with, `save_meta.mod_hash` is the SHA-256 of the merged data it plays with,
and `save_meta.mod_overlay` keeps a copy of the overlay, so the save never changes when the
mod file does. Existing saves, and every game without a mod, have all three NULL.

Revision ID: 0040_m25
Revises: 0039_m16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040_m25"
down_revision: str | None = "0039_m16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("save_meta", sa.Column("mod_name", sa.String(64), nullable=True))
    op.add_column("save_meta", sa.Column("mod_hash", sa.String(64), nullable=True))
    op.add_column("save_meta", sa.Column("mod_overlay", sa.JSON(), nullable=True))
    op.execute("UPDATE save_meta SET schema_version = 40")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 39")
    with op.batch_alter_table("save_meta") as batch:
        batch.drop_column("mod_overlay")
        batch.drop_column("mod_hash")
        batch.drop_column("mod_name")
