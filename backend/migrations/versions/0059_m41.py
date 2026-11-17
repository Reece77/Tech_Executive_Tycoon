"""M41: medical devices (formulas.md 50). `medical_record` holds every medical record (devices'
designs, submissions, clearances, studies, coverage, clinicians' adoption, plants' quality
systems, inspections, recalls and review drift), one row each: `kind` names the collection and
`data` the record's fields (data-dictionary.md). Existing saves have none, and keep the markets
and incumbents they started with: the medical sub-categories and their rivals come with new
games (as M12b's devices did).

Revision ID: 0059_m41
Revises: 0058_m38
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0059_m41"
down_revision: str | None = "0058_m38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "medical_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 59")


def downgrade() -> None:
    op.drop_table("medical_record")
    op.execute("UPDATE save_meta SET schema_version = 58")
