"""M52: custom scenarios (formulas.md 66.2, ADR-0026 point 4). `custom_scenario` holds the
canonical YAML of the custom scenario a game was started from, with its SHA-256 (the same hash
is in the mode record, `game_mode.data.scenario_sha256`), one row at most. Existing saves have
none: they were not started from a custom scenario.

Revision ID: 0068_m52
Revises: 0067_m53
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0068_m52"
down_revision: str | None = "0067_m53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_scenario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("yaml", sa.Text(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 68")


def downgrade() -> None:
    op.drop_table("custom_scenario")
    op.execute("UPDATE save_meta SET schema_version = 67")
