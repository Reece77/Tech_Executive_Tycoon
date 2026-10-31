"""M7b: the saves manager. `save_meta.display_name` is the name the Saves screen shows; null
shows the file's slug. Renaming a save changes only this column (the company name and the
file stay as they are).

Revision ID: 0017_save_display_name
Revises: 0016_events
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_save_display_name"
down_revision: str | None = "0016_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("save_meta") as batch:
        batch.add_column(sa.Column("display_name", sa.String(80), nullable=True))
    op.execute("UPDATE save_meta SET schema_version = 17")


def downgrade() -> None:
    with op.batch_alter_table("save_meta") as batch:
        batch.drop_column("display_name")
    op.execute("UPDATE save_meta SET schema_version = 16")
