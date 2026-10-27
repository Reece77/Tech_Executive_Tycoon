"""M4a finance: the cap table in shares, option grants, SAFEs, priced rounds and term sheets,
board seats, the game state, MRR history and insolvency on the company, and the finance id
counters (ADR-0018).

A brand-new save (no save_meta row yet) gets all of this from `new_game`. An existing save
gets its scenario's cap table (docs/formulas.md 14.2); each employee's `equity_bp` becomes
options at 1,000 per bp from the pool, granted at their hire turn and vested to the save's
turn; the funded spinout also gets its closed seed and the lead's board seat with a
generated director (stream `board`); and the company's MRR history is read from its last
month-end snapshots.

Revision ID: 0009_finance
Revises: 0008_products
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0009_finance"
down_revision: str | None = "0008_products"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS_PER_BP = 1000  # pre-M4 equity: 1 bp of the 10,000,000-share start is 1,000 options
MRR_MONTHS = 13  # month ends of MRR kept on the company (the current one and six before, twice)


def upgrade() -> None:
    op.create_table(
        "cap_table_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("holder_kind", sa.String(length=16), nullable=False),
        sa.Column("share_class", sa.String(length=24), nullable=False),
        sa.Column("shares", sa.BigInteger(), nullable=False),
        sa.Column("acquired_turn", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("firm", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=True),
        sa.Column("round_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "option_grant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("employment_id", sa.Integer(), nullable=False),
        sa.Column("granted", sa.BigInteger(), nullable=False),
        sa.Column("start_turn", sa.Integer(), nullable=False),
        sa.Column("vested", sa.BigInteger(), nullable=False),
        sa.Column("forfeited", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.ForeignKeyConstraint(["employment_id"], ["employment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "safe",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("cap_cents", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("raised_turn", sa.Integer(), nullable=False),
        sa.Column("resolved_turn", sa.Integer(), nullable=True),
        sa.Column("expires_turn", sa.Integer(), nullable=True),
        sa.Column("converted_round_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "funding_round",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("series", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("target_cents", sa.BigInteger(), nullable=False),
        sa.Column("opened_turn", sa.Integer(), nullable=False),
        sa.Column("expires_turn", sa.Integer(), nullable=False),
        sa.Column("accepted_sheet_id", sa.Integer(), nullable=True),
        sa.Column("closed_turn", sa.Integer(), nullable=True),
        sa.Column("lead_firm", sa.String(length=32), nullable=True),
        sa.Column("pre_money_cents", sa.BigInteger(), nullable=True),
        sa.Column("amount_cents", sa.BigInteger(), nullable=True),
        sa.Column("fd_before", sa.BigInteger(), nullable=True),
        sa.Column("pool_shares", sa.BigInteger(), nullable=True),
        sa.Column("safe_shares", sa.BigInteger(), nullable=True),
        sa.Column("new_shares", sa.BigInteger(), nullable=True),
        sa.Column("fd_pre", sa.BigInteger(), nullable=True),
        sa.Column("down_round", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "term_sheet",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("round_id", sa.Integer(), nullable=False),
        sa.Column("firm", sa.String(length=32), nullable=False),
        sa.Column("pre_money_cents", sa.BigInteger(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("offered_turn", sa.Integer(), nullable=False),
        sa.Column("expires_turn", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["round_id"], ["funding_round.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "board_seat",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("seated_turn", sa.Integer(), nullable=False),
        sa.Column("firm", sa.String(length=32), nullable=True),
        sa.Column("round_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("months_below", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # As in 0005_org: columns added to existing tables carry no REFERENCES clause.
    op.add_column(
        "company", sa.Column("mrr_history", sa.JSON(), nullable=False, server_default="[]")
    )
    op.add_column(
        "company",
        sa.Column("insolvent_months", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "save_meta",
        sa.Column("game_state", sa.String(length=16), nullable=False, server_default="active"),
    )
    op.add_column("save_meta", sa.Column("ended_turn", sa.Integer(), nullable=True))
    for name in ("cap_entry", "grant", "safe", "round", "term_sheet", "seat"):
        op.add_column(
            "save_meta",
            sa.Column(f"next_{name}_id", sa.Integer(), nullable=False, server_default="1"),
        )
    _seed_finance()
    op.execute("UPDATE save_meta SET schema_version = 9")


def _seed_finance() -> None:
    """The cap table, grants, seed and board of a save that already exists."""
    conn = op.get_bind()
    meta = conn.execute(
        sa.text("SELECT current_turn, scenario_id, master_seed, next_person_id FROM save_meta")
    ).first()
    if meta is None:
        return
    turn, scenario_id, seed, next_person = int(meta[0]), str(meta[1]), int(meta[2]), int(meta[3])
    player = conn.execute(sa.text("SELECT id FROM company WHERE is_player = 1")).scalar()
    founder = conn.execute(
        sa.text(
            "SELECT p.id FROM person p JOIN employment e ON e.person_id = p.id "
            "WHERE p.is_founder = 1 AND e.company_id = :c"
        ),
        {"c": player},
    ).scalar()
    if player is None or founder is None:
        return
    # Imported here so creating a new save does not read the data files twice.
    from tst.config import Settings
    from tst.db.mappers import finance_to_row, person_to_rows
    from tst.loader import load_all
    from tst.sim.finance.formulas import vested_shares
    from tst.sim.finance.models import OptionGrant
    from tst.sim.finance.setup import initial_cap_table
    from tst.sim.hiring.models import NextIds
    from tst.sim.rng import RngFactory
    from tst.sim.state import CompanyState, GameState, SaveMeta

    loaded = load_all(Settings().data_dir)
    scenario = loaded.game_data.scenario(scenario_id)
    if scenario is None:
        return
    # A minimal state: the cap table only needs the company, the founder's id and counters.
    state = GameState(
        save_meta=SaveMeta(name="", master_seed=seed, scenario_id=scenario_id, difficulty=""),
        turn=turn,
        companies=(CompanyState(id=int(player), name="", is_player=True, stage=0, founded_turn=0),),
        next_ids=NextIds(person=next_person),
    )
    state = initial_cap_table(
        state,
        int(player),
        int(founder),
        scenario,
        RngFactory(seed),
        loaded.balance,
        loaded.game_data,
    )
    # Pre-M4 equity in bp becomes options from the pool (14.2).
    staff = conn.execute(
        sa.text(
            "SELECT id, person_id, equity_bp, start_turn, status FROM employment "
            "WHERE company_id = :c AND equity_bp > 0 ORDER BY id"
        ),
        {"c": player},
    ).all()
    grants: list[OptionGrant] = []
    for i, (emp_id, person_id, bp, start, status) in enumerate(staff, start=1):
        granted = int(bp) * OPTIONS_PER_BP
        vested = vested_shares(granted, turn - int(start), loaded.balance.finance)
        ended = status == "ended"
        grants.append(
            OptionGrant(
                id=i,
                company_id=int(player),
                person_id=int(person_id),
                employment_id=int(emp_id),
                granted=granted,
                start_turn=int(start),
                vested=vested,
                forfeited=granted - vested if ended else 0,
                status="ended" if ended else "active",
            )
        )
    outstanding = sum(g.outstanding for g in grants)

    def insert(row: Any) -> None:
        table = row.__table__
        values = {c.name: getattr(row, c.key) for c in table.columns if hasattr(row, c.key)}
        conn.execute(table.insert().values(**values))

    for person in state.people:  # generated directors
        for row in person_to_rows(person):
            insert(row)
    for entry in state.cap_entries:
        if entry.holder_kind == "pool":  # the pool shrinks by what the grants hold
            entry = replace(entry, shares=max(entry.shares - outstanding, 0))
        insert(finance_to_row(entry))
    for item in (*state.rounds, *state.seats, *grants):
        insert(finance_to_row(item))

    mrr = conn.execute(
        sa.text("SELECT kpis FROM turn_snapshot WHERE company_id = :c ORDER BY turn DESC LIMIT :n"),
        {"c": player, "n": MRR_MONTHS},
    ).all()
    history = [
        int((json.loads(k) if isinstance(k, str) else k).get("mrr_cents", 0)) for (k,) in mrr
    ]
    conn.execute(
        sa.text("UPDATE company SET mrr_history = :h WHERE id = :c"),
        {"h": json.dumps(list(reversed(history))), "c": player},
    )
    ids = state.next_ids
    conn.execute(
        sa.text(
            "UPDATE save_meta SET next_person_id = :person, next_cap_entry_id = :cap, "
            "next_grant_id = :grant, next_round_id = :round, next_seat_id = :seat"
        ),
        {
            "person": ids.person,
            "cap": ids.cap_entry,
            "grant": len(grants) + 1,
            "round": ids.round,
            "seat": ids.seat,
        },
    )


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 8")
    for table in (
        "board_seat",
        "term_sheet",
        "funding_round",
        "safe",
        "option_grant",
        "cap_table_entry",
    ):
        op.drop_table(table)
    # Generated directors are people with no employment; they stay (harmless) on downgrade.
    for name in ("cap_entry", "grant", "safe", "round", "term_sheet", "seat"):
        op.drop_column("save_meta", f"next_{name}_id")
    for table, column in (
        ("save_meta", "ended_turn"),
        ("save_meta", "game_state"),
        ("company", "insolvent_months"),
        ("company", "mrr_history"),
    ):
        op.drop_column(table, column)
