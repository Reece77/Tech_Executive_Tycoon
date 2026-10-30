"""M7b: History's hall of fame. `person_rating_log` holds each player employee's shown
rating at every month end (the mean midpoint of the displayed ranges of their role's primary
skills, as the player sees them; docs/formulas.md 17.2), so best hires and notable departures
come from stored rows. Existing saves start logging at their next turn.

Revision ID: 0018_person_rating_log
Revises: 0017_save_display_name
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_person_rating_log"
down_revision: str | None = "0017_save_display_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "person_rating_log",
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id"), primary_key=True),
        sa.Column("turn", sa.Integer(), primary_key=True),
        sa.Column("rating", sa.Float(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 18")


def downgrade() -> None:
    op.drop_table("person_rating_log")
    op.execute("UPDATE save_meta SET schema_version = 17")
