"""M7b: "Ask my COO" (docs/formulas.md 17.3). `coo_answer` keeps the last `coo.keep_answers`
questions and answers of a save, read-only and never fed into events.

Revision ID: 0019_coo_answer
Revises: 0018_person_rating_log
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_coo_answer"
down_revision: str | None = "0018_person_rating_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "coo_answer",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id"), nullable=True),
        sa.Column("speaker", sa.String(120), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("cost_cents", sa.Float(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 19")


def downgrade() -> None:
    op.drop_table("coo_answer")
    op.execute("UPDATE save_meta SET schema_version = 18")
