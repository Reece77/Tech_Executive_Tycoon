"""M24: the founder's life (formulas.md section 32): founders' stress, burnout and persona
(`founder_life`), the founder's own double-entry book (`personal_entry`, apart from the
companies' `ledger_entry`), foundations (`foundation`) and influence by region (`influence`,
whose JSON holds the hidden scandal risk). Records keep their fields in a JSON `data` column
(data-dictionary.md). Existing saves have none: their founder starts at stress 20 and every
trait at 20 at the next month end.

Revision ID: 0037_founder
Revises: 0036_m15a
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037_founder"
down_revision: str | None = "0036_m15a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "founder_life",
        sa.Column("person_id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "personal_entry",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("memo", sa.String(200), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("lines", sa.JSON(), nullable=False),
    )
    op.create_index("ix_personal_entry_person_id", "personal_entry", ["person_id"])
    op.create_table(
        "foundation",
        sa.Column("person_id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "influence",
        sa.Column("company_id", sa.Integer(), primary_key=True),
        sa.Column("region", sa.String(40), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 37")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 36")
    op.drop_index("ix_personal_entry_person_id", table_name="personal_entry")
    for table in ("influence", "foundation", "personal_entry", "founder_life"):
        op.drop_table(table)
