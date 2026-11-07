"""M15b: game modes and polish (formulas.md section 30): company scores each December and at
a game's end (`company_score`), the save's mode, Sandbox or a scenario (`game_mode`, one row
at most), and each January's industry rankings (`ranking`). Records keep their fields in a JSON
`data` column (data-dictionary.md). Also each product's quality and customers at the last
quarterly reports (`product_quarter_mark`), the next reports' starting values, and the
companies a serial founder sold (`venture`, addendum 10). Existing saves have none: a campaign with no history.

Revision ID: 0035_m15b
Revises: 0034_mna
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035_m15b"
down_revision: str | None = "0034_mna"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_score",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("turn", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "game_mode",
        sa.Column("id", sa.Integer(), primary_key=True),  # always 1
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "ranking",
        sa.Column("turn", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(16), primary_key=True),
        sa.Column("place", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "product_quarter_mark",
        sa.Column("product_id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "venture",
        sa.Column("company_id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 35")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 34")
    for table in ("venture", "product_quarter_mark", "ranking", "game_mode", "company_score"):
        op.drop_table(table)
