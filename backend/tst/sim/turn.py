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
from tst.sim.data_models import AccountType, Balance, GameData
from tst.sim.decisions import Decisions
from tst.sim.errors import CriticalEventOpenError, GameOverError
from tst.sim.events.director import direct
from tst.sim.events.effects import auto_resolve, energy_next_month
from tst.sim.events.models import EventRequest, TextRequest
from tst.sim.finance import debt, fundraising, insolvency, macro
from tst.sim.finance.board import average_confidence, board_month, vacate_departed
from tst.sim.finance.captable import founder_bp
from tst.sim.finance.options import settle_leavers, vest
from tst.sim.finance.statements import cash_before_financing, profit_and_loss
from tst.sim.geo.cities import settle_home_cities
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
from tst.sim.org.divisions import division_months
from tst.sim.org.relationships import relationships_month
from tst.sim.org.rules import manager_terms, org_view
from tst.sim.org.upkeep import detach_departed
from tst.sim.people.growth import grow_person
from tst.sim.products import phases as products
from tst.sim.products.models import ProductMonth
from tst.sim.rivals.decisions import apply_effects, market_news, remember_shares, rival_month
from tst.sim.rivals.models import RivalMove
from tst.sim.rivals.poaching import answer_approaches, join_rivals
from tst.sim.rivals.startups import (
    found_entrants,
    found_startups,
    launch_ready,
    record_failures,
)
from tst.sim.rng import RngFactory
from tst.sim.snapshot import CompanySnapshot, DivisionMonth, TurnSnapshot
from tst.sim.state import GameState, with_company, with_person_state


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
    rival_moves: tuple[RivalMove, ...] = ()  # phase 2 (and startup events, phase 9), M5
    text_requests: tuple[TextRequest, ...] = ()  # read-only LLM text, phase 12 (M6, 16.8)
    division_months: tuple[DivisionMonth, ...] = ()  # headcount per division, phase 6 (M8)


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
    rival_moves: tuple[RivalMove, ...] = ()  # M5: phase 2 decisions and phase 9 startup events
    start: GameState | None = None  # the state the turn began from (M6 milestones)
    text_requests: tuple[TextRequest, ...] = ()
    division_months: tuple[DivisionMonth, ...] = ()  # phase 6 (M8, 18.1)
    # Cash from operating and investing the month already moved before Continue (actions such
    # as a paid event), per company: burn covers the whole month (14.1; M8r).
    prior_flow: Mapping[int, Cents] = field(default_factory=dict)

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

BOARD_MEETING = "board_meeting"  # inbox templates that ask for read-only text (16.8)
RESIGNED = "resigned"


# --- Phases, in ADR-0006 order -------------------------------------------------------------


def apply_player_decisions(ctx: TurnContext) -> TurnContext:
    """Notices that end this turn close; pending offers resolve (ADR-0014, formulas.md 7, 10).

    Player actions themselves were applied at once between turns; Decisions stays empty in M1.
    The month's unanswered minor and major events resolve to their first choice first (M6).
    The macro indicators for the month come first of all (M10, 20.1).
    """
    ctx = replace(ctx, state=macro.macro_phase(ctx.state, ctx.rng, ctx.balance, ctx.data))
    state, event_entries, event_logs = auto_resolve(ctx.state, ctx.balance, ctx.data)
    ctx = replace(ctx, state=state).post(*event_entries).log(*event_logs)
    state, ended = phases.end_notices(ctx.state)
    state = join_rivals(state)  # people who took a rival's offer join it (M5, 15.6)
    state, answered = answer_approaches(state, ctx.rng, ctx.balance)  # M5 (15.6)
    state = settle_leavers(state)  # leavers' unvested options return to the pool (14.2)
    state, detached = detach_departed(state, ctx.data)
    state, vacated = vacate_departed(state)  # a departed nominee's seat empties (14.6, M4c)
    state, entries, resolved = phases.resolve_offers(state, ctx.rng, ctx.balance, ctx.data)
    state, closing, closed = fundraising.close_rounds(state, ctx.rng, ctx.balance, ctx.data)
    state = settle_home_cities(state, state.player.id, ctx.balance, ctx.data)  # M9 (19.2)
    ctx = replace(ctx, state=state).post(*entries, *closing)
    return ctx.log(*ended, *answered, *detached, *vacated, *resolved, *closed)


def rival_decisions(ctx: TurnContext) -> TurnContext:
    """Phase 2: delegates work their hiring plans (ADR-0015); then each rival takes at most
    one action (formulas.md 15.3), and the month's moves become Market news (15.5)."""
    state, entries, logs, taken = run_delegates(
        ctx.state, ctx.rng, ctx.balance, ctx.data, ctx.balances
    )
    ctx = replace(ctx, state=state, delegate_actions=taken).post(*entries).log(*logs)
    state, moves, approached, raised = rival_month(
        ctx.state, ctx.rng, ctx.balances, ctx.balance, ctx.data
    )
    ctx = replace(ctx, state=state, rival_moves=ctx.rival_moves + moves).post(*raised)
    return ctx.log(*approached)


