"""M4c: inbox items can be archived (`inbox_item.archived`): hidden from the inbox unless the
player asks for the archive. A UI flag with no game effect; existing items start unarchived.

Revision ID: 0012_inbox_archive
Revises: 0011_board_nominee
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_inbox_archive"
down_revision: str | None = "0011_board_nominee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inbox_item",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.execute("UPDATE save_meta SET schema_version = 12")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 11")
    with op.batch_alter_table("inbox_item") as batch:
        batch.drop_column("archived")
