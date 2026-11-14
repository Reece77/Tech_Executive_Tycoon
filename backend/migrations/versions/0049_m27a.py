"""M27a: automation everywhere (formulas.md 40). `area_owner`: who runs each automated area of
a company (no row: the player manages it); `area_decision`: each owner's logged month; and
`inbox_item.in_digest`, set on items an automated area produced (the inbox's default view hides
them and the month's digest links to them). Existing saves get no owners and no flags, so they
play exactly as before (40.9).

Revision ID: 0049_m27a
Revises: 0048_m23a
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049_m27a"
down_revision: str | None = "0048_m23a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "area_owner",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("area", sa.String(32), primary_key=True),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("limit_cents", sa.BigInteger(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("since_turn", sa.Integer(), nullable=False),
        sa.Column("answer_events", sa.Boolean(), nullable=False),
        sa.Column("allow_bold", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "area_decision",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("turn", sa.Integer(), primary_key=True),
        sa.Column("seq", sa.Integer(), primary_key=True),
        sa.Column("area", sa.String(32), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("commitment_cents", sa.BigInteger(), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=True),
    )
    with op.batch_alter_table("inbox_item") as batch:
        batch.add_column(sa.Column("in_digest", sa.Boolean(), nullable=False, server_default="0"))
    op.execute("UPDATE save_meta SET schema_version = 49")


def downgrade() -> None:
    with op.batch_alter_table("inbox_item") as batch:
        batch.drop_column("in_digest")
    op.drop_table("area_decision")
    op.drop_table("area_owner")
    op.execute("UPDATE save_meta SET schema_version = 48")
