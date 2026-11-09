"""M26: the founder's life, part 2: personal investing (formulas.md section 37).
`startup_round` holds rival startups' rounds and their prices, `angel_stake` the founder's
stakes in private startups, `personal_trade` trades of listed shares (with the hidden
regulatory risk and investigation draw, ADR-0007), `public_holding` listed shares held,
`family_office` the founder's family office, `wealth_point` net worth by month and
`market_index` the market index, `founder_network` people who left the player's companies; each record's fields in a JSON `data` column
(data-dictionary.md). The personal accounts 9110-9430 live in data (accounts.yaml), not in
the company chart.

Existing saves start with none of these: their rounds, index and net worth are recorded from
the next month.

Revision ID: 0044_m26
Revises: 0043_m19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044_m26"
down_revision: str | None = "0043_m19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("startup_round", ("id",)),
    ("angel_stake", ("id",)),
    ("personal_trade", ("id",)),
    ("public_holding", ("person_id", "company_id")),
    ("family_office", ("person_id",)),
    ("wealth_point", ("person_id", "turn")),
    ("market_index", ("turn",)),
    ("founder_network", ("person_id",)),
)


def upgrade() -> None:
    for name, keys in TABLES:
        op.create_table(
            name,
            *(sa.Column(k, sa.Integer(), primary_key=True, autoincrement=False) for k in keys),
            sa.Column("data", sa.JSON(), nullable=False),
        )
    op.execute("UPDATE save_meta SET schema_version = 44")


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 43")
    for name, _ in reversed(TABLES):
        op.drop_table(name)
