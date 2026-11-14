"""M36: family and succession (formulas.md 45). The player's family (`family`, one row, its
public record as JSON) and its members (`family_member`, by person id, JSON). Family members
are people in `person`; a save without a family has no rows (Family none).

Revision ID: 0053_m36
Revises: 0052_m31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0053_m36"
down_revision: str | None = "0052_m31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "family",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "family_member",
        sa.Column("person_id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 53")


def downgrade() -> None:
    op.drop_table("family_member")
    op.drop_table("family")
    op.execute("UPDATE save_meta SET schema_version = 52")
