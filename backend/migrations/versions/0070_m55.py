"""M55: media and entertainment (formulas.md 65). `media_record` holds every media record (titles,
creative leads and leads on offer, line settings, licences, divest-or-ban laws, service and ad
months, the game-wide draws and the ad market's calibration), one row each: `kind` names the
collection and `data` the record's fields (data-dictionary.md). Existing saves have none, and no
media markets: like M53's telecom, media comes only with a new game.

Revision ID: 0070_m55
Revises: 0069_m54
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0070_m55"
down_revision: str | None = "0069_m54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.execute("UPDATE save_meta SET schema_version = 70")


def downgrade() -> None:
    op.drop_table("media_record")
    op.execute("UPDATE save_meta SET schema_version = 69")
