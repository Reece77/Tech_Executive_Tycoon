"""M53: telecom (formulas.md 62). `telecom_record` holds every telecom record (the player's radio,
fibre and cable networks, spectrum licences, auctions with their awards, line settings, network
months and cash, and the game-wide `telecom_world`), one row each: `kind` names the collection and
`data` the record's fields (data-dictionary.md). Existing saves have none, and no telecom markets:
like M40's space, telecom comes only with a new game.

Revision ID: 0067_m53
Revises: 0066_m50
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0067_m53"
down_revision: str | None = "0066_m50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telecom_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 67")


def downgrade() -> None:
    op.drop_table("telecom_record")
    op.execute("UPDATE save_meta SET schema_version = 66")
