"""M10b: inbox items can be bookmarked (`inbox_item.bookmarked`, formulas.md 23.1): a
bookmarked item is never auto-archived. A UI flag with no game effect; existing items start
unbookmarked.

Revision ID: 0024_inbox_bookmark
Revises: 0023_geo
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_inbox_bookmark"
down_revision: str | None = "0023_geo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inbox_item",
        sa.Column("bookmarked", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.execute("UPDATE save_meta SET schema_version = 24")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 23")
    with op.batch_alter_table("inbox_item") as batch:
        batch.drop_column("bookmarked")