def research_progress(ctx: TurnContext) -> TurnContext:
    """Product development: quality and features (formulas.md 11.4, ADR-0017). The v2
    technology tree joins this phase later."""
    state, logs = products.develop(ctx.state, ctx.rng, ctx.balance, ctx.data)
    state = apply_effects(state, ctx.balance, ctx.data)  # rival pushes and drags (M5, 15.2)
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
    months = division_months(ctx.state)  # headcounts for the division statements (M8)
    return replace(ctx, payroll=payroll, division_months=months).post(*entries)


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
    # M10 (20.3): loans' interest and principal, then covenants, before insolvency.
    state, debt_entries, debt_logs = debt.debt_month(ctx.state, ctx.balances, ctx.balance, ctx.data)
    ctx = replace(ctx, state=state).post(*debt_entries).log(*debt_logs)
    state, insolvent = insolvency.insolvency(ctx.state, ctx.balances, ctx.balance, ctx.data)
    state, failed = record_failures(state, insolvent)  # rivals that closed (M5, 15.1)
    ctx = replace(ctx, rival_moves=ctx.rival_moves + failed)
    return replace(ctx, state=state).log(*answered, *sheets, *lapsed, *bridges, *insolvent)


def people_updates(ctx: TurnContext) -> TurnContext:
    """Growth and aging for everyone on staff (formulas.md section 3), by person id, with
    each manager's mentoring multiplier (13.5) from the reporting lines at the phase start.

    Then morale, resignations and retirements, monthly tag reveals, and employed_month
    narrowing (formulas.md sections 4, 9, 10). Relationships move first, so morale reads this
    month's W_rel (16.7).
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
    state = relationships_month(state, ctx.balance)  # before morale, which reads W_rel (M6)
    state, departures = phases.morale_and_departures(
        state, ctx.rng, ctx.balance, ctx.data, ctx.opening_balances, ctx.balances
    )
    state, reveals = phases.monthly_tag_reveals(state, ctx.rng, ctx.balance, ctx.data)
    state = phases.employed_month(state, ctx.balance, ctx.data)
    return replace(ctx, state=state).log(*departures, *reveals)


def market_and_macro_update(ctx: TurnContext) -> TurnContext:
    """Brand toward its marketing target and addressable demand growth (11.1, 11.5); the
    macro layer joins later."""
    state = products.brand_and_demand(ctx.state, ctx.balance, ctx.data)
    going_live = products.regions_going_live(state, ctx.data)  # M9 (19.5)
    state, launched = launch_ready(state, ctx.balance, ctx.data)  # rival startups (M5, 15.4)
    state, arriving, arrived = found_entrants(state, ctx.rng, ctx.balance, ctx.data)  # M8 (18.7)
    state, founding, founded = found_startups(state, ctx.rng, ctx.balance, ctx.data)
    moves = ctx.rival_moves + launched + arrived + founded
    ctx = replace(ctx, state=state, rival_moves=moves).post(*arriving, *founding)
    return ctx.log(*going_live)


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
    types = {a.code: a.type for a in ctx.data.accounts}
    for company in ctx.state.ledger_companies():  # incumbents have no books until M5
        closing = account_balance(ctx.balances, company.id, CASH)
        # Burn: net cash used before financing over the month (14.1; M8r finding 7).
        lines = [
            (e.turn, line.account, line.amount)
            for e in ctx.entries
            if e.company_id == company.id
            for line in e.lines
        ]
        flow = ctx.prior_flow.get(company.id, 0) + cash_before_financing(lines, types)
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
                monthly_burn_cents=max(-flow, 0),
                headcount=len(ctx.state.staff(company.id)),
                payroll_cents=ctx.payroll.get(company.id, 0),
                avg_morale=sum(known) / len(known) if known else None,
                mrr_cents=ctx.revenue.get(company.id, 0),
                arr_cents=products.arr_of(ctx.revenue.get(company.id, 0)),
                founder_bp=founder_bp(ctx.state, company.id),
                board_confidence=average_confidence(ctx.state, company.id),
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
    state = remember_shares(ctx.state, ctx.balance)  # rivals' share memory (M5, 15.3)
    keep = 2 * ctx.balance.finance.growth_window_months + 1
    for company in state.ledger_companies():
        history = (*company.mrr_history, ctx.revenue.get(company.id, 0))[-keep:]
        state = with_company(state, replace(company, mrr_history=history))
    state = _debt_history(state, ctx, types)  # M10 (20.3): covenants read completed months
    ctx = replace(
        ctx,
        state=state,
        snapshot=TurnSnapshot(turn=ctx.turn, companies=tuple(snaps)),
        product_months=products.month_history(ctx.state, ctx.flows, ctx.data, ctx.balance),
    )
    return ctx.log(*items, *market_news(state, ctx.rival_moves))  # M5 (15.5)


def _debt_history(
    state: GameState, ctx: TurnContext, types: Mapping[str, AccountType]
) -> GameState:
    """The player's operating result and burn for the month just ended (M10, 20.3): the
    turn's entries plus what actions moved before Continue (all operating in practice)."""
    company = state.player
    lines = [
        (e.turn, line.account, line.amount)
        for e in ctx.entries
        if e.company_id == company.id
        for line in e.lines
    ]
    prior = ctx.prior_flow.get(company.id, 0)
    result = profit_and_loss(lines, types, ctx.turn, ctx.turn).operating_result + prior
    burn = max(-(prior + cash_before_financing(lines, types)), 0)
    keep = ctx.balance.debt.bank.profit_months + ctx.balance.debt.bank.covenant_profit_months
    company = replace(
        company,
        op_history=(*company.op_history, result)[-keep:],
        burn_history=(*company.burn_history, burn)[-keep:],
    )
    return with_company(state, company)


