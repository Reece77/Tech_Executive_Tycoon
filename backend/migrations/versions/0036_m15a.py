"""M15a: a rival startup's run of months below rivals.startup.small_staff people
(formulas.md 30.7 V5): `startup_small`, one row per small startup. Existing saves have none:
every startup's count starts at the first month after the upgrade.

Revision ID: 0036_m15a
Revises: 0035_m15b
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036_m15a"
down_revision: str | None = "0035_m15b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "startup_small",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("since_turn", sa.Integer(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 36")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 35")
    op.drop_table("startup_small")
