"""M31: platforms and ecosystems (formulas.md 44, ADR-0021). `platform_record` holds every
platform record (platforms, their regions, device lines' platforms, listings, gatekeepers'
reviews, open-sourced products, standards and products' formats, the player's steering apps
and rival stores), one row each: `kind` names the collection and `data` the record's fields
(data-dictionary.md). Existing saves have none: the platforms materialise in the next month.

Revision ID: 0052_m31
Revises: 0051_m27b
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0052_m31"
down_revision: str | None = "0051_m27b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 51")


def downgrade() -> None:
    op.drop_table("platform_record")
    op.execute("UPDATE save_meta SET schema_version = 50")