def event_director_requests(ctx: TurnContext) -> TurnContext:
    """Phase 12: candidates expire, open searches deliver next month's batches, and the
    event director queues next month's events (16.1) and the month's read-only texts (16.8)."""
    state = phases.expire_candidates(ctx.state)
    state, arrivals = phases.candidate_batches(state, ctx.rng, ctx.balance, ctx.data)
    player = state.player.id
    state, requests = direct(
        state,
        ctx.start or ctx.state,
        ctx.rng,
        ctx.balance,
        ctx.data,
        account_balance(ctx.balances, player, CASH),
        ctx.revenue.get(player, 0),
        ctx.rival_moves,
    )
    texts = text_requests(ctx.log_items, player, ctx.turn)
    ctx = replace(ctx, state=state, event_requests=requests, text_requests=texts)
    return ctx.log(*arrivals)


def text_requests(logs: tuple[LogItem, ...], player: int, turn: int) -> tuple[TextRequest, ...]:
    """16.8: headlines every month; minutes after a quarterly board meeting; an exit line
    for each resignation, all for the player."""
    out = [TextRequest("headlines", player, turn)]
    mine = [i for i in logs if i.company_id == player]
    if any(i.template == BOARD_MEETING for i in mine):
        out.append(TextRequest("minutes", player, turn))
    out += [
        TextRequest("exit_line", player, turn, i.link_id)
        for i in mine
        if i.template == RESIGNED and i.link_id is not None
    ]
    return tuple(out)


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
    *,
    prior_flow: Mapping[int, Cents] | None = None,
) -> TurnResult:
    """Resolve turn `state.turn` and return the next state plus everything to persist.
    `prior_flow`: cash from operating and investing that this month's actions already moved,
    per company (from the ledger), so the stored burn covers the whole month (14.1; M8r)."""
    if state.ended:
        raise GameOverError(f"the game is over ({state.save_meta.game_state.replace('_', ' ')})")
    for event in state.open_events(state.player.id):
        if event.severity == "critical" and event.status == "open":
            raise CriticalEventOpenError(
                f"answer the critical event {event.title or event.template_id!r} first", event.id
            )
    ctx = TurnContext(
        state=state,
        decisions=decisions,
        rng=rng,
        balance=balance,
        data=data,
        opening_balances=ledger_balances,
        balances=dict(ledger_balances),
        start=state,
        prior_flow=prior_flow or {},
    )
    for _name, phase in PHASES:
        ctx = phase(ctx)
    if ctx.snapshot is None:
        raise RuntimeError("snapshot phase did not run")
    # Founder and delegate energy reset for the new month after phase 12 (ADR-0014).
    final = phases.reset_energy(ctx.state, balance, data)
    founder = final.founder_of(final.player.id)
    bonus = energy_next_month(ctx.state, founder.id) if founder else 0
    if founder is not None and bonus:  # events' energy_delta, next month (16.3)
        ps = final.person_state(founder.id)
        final = with_person_state(final, replace(ps, energy=max(0, (ps.energy or 0) + bonus)))
    return TurnResult(
        new_state=replace(final, turn=state.turn + 1),
        ledger_entries=ctx.entries,
        log_items=ctx.log_items,
        snapshot=ctx.snapshot,
        event_requests=ctx.event_requests,
        delegate_actions=ctx.delegate_actions,
        product_months=ctx.product_months,
        rival_moves=ctx.rival_moves,
        text_requests=ctx.text_requests,
        division_months=ctx.division_months,
    )
