"""M1b inbox: rendered messages for the player company.

Revision ID: 0004_inbox
Revises: 0003_hiring
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_inbox"
down_revision: str | None = "0003_hiring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inbox_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("template", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link_kind", sa.String(length=16), nullable=True),
        sa.Column("link_id", sa.Integer(), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inbox_item_company_read", "inbox_item", ["company_id", "read"])
    op.execute("UPDATE save_meta SET schema_version = 4")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 3")
    op.drop_index("ix_inbox_item_company_read", table_name="inbox_item")
    op.drop_table("inbox_item")
