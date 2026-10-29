"""Funding diagnostics on 10 seeds (M4a, printed), with M4c's balance targets (checked):

(a) the M3a earn-and-burn script in funded_spinout with no fundraising: survives to turn 36
    on at least 7 of 10 seeds (staying small and self-funded stays viable);
(b) the same script hiring to 15 staff by turn 12, no fundraising: cash goes below zero
    (insolvent) before turn 36 on at least 7 of 10 seeds (fast growth needs money);
(c) as (b), raising a Series A at the best term sheet as soon as ARR allows: survives to
    turn 60 on at least 8 of 10 seeds.

The table also shows the bridge investors would offer at (b)'s first insolvency against the
deficit then (the M4b follow-up). Run with `-s` to see it; the M4c brief records it.
"""

from __future__ import annotations

from dataclasses import dataclass

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
from tst.sim.finance.insolvency import bridge_amount
from tst.sim.ledger import CASH
from tst.sim.rivals.models import PoachApproach

SEEDS = range(1, 11)
EXTRA_ROLES = ("software_engineer", "account_executive", "marketer")  # cycled to 15 staff
HIRE_TO = 15
HIRE_BY = 12
SERIES_A_TARGET = 600_000_000  # $6M


@dataclass
class Outcome:
    insolvent_turn: int | None = None  # first month end with cash below zero
    bridge_cents: int | None = None  # the bridge offered then (14.7), if any
    deficit_cents: int | None = None  # how far below zero cash was then
    bankrupt_turn: int | None = None
    a_turn: int | None = None
    a_pre_cents: int | None = None
    a_amount_cents: int | None = None
    founder_after_bp: int | None = None
    survived: bool = True
    run: Run | None = None  # kept on request (M5 balance: approaches)
    approaches: tuple[PoachApproach, ...] = ()


def play(
    loaded: LoadedData, seed: int, turns: int, grow: bool, raise_a: bool, keep_run: bool = False
) -> Outcome:
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
        cash = run.balances.get((1, CASH), 0)
        if cash < 0 and out.insolvent_turn is None:
            out.insolvent_turn = run.state.turn - 1
            out.deficit_cents = -cash
            bridge = next((x for x in run.state.company_safes(1) if x.kind == "bridge"), None)
            if bridge is not None:
                out.bridge_cents = bridge_amount(
                    run.state, 1, cash, loaded.balance, loaded.game_data
                )
        if run.state.ended:
            out.bankrupt_turn = run.state.save_meta.ended_turn
            out.survived = False
            break
        closed = [r for r in run.state.rounds if r.series == "a" and r.status == "closed"]
        if closed and out.a_turn is None:
            out.a_turn = closed[0].closed_turn
            out.founder_after_bp = founder_bp(run.state, 1)
    if keep_run:
        out.run = run
        out.approaches = run.state.approaches
    return out


def _money(cents: int | None) -> str:
    return "-" if cents is None else f"${cents / 100_000_000:.2f}M"


def test_funding_balance_targets(loaded: LoadedData) -> None:
    """M4c change 7: fast growth must need outside money; lean stays viable."""
    lean = survived_a = insolvent_b = survived_c = 0
    for seed in SEEDS:
        a = play(loaded, seed, 36, grow=False, raise_a=False)
        b = play(loaded, seed, 36, grow=True, raise_a=False)
        c = play(loaded, seed, 60, grow=True, raise_a=True)
        founder = "-" if c.founder_after_bp is None else f"{c.founder_after_bp / 100:.1f}%"
        print(
            f"\nseed {seed:2d} | (a) survives 36: {a.survived} "
            f"| (b) insolvent turn {b.insolvent_turn}, deficit {_money(b.deficit_cents)}, "
            f"bridge {_money(b.bridge_cents)}, bankrupt turn {b.bankrupt_turn} "
            f"| (c) Series A turn {c.a_turn}, pre {_money(c.a_pre_cents)}, "
            f"amount {_money(c.a_amount_cents)}, founder after {founder}, survives 60: {c.survived}"
        )
        survived_a += a.survived
        insolvent_b += b.insolvent_turn is not None and b.insolvent_turn < 36
        survived_c += c.survived
        lean += 1
    print(
        f"\n(a) {survived_a}/{lean} survive 36 | (b) {insolvent_b}/{lean} insolvent before 36 "
        f"| (c) {survived_c}/{lean} survive 60"
    )
    assert survived_a >= 7, "a lean, self-funded company should usually survive three years"
    assert insolvent_b >= 7, "hiring to 15 by month 12 without raising should run out of cash"
    assert survived_c >= 8, "the same growth with a Series A should usually survive five years"
