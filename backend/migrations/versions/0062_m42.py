"""M42: pharmaceuticals (formulas.md 55). `pharma_record` holds every pharmaceutical record
(programmes with their hidden efficacy and safety, readouts, reviews, authorisations, drugs,
HTAs, drug months, rivals' seeded approvals, rules, IRA picks, plants, contract supply,
inspections, recalls, assets for licence and deals), one row each: `kind` names the collection and
`data` the record's fields (data-dictionary.md). Existing saves have none, and no pharma rivals:
like M41's medical makers, they come only with a new game.

Revision ID: 0062_m42
Revises: 0061_m39
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062_m42"
down_revision: str | None = "0061_m39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pharma_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 62")


def downgrade() -> None:
    op.drop_table("pharma_record")
    op.execute("UPDATE save_meta SET schema_version = 61")
