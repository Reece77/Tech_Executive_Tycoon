"""M34: regulation with teeth (formulas.md 48). `regulation_record` holds every regulation
record (designations from the model, designation warnings, duties, investigations, structural
warning signs and orders), one row each: `kind` names the collection and `data` the record's
fields (data-dictionary.md). History's designations and cases are regulation.yaml's, not rows.
Existing saves have none: the model starts in January 2026.

Revision ID: 0055_m34
Revises: 0054_m30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0055_m34"
down_revision: str | None = "0054_m30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "regulation_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 55")


def downgrade() -> None:
    op.drop_table("regulation_record")
    op.execute("UPDATE save_meta SET schema_version = 54")
