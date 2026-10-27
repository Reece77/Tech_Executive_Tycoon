"""M4b: the turn each stage is reached (`company.stage_history`) and each director's recent
confidence (table `board_seat_history`), for "Stage 2 since Jan 2012" and the Board tab's
trend.

An existing save cannot know when its company reached its current stage, so its history
starts empty and the API shows no "since" date; each director's history starts with their
current confidence. The history is a table of its own rather than a column on board_seat
because migration 0009 builds board_seat rows from the current models.

Revision ID: 0010_stage_board_history
Revises: 0009_finance
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_stage_board_history"
down_revision: str | None = "0009_finance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "company", sa.Column("stage_history", sa.JSON(), nullable=False, server_default="[]")
    )
    op.create_table(
        "board_seat_history",
        sa.Column("seat_id", sa.Integer(), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["seat_id"], ["board_seat.id"]),
        sa.PrimaryKeyConstraint("seat_id"),
    )
    conn = op.get_bind()
    seats = conn.execute(sa.text("SELECT id, confidence FROM board_seat ORDER BY id")).all()
    for seat_id, confidence in seats:
        conn.execute(
            sa.text("INSERT INTO board_seat_history (seat_id, history) VALUES (:id, :h)"),
            {"id": seat_id, "h": json.dumps([] if confidence is None else [confidence])},
        )
    op.execute("UPDATE save_meta SET schema_version = 10")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 9")
    op.drop_table("board_seat_history")
    op.drop_column("company", "stage_history")
