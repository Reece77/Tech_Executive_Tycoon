"""The monthly turn pipeline (ADR-0006 order, ADR-0012 signature).

Every phase is a pure function `TurnContext -> TurnContext`. Phases not yet implemented are
no-ops so the order never changes. Inside a turn, cash comes from the starting balances plus
entries posted earlier in the same turn, never from the database.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Final

from tst.sim.actions import Action
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.decisions import Decisions
from tst.sim.errors import GameOverError
from tst.sim.finance import fundraising, insolvency
from tst.sim.finance.board import board_month
from tst.sim.finance.options import settle_leavers, vest
from tst.sim.hiring import phases
from tst.sim.ledger import (
    CASH,
    AccountCode,
    LedgerBalances,
    LedgerEntry,
    account_balance,
    apply_entries,
)
from tst.sim.log import LogItem
from tst.sim.money import Cents
from tst.sim.org.delegates import run_delegates
from tst.sim.org.rules import manager_terms, org_view
from tst.sim.org.upkeep import detach_departed
from tst.sim.people.growth import grow_person
from tst.sim.products import phases as products
from tst.sim.products.models import ProductMonth
from tst.sim.rng import RngFactory
from tst.sim.snapshot import CompanySnapshot, TurnSnapshot
from tst.sim.state import GameState, with_company


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
    # Phase 2's delegate actions as (company id, action), in the order taken (ADR-0015).
    delegate_actions: tuple[tuple[int, Action], ...] = ()
    product_months: tuple[ProductMonth, ...] = ()  # month-end history per product and segment


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
    delegate_actions: tuple[tuple[int, Action], ...] = ()  # phase 2
    revenue: Mapping[int, Cents] = field(default_factory=dict)  # MRR per company, phase 5
    flows: Mapping[products.FlowKey, products.Flow] = field(default_factory=dict)  # phase 5
    product_months: tuple[ProductMonth, ...] = ()  # phase 11

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
    state = settle_leavers(state)  # leavers' unvested options return to the pool (14.2)
    state, detached = detach_departed(state, ctx.data)
    state, entries, resolved = phases.resolve_offers(state, ctx.rng, ctx.balance, ctx.data)
    state, closing, closed = fundraising.close_rounds(state, ctx.rng, ctx.balance, ctx.data)
    ctx = replace(ctx, state=state).post(*entries, *closing)
    return ctx.log(*ended, *detached, *resolved, *closed)


def rival_decisions(ctx: TurnContext) -> TurnContext:
    """Phase 2: delegates work their hiring plans (ADR-0015); rivals join in M5."""
    state, entries, logs, taken = run_delegates(
        ctx.state, ctx.rng, ctx.balance, ctx.data, ctx.balances
    )
    return replace(ctx, state=state, delegate_actions=taken).post(*entries).log(*logs)


def research_progress(ctx: TurnContext) -> TurnContext:
    """Product development: quality and features (formulas.md 11.4, ADR-0017). The v2
    technology tree joins this phase later."""
    state, logs = products.develop(ctx.state, ctx.rng, ctx.balance, ctx.data)
    return replace(ctx, state=state).log(*logs)


def production_and_capacity(ctx: TurnContext) -> TurnContext:  # v2
    return ctx


def sales_revenue_churn(ctx: TurnContext) -> TurnContext:
    """Appeal, churn, customers won, and revenue for every market segment (11.6-11.8)."""
    out = products.run_markets(ctx.state, ctx.rng, ctx.balance, ctx.data)
    ctx = replace(ctx, state=out.state, revenue=out.revenue, flows=out.flows)
    return ctx.post(*out.entries).log(*out.logs)


def payroll_and_operating_costs(ctx: TurnContext) -> TurnContext:
    """Salaries, benefits, office, base overhead, job-post fees, hosting and marketing
    (formulas.md sections 8 and 11.8)."""
    entries, payroll = phases.payroll(ctx.state, ctx.balance, ctx.data)
    return replace(ctx, payroll=payroll).post(*entries)


def financing(ctx: TurnContext) -> TurnContext:
    """Phase 7 (M4): SAFEs are answered, a new round's term sheets arrive, unaccepted rounds
    lapse (14.4, 14.5), options vest for the month just ending (14.2), accepted bridges post,
    and cash below zero is insolvency, possibly a bridge offer, or bankruptcy (14.7)."""
    state, entries, answered = fundraising.answer_safes(ctx.state, ctx.rng, ctx.balance, ctx.data)
    state, sheets = fundraising.deliver_term_sheets(state, ctx.rng, ctx.balance, ctx.data)
    state, lapsed = fundraising.lapse_rounds(state)
    state, bridging, bridges = insolvency.post_bridges(state, ctx.balance)
    state = vest(state, ctx.balance)
    ctx = replace(ctx, state=state).post(*entries, *bridging)
    state, insolvent = insolvency.insolvency(
        ctx.state, ctx.opening_balances, ctx.balances, ctx.balance, ctx.data
    )
    return replace(ctx, state=state).log(*answered, *sheets, *lapsed, *bridges, *insolvent)


def people_updates(ctx: TurnContext) -> TurnContext:
    """Growth and aging for everyone on staff (formulas.md section 3), by person id, with
    each manager's mentoring multiplier (13.5) from the reporting lines at the phase start.

    Then morale, resignations and retirements, monthly tag reveals, and employed_month
    narrowing (formulas.md sections 4, 9, 10). Relationships arrive later.
    """
    mentoring: dict[int, float] = {}
    for company in ctx.state.companies:
        view = org_view(ctx.state, company.id)
        for person_id in view.unit_of:
            mentoring[person_id] = manager_terms(ctx.state, view, person_id, ctx.balance).growth
    people = tuple(
        grow_person(p, ctx.turn, ctx.rng, ctx.data, ctx.balance, mentoring[p.id])
        if p.id in mentoring
        else p
        for p in sorted(ctx.state.people, key=lambda p: p.id)
    )
    state = replace(ctx.state, people=people)
    state, departures = phases.morale_and_departures(
        state, ctx.rng, ctx.balance, ctx.data, ctx.opening_balances, ctx.balances
    )
    state, reveals = phases.monthly_tag_reveals(state, ctx.rng, ctx.balance, ctx.data)
    state = phases.employed_month(state, ctx.balance, ctx.data)
    return replace(ctx, state=state).log(*departures, *reveals)


def market_and_macro_update(ctx: TurnContext) -> TurnContext:
    """Brand toward its marketing target and addressable demand growth (11.1, 11.5); the
    macro layer joins later."""
    return replace(ctx, state=products.brand_and_demand(ctx.state, ctx.balance, ctx.data))


def stage_checks(ctx: TurnContext) -> TurnContext:
    """Stage 0 -> 1 on the first hire (formulas.md section 7); stages 2 and 3 from ARR (11.11);
    the board's monthly confidence, meetings and removal vote (14.6)."""
    state = phases.first_hire_stage(ctx.state)
    state, logs = products.arr_stages(state, ctx.revenue, ctx.balance)
    state, funded = insolvency.funding_stages(state, ctx.balance)  # M4 (14.8)
    logs = (*logs, *funded)
    cash = {c.id: account_balance(ctx.balances, c.id, CASH) for c in state.ledger_companies()}
    state, board = board_month(state, cash, ctx.balance, ctx.data)  # M4 (14.6)
    return replace(ctx, state=state).log(*logs, *board)


