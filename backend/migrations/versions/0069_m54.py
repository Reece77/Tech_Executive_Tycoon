"""M54: financial services and currencies (formulas.md 64). `finserv_record` holds every financial
services record (banks with their balance sheets, payments networks, insurers, their months and the
game-wide `finserv_world`), and `fx_record` every currency record (translation marks, hedges, the
indexes' walk after 2025 and the hedging programme), one row each: `kind` names the collection and
`data` the record's fields (data-dictionary.md). Existing saves have none, and no finance markets:
like M53's telecom, financial services come only with a new game; an existing save's indexes read
fx_history.yaml.

Revision ID: 0069_m54
Revises: 0068_m52
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0069_m54"
down_revision: str | None = "0068_m52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in ("finserv_record", "fx_record"):
        op.create_table(
            name,
            sa.Column("n", sa.Integer(), primary_key=True),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("data", sa.JSON(), nullable=False),
        )
    op.execute("UPDATE save_meta SET schema_version = 68")


def downgrade() -> None:
    op.drop_table("fx_record")
    op.drop_table("finserv_record")
    op.execute("UPDATE save_meta SET schema_version = 67")
