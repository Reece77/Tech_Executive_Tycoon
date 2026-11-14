"""M30: old history summarised, not lost (tst.db.history; data-dictionary.md). `turn_log_summary`
counts log items past the retention window a company, kind and year; `world_news_archive` keeps
the major World news items that left the state's window; `save_meta.history_pruned_through` is
the last month thinned; `ix_turn_snapshot_company_turn` serves a company's history, and
`ix_candidate_status` and `ix_person_is_founder` the loads' and screens' lookups. An existing
save's history is thinned here, once, to its current month (the turn then thins a month at a
time). The game reads none of these rows, so nothing it plays changes.

Revision ID: 0051_m30
Revises: 0050_m28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0051_m30"
down_revision: str | None = "0050_m28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "turn_log_summary",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("items", sa.Integer(), nullable=False),
    )
    op.create_index("ix_turn_log_summary_year", "turn_log_summary", ["year"])
    op.create_table(
        "world_news_archive",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("other_id", sa.Integer(), nullable=True),
        sa.Column("region", sa.String(64), nullable=True),
        sa.Column("good", sa.String(64), nullable=True),
    )
    op.create_index("ix_turn_snapshot_company_turn", "turn_snapshot", ["company_id", "turn"])
    op.create_index("ix_candidate_status", "candidate", ["status"])
    op.create_index("ix_person_is_founder", "person", ["is_founder"])
    op.add_column("save_meta", sa.Column("history_pruned_through", sa.Integer(), nullable=True))
    op.execute("UPDATE save_meta SET schema_version = 51")
    _catch_up()


def _catch_up() -> None:
    from sqlalchemy.orm import Session

    from tst.config import Settings
    from tst.db.history import prune
    from tst.loader import load_all

    session = Session(bind=op.get_bind())
    turn = session.execute(sa.text("SELECT current_turn FROM save_meta")).scalar()
    if turn is None:  # a new save: migrated before its first row is written
        return
    prune(session, int(turn) - 1, load_all(Settings().data_dir).balance.retention)
    session.flush()


def downgrade() -> None:
    with op.batch_alter_table("save_meta") as batch:
        batch.drop_column("history_pruned_through")
    op.drop_index("ix_person_is_founder", table_name="person")
    op.drop_index("ix_candidate_status", table_name="candidate")
    op.drop_index("ix_turn_snapshot_company_turn", table_name="turn_snapshot")
    op.drop_table("world_news_archive")
    op.drop_index("ix_turn_log_summary_year", table_name="turn_log_summary")
    op.drop_table("turn_log_summary")
    op.execute("UPDATE save_meta SET schema_version = 50")
