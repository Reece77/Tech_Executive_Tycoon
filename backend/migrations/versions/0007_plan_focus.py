"""M2b: a hiring plan's focus, `current` (best now, the default) or `potential`
(formulas.md 13.10). Existing plans keep `current`.

Revision ID: 0007_plan_focus
Revises: 0006_search_plan
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_plan_focus"
down_revision: str | None = "0006_search_plan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "hiring_plan",
        sa.Column("focus", sa.String(length=16), nullable=False, server_default="current"),
    )
    op.execute("UPDATE save_meta SET schema_version = 7")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 6")
    op.drop_column("hiring_plan", "focus")
