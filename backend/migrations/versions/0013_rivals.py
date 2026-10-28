"""M5 rivals (docs/formulas.md section 15): company personality and rival columns, id
counters, and tables workforce_pool, rival_effect, rival_move, poach_approach and
segment_share.

An existing save's incumbents become rivals at the save's turn, as at a new game: pools
sized from their current revenue, 8 key people, a marketing budget of 8% of revenue, and
opening cash of the table's months of revenue (15.1). This upgrade reads and writes the
state through the current models, so it must stay the newest data migration that does so;
a later migration that changes these tables adds its own columns after it runs.

Revision ID: 0013_rivals
Revises: 0012_inbox_archive
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_rivals"
down_revision: str | None = "0012_inbox_archive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _company_columns() -> tuple[sa.Column[object], ...]:
    """Fresh Column objects each call: one may be attached to only one table."""
    return (
        sa.Column("personality", sa.String(length=16), nullable=True),
        sa.Column("builder_skill", sa.Float(), nullable=True),
        sa.Column("target_margin_bp", sa.Integer(), nullable=True),
        sa.Column("is_startup", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("failed_turn", sa.Integer(), nullable=True),
        sa.Column("last_raise_turn", sa.Integer(), nullable=True),
    )


COUNTERS = ("rival_effect", "rival_move", "approach")
RIVAL_COUNTERS = ("rival_person", "rival_employment")  # rivals' own ids count from 1,000,001


def upgrade() -> None:
    for column in _company_columns():
        op.add_column("company", column)
    for name in COUNTERS:
        op.add_column(
            "save_meta",
            sa.Column(f"next_{name}_id", sa.Integer(), nullable=False, server_default="1"),
        )
    for name in RIVAL_COUNTERS:
        op.add_column(
            "save_meta",
            sa.Column(f"next_{name}_id", sa.Integer(), nullable=False, server_default="1000001"),
        )
    op.create_table(
        "workforce_pool",
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("function", sa.String(length=16), nullable=False),
        sa.Column("headcount", sa.Float(), nullable=False),
        sa.Column("skill", sa.Float(), nullable=False),
        sa.Column("morale", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("company_id", "function"),
    )
    op.create_table(
        "rival_effect",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("start_turn", sa.Integer(), nullable=False),
        sa.Column("end_turn", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "rival_move",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("segment", sa.String(length=32), nullable=True),
        sa.Column("detail", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rival_move_turn", "rival_move", ["turn"])
    op.create_table(
        "poach_approach",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rival_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("offer_cents", sa.BigInteger(), nullable=False),
        sa.Column("made_turn", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("resolved_turn", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["rival_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "segment_share",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("segment", sa.String(length=32), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("product_id", "segment"),
    )
    _seed_rivals()
    op.execute("UPDATE save_meta SET schema_version = 13")


def _seed_rivals() -> None:
    """An existing save's incumbents become rivals at its turn (15.1)."""
    conn = op.get_bind()
    meta = conn.execute(sa.text("SELECT master_seed FROM save_meta")).first()
    if meta is None:
        return  # a brand-new save: new_game sets the rivals up
    # Imported here so creating a new save does not read the data files twice.
    from sqlalchemy.orm import Session

    from tst.config import Settings
    from tst.db.mappers import entry_to_row
    from tst.db.state_io import load_state, sync_state
    from tst.loader import load_all
    from tst.sim.rivals.setup import setup_incumbents
    from tst.sim.rng import RngFactory

    loaded = load_all(Settings().data_dir)
    known = {row[0] for row in conn.execute(sa.text("SELECT code FROM account"))}
    for account in loaded.game_data.accounts:  # saves from M0 may predate some accounts
        if account.code not in known:
            conn.execute(
                sa.text("INSERT INTO account (code, name, type) VALUES (:c, :n, :t)"),
                {"c": account.code, "n": account.name, "t": account.type},
            )
    session = Session(bind=conn)
    old = load_state(session)
    new, entries = setup_incumbents(old, RngFactory(int(meta[0])), loaded.balance, loaded.game_data)
    sync_state(session, old, new)
    session.add_all(entry_to_row(e) for e in entries)
    session.flush()


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 12")
    # The rivals' own people, employments, knowledge and books go (ids from 1,000,001).
    first = 1_000_001
    for table in ("person_state", "person_reveal", "person_profile_reveal", "person_tag_reveal"):
        op.execute(f"DELETE FROM {table} WHERE person_id >= {first}")
    for table in (
        "person_skill",
        "person_personality",
        "person_hidden",
        "person_interest",
        "person_tag",
        "person_morale_log",
    ):
        op.execute(f"DELETE FROM {table} WHERE person_id >= {first}")
    op.execute(f"DELETE FROM employment WHERE id >= {first}")
    op.execute(f"DELETE FROM person WHERE id >= {first}")
    op.execute(
        "DELETE FROM ledger_line WHERE entry_id IN (SELECT id FROM ledger_entry WHERE company_id"
        " IN (SELECT id FROM company WHERE is_player = 0))"
    )
    op.execute(
        "DELETE FROM ledger_entry WHERE company_id IN (SELECT id FROM company WHERE is_player = 0)"
    )
    # Rival moves in decision_log, and startups with their products and history.
    op.execute("DELETE FROM decision_log WHERE source = 'rival'")
    startups = "SELECT id FROM company WHERE is_startup = 1"
    products = f"SELECT id FROM product WHERE company_id IN ({startups})"
    for table in ("product_month", "product_segment"):
        op.execute(f"DELETE FROM {table} WHERE product_id IN ({products})")
    op.execute(f"DELETE FROM product WHERE company_id IN ({startups})")
    for table in ("turn_log", "turn_snapshot"):
        op.execute(
            f"DELETE FROM {table} WHERE company_id IN (SELECT id FROM company WHERE is_player = 0)"
        )
    op.execute(
        "UPDATE product SET marketing_budget_cents = 0 WHERE company_id IN "
        "(SELECT id FROM company WHERE is_player = 0)"
    )
    op.drop_table("segment_share")
    op.drop_table("poach_approach")
    op.drop_index("ix_rival_move_turn", table_name="rival_move")
    op.drop_table("rival_move")
    op.drop_table("rival_effect")
    op.drop_table("workforce_pool")
    op.execute(f"DELETE FROM company WHERE id IN ({startups})")
    # Native DROP COLUMN (SQLite 3.35+): a batch rebuild of company would break the foreign
    # keys that point at it.
    for name in (*COUNTERS, *RIVAL_COUNTERS):
        op.execute(f"ALTER TABLE save_meta DROP COLUMN next_{name}_id")
    for column in _company_columns():
        op.execute(f"ALTER TABLE company DROP COLUMN {column.name}")
