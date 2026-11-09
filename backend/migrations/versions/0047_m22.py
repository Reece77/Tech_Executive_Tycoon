"""M22: geopolitics and export controls (formulas.md section 39). `geo_record` holds every
geopolitical record (seeded tension months, seeded rules and suspensions, licences, compliant
variants, entity listings, sites, blocked customers leaving, and event notices), one row each:
`kind` names the collection and `data` the record's fields (data-dictionary.md); accounts 5100
and 5110. Existing saves have none: nothing to fill (history is data, the same on every seed).

Revision ID: 0047_m22
Revises: 0046_m21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047_m22"
down_revision: str | None = "0046_m21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNTS = (
    ("5100_tariffs", "Tariffs", "expense"),
    ("5110_local_partner_share", "Local partner's share", "expense"),
)


def upgrade() -> None:
    op.create_table(
        "geo_record",
        sa.Column("n", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    conn = op.get_bind()
    has_accounts = conn.execute(sa.text("SELECT COUNT(*) FROM account")).scalar()
    if has_accounts:  # a new save gets them from data
        for code, name, kind in ACCOUNTS:
            conn.execute(
                sa.text(
                    "INSERT INTO account (code, name, type) SELECT :c, :n, :t "
                    "WHERE NOT EXISTS (SELECT 1 FROM account WHERE code = :c)"
                ),
                {"c": code, "n": name, "t": kind},
            )
    op.execute("UPDATE save_meta SET schema_version = 47")


def downgrade() -> None:
    op.drop_table("geo_record")
    for code, _, _ in ACCOUNTS:
        op.execute(
            f"DELETE FROM account WHERE code = '{code}' AND NOT EXISTS "  # noqa: S608 - constants
            f"(SELECT 1 FROM ledger_line WHERE account_code = '{code}')"
        )
    op.execute("UPDATE save_meta SET schema_version = 46")
