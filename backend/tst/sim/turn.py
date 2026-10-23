"""The monthly turn pipeline (ADR-0006 order, ADR-0012 signature).

Every phase is a pure function `TurnContext -> TurnContext`. Phases not yet implemented are
no-ops so the order never changes. Inside a turn, cash comes from the starting balances plus
entries posted earlier in the same turn, never from the database.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Final

from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.decisions import Decisions
from tst.sim.ledger import (
    CASH,
    GENERAL_ADMIN,
    AccountCode,
    LedgerBalances,
    LedgerEntry,
    account_balance,
    apply_entries,
)
from tst.sim.money import Cents
from tst.sim.people.growth import grow_person
from tst.sim.rng import RngFactory
from tst.sim.snapshot import CompanySnapshot, TurnSnapshot
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class LogItem:
    turn: int
    company_id: int | None
    kind: str
    message: str


@dataclass(frozen=True, slots=True)
class EventRequest:
    """Request for the event director. Empty until M6 (ADR-0012)."""


@dataclass(frozen=True, slots=True)
class TurnResult:
    new_state: GameState
    ledger_entries: tuple[LedgerEntry, ...]
    log_items: tuple[LogItem, ...]
    snapshot: TurnSnapshot
    event_requests: tuple[EventRequest, ...]


@dataclass(frozen=True, slots=True)
class TurnContext:
    state: GameState
    decisions: Decisions
    rng: RngFactory
    balance: Balance
    data: GameData
    opening_balances: LedgerBalances
    balances: Mapping[tuple[int, AccountCode], Cents]  # running: opening + entries so far
    entries: tuple[LedgerEntry, ...] = ()
    log_items: tuple[LogItem, ...] = ()
    snapshot: TurnSnapshot | None = None
    event_requests: tuple[EventRequest, ...] = ()

    @property
    def turn(self) -> int:
        return self.state.turn

    def post(self, *entries: LedgerEntry) -> TurnContext:
        return replace(
            self,
            entries=self.entries + entries,
            balances=apply_entries(self.balances, entries),
        )

    def log(self, *items: LogItem) -> TurnContext:
        return replace(self, log_items=self.log_items + items)


type Phase = Callable[[TurnContext], TurnContext]


# --- Phases, in ADR-0006 order -------------------------------------------------------------


def apply_player_decisions(ctx: TurnContext) -> TurnContext:
    return ctx


def rival_decisions(ctx: TurnContext) -> TurnContext:  # M5
    return ctx


def research_progress(ctx: TurnContext) -> TurnContext:  # v2
    return ctx


def production_and_capacity(ctx: TurnContext) -> TurnContext:  # v2
    return ctx


def sales_revenue_churn(ctx: TurnContext) -> TurnContext:  # M3
    return ctx


def payroll_and_operating_costs(ctx: TurnContext) -> TurnContext:
    """M0: post the placeholder base overhead for every company."""
    cost = ctx.balance.company.base_monthly_cost_cents
    if cost == 0:
        return ctx
    entries = tuple(
        LedgerEntry.transfer(
            turn=ctx.turn,
            company_id=company.id,
            memo="Base overhead",
            debit=GENERAL_ADMIN,
            credit=CASH,
            amount=cost,
        )
        for company in sorted(ctx.state.companies, key=lambda c: c.id)
    )
    return ctx.post(*entries)


def financing(ctx: TurnContext) -> TurnContext:  # M4
    return ctx


def people_updates(ctx: TurnContext) -> TurnContext:
    """Growth and aging for everyone on staff (formulas.md section 3), by person id.

    Morale, stress, relationships and resignations join this phase in M1b.
    """
    staff_ids = {e.person_id for e in ctx.state.employments if e.counts_as_staff}
    people = tuple(
        grow_person(p, ctx.turn, ctx.rng, ctx.data, ctx.balance) if p.id in staff_ids else p
        for p in sorted(ctx.state.people, key=lambda p: p.id)
    )
    return replace(ctx, state=replace(ctx.state, people=people))


def market_and_macro_update(ctx: TurnContext) -> TurnContext:  # M3
    return ctx


def stage_checks(ctx: TurnContext) -> TurnContext:
    return ctx


def snapshot_and_month_end_report(ctx: TurnContext) -> TurnContext:
    snaps = []
    items = []
    for company in sorted(ctx.state.companies, key=lambda c: c.id):
        opening = account_balance(ctx.opening_balances, company.id, CASH)
        closing = account_balance(ctx.balances, company.id, CASH)
        snaps.append(
            CompanySnapshot(
                company_id=company.id,
                cash_cents=closing,
                monthly_burn_cents=max(opening - closing, 0),
                headcount=len(ctx.state.staff(company.id)),
            )
        )
        items.append(
            LogItem(
                turn=ctx.turn,
                company_id=company.id,
                kind="month_end",
                message=f"{format_turn(ctx.turn)} closed for {company.name}",
            )
        )
    ctx = replace(ctx, snapshot=TurnSnapshot(turn=ctx.turn, companies=tuple(snaps)))
    return ctx.log(*items)


def event_director_requests(ctx: TurnContext) -> TurnContext:  # M6
    return ctx


PHASES: Final[tuple[tuple[str, Phase], ...]] = (
    ("apply_player_decisions", apply_player_decisions),
    ("rival_decisions", rival_decisions),
    ("research_progress", research_progress),
    ("production_and_capacity", production_and_capacity),
    ("sales_revenue_churn", sales_revenue_churn),
    ("payroll_and_operating_costs", payroll_and_operating_costs),
    ("financing", financing),
    ("people_updates", people_updates),
    ("market_and_macro_update", market_and_macro_update),
    ("stage_checks", stage_checks),
    ("snapshot_and_month_end_report", snapshot_and_month_end_report),
    ("event_director_requests", event_director_requests),
)


def advance_turn(
    state: GameState,
    decisions: Decisions,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    ledger_balances: LedgerBalances,
) -> TurnResult:
    """Resolve turn `state.turn` and return the next state plus everything to persist."""
    ctx = TurnContext(
        state=state,
        decisions=decisions,
        rng=rng,
        balance=balance,
        data=data,
        opening_balances=ledger_balances,
        balances=dict(ledger_balances),
    )
    for _name, phase in PHASES:
        ctx = phase(ctx)
    if ctx.snapshot is None:
        raise RuntimeError("snapshot phase did not run")
    return TurnResult(
        new_state=replace(ctx.state, turn=state.turn + 1),
        ledger_entries=ctx.entries,
        log_items=ctx.log_items,
        snapshot=ctx.snapshot,
        event_requests=ctx.event_requests,
    )