def snapshot_and_month_end_report(ctx: TurnContext) -> TurnContext:
    snaps = []
    items = []
    for company in ctx.state.ledger_companies():  # incumbents have no books until M5
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
                mrr_cents=ctx.revenue.get(company.id, 0),
                arr_cents=products.arr_of(ctx.revenue.get(company.id, 0)),
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
    # MRR at each month end feeds investors' growth and the board (M4, 14.3).
    state = ctx.state
    keep = 2 * ctx.balance.finance.growth_window_months + 1
    for company in state.ledger_companies():
        history = (*company.mrr_history, ctx.revenue.get(company.id, 0))[-keep:]
        state = with_company(state, replace(company, mrr_history=history))
    ctx = replace(
        ctx,
        state=state,
        snapshot=TurnSnapshot(turn=ctx.turn, companies=tuple(snaps)),
        product_months=products.month_history(ctx.state, ctx.flows, ctx.data),
    )
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
    if state.ended:
        raise GameOverError(f"the game is over ({state.save_meta.game_state.replace('_', ' ')})")
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
    # Founder and delegate energy reset for the new month after phase 12 (ADR-0014).
    final = phases.reset_energy(ctx.state, balance)
    return TurnResult(
        new_state=replace(final, turn=state.turn + 1),
        ledger_entries=ctx.entries,
        log_items=ctx.log_items,
        snapshot=ctx.snapshot,
        event_requests=ctx.event_requests,
        delegate_actions=ctx.delegate_actions,
        product_months=ctx.product_months,
    )
