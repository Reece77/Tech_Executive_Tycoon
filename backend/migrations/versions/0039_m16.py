"""M16: the holding company and its subsidiaries (formulas.md section 31). `group_ownership`
holds every company's holdings of another over a run of turns (31.1; Codex review 4 findings 2
and 3), `group_holding` the player's holding company (31.2) and `group_stake` the stakes it
does not control (31.3, 31.5), each record's fields in a JSON
`data` column (data-dictionary.md); accounts 1820, 1830,
3500, 4910, 4920, 4930 and 4990 (31.3).

Existing saves: each kept brand (`company_parent`) gets an open holding from its latest
closing by that parent, with the 1810 investment its parent posted at closing (the
"Acquisition of <name>" entry) and its equity accounts' balance at the end of that turn. A
brand that has already failed keeps an open holding: the next month end disposes of it.

Revision ID: 0039_m16
Revises: 0038_m15r
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039_m16"
down_revision: str | None = "0038_m15r"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNTS = (
    ("1820_investment_associates", "Investments in associates", "asset"),
    ("1830_financial_investments", "Financial investments", "asset"),
    ("3500_non_controlling_interest", "Non-controlling interest", "equity"),
    ("4910_share_of_associates", "Share of associates' profit", "revenue"),
    ("4920_fair_value_gains", "Fair-value gains and losses", "revenue"),
    ("4930_gain_on_disposal", "Gain or loss on disposal", "revenue"),
    ("4990_nci_share_of_profit", "Attributable to non-controlling interest", "expense"),
)
INVESTMENT = "1810_investment_subsidiaries"


def upgrade() -> None:
    op.create_table(
        "group_ownership",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_index("ix_group_ownership_company", "group_ownership", ["company_id"])
    op.create_table(
        "group_stake",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_table(
        "group_holding",
        sa.Column("company_id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    conn = op.get_bind()
    has_accounts = conn.execute(sa.text("SELECT COUNT(*) FROM account")).scalar()
    for code, name, kind in ACCOUNTS if has_accounts else ():  # a new save gets them from data
        conn.execute(
            sa.text(
                "INSERT INTO account (code, name, type) SELECT :c, :n, :t "
                "WHERE NOT EXISTS (SELECT 1 FROM account WHERE code = :c)"
            ),
            {"c": code, "n": name, "t": kind},
        )
    _backfill(conn)
    op.execute("UPDATE save_meta SET schema_version = 39")


def _backfill(conn: sa.Connection) -> None:
    tables = set(sa.inspect(conn).get_table_names())
    if not {"company_parent", "mna_acquisition"} <= tables:
        return
    closings: dict[tuple[int, int], int] = {}
    for (data,) in conn.execute(sa.text("SELECT data FROM mna_acquisition")):
        record = json.loads(data) if isinstance(data, str) else data
        if record.get("mode") != "brand":
            continue
        key = (int(record["target_id"]), int(record["acquirer_id"]))
        closings[key] = max(closings.get(key, 0), int(record["closed_turn"]))
    parents = conn.execute(
        sa.text(
            "SELECT p.company_id, p.parent_id, c.name FROM company_parent p "
            "JOIN company c ON c.id = p.company_id ORDER BY p.company_id"
        )
    ).all()
    for oid, (company_id, parent_id, name) in enumerate(parents, start=1):
        closed = closings.get((company_id, parent_id), 0)
        book = conn.execute(
            sa.text(
                "SELECT COALESCE(SUM(l.amount_cents), 0) FROM ledger_line l "
                "JOIN ledger_entry e ON e.id = l.entry_id "
                "WHERE e.company_id = :p AND e.turn = :t AND e.memo = :m AND l.account_code = :a"
            ),
            {"p": parent_id, "t": closed, "m": f"Acquisition of {name}", "a": INVESTMENT},
        ).scalar()
        equity = conn.execute(
            sa.text(
                "SELECT COALESCE(SUM(l.amount_cents), 0) FROM ledger_line l "
                "JOIN ledger_entry e ON e.id = l.entry_id "
                "JOIN account a ON a.code = l.account_code "
                "WHERE e.company_id = :c AND e.turn <= :t AND a.type = 'equity'"
            ),
            {"c": company_id, "t": closed},
        ).scalar()
        data = {
            "from_turn": closed,
            "to_turn": None,
            "book_cents": int(book or 0),
            "equity_cents": int(equity or 0),
            "stake_bp": 10_000,
            "end_reason": None,
        }
        conn.execute(
            sa.text(
                "INSERT INTO group_ownership (id, company_id, owner_id, data) "
                "VALUES (:i, :c, :o, :d)"
            ),
            {"i": oid, "c": company_id, "o": parent_id, "d": json.dumps(data)},
        )


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 38")
    op.drop_table("group_holding")
    op.drop_table("group_stake")
    op.drop_index("ix_group_ownership_company", table_name="group_ownership")
    op.drop_table("group_ownership")
    for code, _, _ in ACCOUNTS:
        op.execute(
            f"DELETE FROM account WHERE code = '{code}' AND NOT EXISTS "
            f"(SELECT 1 FROM ledger_line WHERE account_code = '{code}')"
        )
