"""M57r-B (review 10 item 34): a save made before 0066_m50 and begun after January 2010 (a
Sandbox or scenario from 2015, say) was backfilled with `save_meta.start_turn = 0`. Its game
began in the month it was created, so `start_turn = created_turn` where `created_turn > 0`.
A 2010 game (created at 0) and a 2008 game (created at -24, and recorded right since M50) are
unchanged. Data only: 0066 is never edited.

Revision ID: 0071_m57rb
Revises: 0070_m55
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0071_m57rb"
down_revision: str | None = "0070_m55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE save_meta SET start_turn = created_turn WHERE created_turn > 0 AND start_turn = 0"
    )
    op.execute("UPDATE save_meta SET schema_version = 71")


def downgrade() -> None:
    # The backfill is not undone (0066's 0 was wrong); the schema is unchanged.
    op.execute("UPDATE save_meta SET schema_version = 70")
