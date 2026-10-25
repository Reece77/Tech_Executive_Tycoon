"""M2a: searches remember the hiring plan they serve, so a filled or closed plan's job posts
can close (formulas.md 13.10). Existing searches get NULL (opened by the player).

Revision ID: 0006_search_plan
Revises: 0005_org
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_search_plan"
down_revision: str | None = "0005_org"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No REFERENCES clause, as for the columns 0005_org added to existing tables.
    op.add_column("search", sa.Column("plan_id", sa.Integer(), nullable=True))
    op.execute("UPDATE save_meta SET schema_version = 6")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 5")
    op.drop_column("search", "plan_id")
