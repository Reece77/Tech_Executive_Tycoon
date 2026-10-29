"""M6 sub-task 2: relationships (docs/formulas.md 16.7). The M1a `relationship` table was never
written, so it is rebuilt with the true value, the start value it drifts toward and the turn
the pair began. Existing saves start with no pairs; phase 8 of the next turn creates them.

Revision ID: 0015_relationships
Revises: 0014_free_agents
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_relationships"
down_revision: str | None = "0014_free_agents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("relationship")
    op.create_table(
        "relationship",
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id"), primary_key=True),
        sa.Column("other_person_id", sa.Integer(), sa.ForeignKey("person.id"), primary_key=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("start_value", sa.Float(), nullable=False),
        sa.Column("since_turn", sa.Integer(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 15")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 14")
    op.drop_table("relationship")
    op.create_table(
        "relationship",
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id"), primary_key=True),
        sa.Column("other_person_id", sa.Integer(), sa.ForeignKey("person.id"), primary_key=True),
        sa.Column("affinity", sa.Float(), nullable=False),
        sa.Column("updated_turn", sa.Integer(), nullable=False),
    )
