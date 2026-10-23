"""The monthly turn pipeline (ADR-0006 order, ADR-0012 signature).

Every phase is a pure function `TurnContext -> TurnContext`. Phases not yet implemented are
no-ops so the order never changes. Inside a turn, cash comes from the starting balances plus
entries posted earlier in the same turn, never from the database.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Final

from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.decisions import Decisions
from tst.sim.hiring import phases
from tst.sim.ledger import (
    CASH,
    AccountCode,
    LedgerBalances,
    LedgerEntry,
    account_balance,
    apply_entries,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import Cents
from tst.sim.people.growth import grow_person
from tst.sim.rng import RngFactory
from tst.sim.snapshot import CompanySnapshot, TurnSnapshot
from tst.sim.state import GameState


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
    payroll: Mapping[int, Cents] = field(default_factory=dict)  # per company, phase 6

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
    """Notices that end this turn close; pending offers resolve (ADR-0014, formulas.md 7, 10).

    Player actions themselves were applied at once between turns; Decisions stays empty in M1.
    """
    state, ended = phases.end_notices(ctx.state)
    state, entries, resolved = phases.resolve_offers(state, ctx.rng, ctx.balance)
    return replace(ctx, state=state).post(*entries).log(*ended, *resolved)


def rival_decisions(ctx: TurnContext) -> TurnContext:  # M5
    return ctx


def research_progress(ctx: TurnContext) -> TurnContext:  # v2
    return ctx


def production_and_capacity(ctx: TurnContext) -> TurnContext:  # v2
    return ctx


def sales_revenue_churn(ctx: TurnContext) -> TurnContext:  # M3
    return ctx


def payroll_and_operating_costs(ctx: TurnContext) -> TurnContext:
    """Salaries, benefits, office, base overhead and job-post fees (formulas.md section 8)."""
    entries, payroll = phases.payroll(ctx.state, ctx.balance)
    return replace(ctx, payroll=payroll).post(*entries)


def financing(ctx: TurnContext) -> TurnContext:  # M4
    return ctx


def people_updates(ctx: TurnContext) -> TurnContext:
    """Growth and aging for everyone on staff (formulas.md section 3), by person id.

    Then morale, resignations and retirements, monthly tag reveals, and employed_month
    narrowing (formulas.md sections 4, 9, 10). Relationships arrive later.
    """
    staff_ids = {e.person_id for e in ctx.state.employments if e.counts_as_staff}
    people = tuple(
        grow_person(p, ctx.turn, ctx.rng, ctx.data, ctx.balance) if p.id in staff_ids else p
        for p in sorted(ctx.state.people, key=lambda p: p.id)
    )
    state = replace(ctx.state, people=people)
    state, departures = phases.morale_and_departures(
        state, ctx.rng, ctx.balance, ctx.data, ctx.opening_balances, ctx.balances
    )
    state, reveals = phases.monthly_tag_reveals(state, ctx.rng, ctx.balance, ctx.data)
    state = phases.employed_month(state, ctx.balance, ctx.data)
    return replace(ctx, state=state).log(*departures, *reveals)


def market_and_macro_update(ctx: TurnContext) -> TurnContext:  # M3
    return ctx


def stage_checks(ctx: TurnContext) -> TurnContext:
    """Stage 0 -> 1 on the first hire (formulas.md section 7)."""
    return replace(ctx, state=phases.first_hire_stage(ctx.state))


def snapshot_and_month_end_report(ctx: TurnContext) -> TurnContext:
    snaps = []
    items = []
    for company in sorted(ctx.state.companies, key=lambda c: c.id):
        opening = account_balance(ctx.opening_balances, company.id, CASH)
        closing = account_balance(ctx.balances, company.id, CASH)
        morale = [
            ctx.state.person_state(e.person_id).morale
            for e in ctx.state.staff(company.id)
            if not ctx.state.person(e.person_id).is_founder
        ]
        known = [m for m in morale if m is not None]
        snaps.append(
            CompanySnapshot(
                company_id=company.id,
                cash_cents=closing,
                monthly_burn_cents=max(opening - closing, 0),
                headcount=len(ctx.state.staff(company.id)),
                payroll_cents=ctx.payroll.get(company.id, 0),
                avg_morale=sum(known) / len(known) if known else None,
            )
        )
        if closing < 0:  # M1 has no insolvency: warn every month cash is negative
            items.append(inbox_item(ctx.turn, company.id, "out_of_cash", cash_cents=closing))
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


def event_director_requests(ctx: TurnContext) -> TurnContext:
    """Phase 12: candidates expire, open searches deliver next month's batches.

    Event requests for the next turn join this phase in M6 (always empty until then).
    """
    state = phases.expire_candidates(ctx.state)
    state, arrivals = phases.candidate_batches(state, ctx.rng, ctx.balance, ctx.data)
    return replace(ctx, state=state).log(*arrivals)


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
    # Founder energy resets for the new month after phase 12 (ADR-0014).
    final = phases.reset_energy(ctx.state, balance)
    return TurnResult(
        new_state=replace(final, turn=state.turn + 1),
        ledger_entries=ctx.entries,
        log_items=ctx.log_items,
        snapshot=ctx.snapshot,
        event_requests=ctx.event_requests,
    )
