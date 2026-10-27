"""M4a funding diagnostics (printed, no thresholds; the brief's sub-task 10), on 10 seeds:

(a) the M3a earn-and-burn script in funded_spinout with no fundraising, 36 turns;
(b) the same script hiring to 15 staff by turn 12, no fundraising: the bankruptcy turn;
(c) as (b), raising a Series A at the best term sheet as soon as ARR allows: the turn,
    pre-money, amount, founder ownership after, and survival to turn 60.

Run with `-s` to see the table; the brief's Decisions made records it. Nothing is tuned to it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from tests.balance_scripts import (
    BUILDER_SKILL,
    EARN_AND_BURN_PRICES,
    FOUNDER,
    MARKETING_CENTS,
    Run,
    hire,
    start,
)
from tst.loader import LoadedData
from tst.sim.actions import (
    AcceptTermSheet,
    AssignUnit,
    CreateProduct,
    LaunchProduct,
    SetMarketing,
    SetPrice,
    StartRound,
)
from tst.sim.actions.products import launch_problems
from tst.sim.errors import GameOverError
from tst.sim.finance.captable import founder_bp, open_round
from tst.sim.finance.fundraising import series_problem

SEEDS = range(1, 11)
EXTRA_ROLES = ("software_engineer", "account_executive", "marketer")  # cycled to 15 staff
HIRE_TO = 15
HIRE_BY = 12
SERIES_A_TARGET = 600_000_000  # $6M


@dataclass
class Outcome:
    bankrupt_turn: int | None = None
    a_turn: int | None = None
    a_pre_cents: int | None = None
    a_amount_cents: int | None = None
    founder_after_bp: int | None = None
    survived: bool = True


def play(loaded: LoadedData, seed: int, turns: int, grow: bool, raise_a: bool) -> Outcome:
    run: Run = start(loaded, seed)
    for pid in (2, 3, 4):
        hire(run, pid, "software_engineer", BUILDER_SKILL)
    hire(run, 5, "account_executive")
    hire(run, 6, "marketer")
    product = run.state.next_ids.product
    run.act(CreateProduct(FOUNDER, "Pipeline", "b2b_saas", tuple(EARN_AND_BURN_PRICES)))
    for segment, price in EARN_AND_BURN_PRICES.items():
        run.act(SetPrice(FOUNDER, product, segment, price))
    run.act(AssignUnit(FOUNDER, product, None))
    run.act(SetMarketing(FOUNDER, product, MARKETING_CENTS))
    out = Outcome()
    next_pid = 7
    for _ in range(turns):
        state = run.state
        current = state.product(product)
        developing = current is not None and current.status == "in_development"
        if developing and not launch_problems(state, current, loaded.balance, loaded.game_data):
            run.act(LaunchProduct(FOUNDER, product))
        staff = len(state.staff(1))
        if grow and staff < HIRE_TO and 1 <= state.turn <= HIRE_BY:
            per_turn = -(-(HIRE_TO - staff) // max(HIRE_BY - state.turn + 1, 1))
            for _ in range(per_turn):
                hire(run, next_pid, EXTRA_ROLES[next_pid % len(EXTRA_ROLES)])
                next_pid += 1
        if raise_a and out.a_turn is None:
            rnd = open_round(run.state, 1)
            if rnd is None and series_problem(run.state, 1, "a", loaded.balance) is None:
                run.act(StartRound(FOUNDER, "a", SERIES_A_TARGET))
            elif rnd is not None and rnd.status == "open":
                sheets = [t for t in run.state.sheets_of(rnd.id) if t.status == "offered"]
                if sheets:
                    best = max(sheets, key=lambda t: t.pre_money_cents)
                    run.act(AcceptTermSheet(FOUNDER, best.id))
                    out.a_pre_cents, out.a_amount_cents = best.pre_money_cents, best.amount_cents
        try:
            run.turn()
        except GameOverError:
            break
        if run.state.ended:
            out.bankrupt_turn = run.state.save_meta.ended_turn
            out.survived = False
            break
        closed = [r for r in run.state.rounds if r.series == "a" and r.status == "closed"]
        if closed and out.a_turn is None:
            out.a_turn = closed[0].closed_turn
            out.founder_after_bp = founder_bp(run.state, 1)
    return out


def _money(cents: int | None) -> str:
    return "-" if cents is None else f"${cents / 100_000_000:.2f}M"


@pytest.mark.parametrize("seed", SEEDS)
def test_funding_diagnostics(loaded: LoadedData, seed: int) -> None:
    a = play(loaded, seed, 36, grow=False, raise_a=False)
    b = play(loaded, seed, 36, grow=True, raise_a=False)
    c = play(loaded, seed, 60, grow=True, raise_a=True)
    founder = "-" if c.founder_after_bp is None else f"{c.founder_after_bp / 100:.1f}%"
    print(
        f"\nseed {seed:2d} | (a) survives 36: {a.survived} "
        f"| (b) bankrupt turn: {b.bankrupt_turn} "
        f"| (c) Series A turn {c.a_turn}, pre {_money(c.a_pre_cents)}, "
        f"amount {_money(c.a_amount_cents)}, founder after {founder}, survives 60: {c.survived}"
    )
    assert a.bankrupt_turn is None or a.bankrupt_turn > 0  # printed, not judged
