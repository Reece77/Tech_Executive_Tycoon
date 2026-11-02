"""Executives with authority act in phase 2 (docs/formulas.md 24.1-24.2, M10c; ADR-0015).

After the hiring delegates, each seat holder with authority runs its seat's rule through the
same actions the player uses, as the actor, with its own energy. Choosing uses only what the
company can see (displayed ranges, the shown team: ADR-0015, ADR-0007); how well the choice is
made comes from the holder's true seat score: the right rule with probability
clamp(0.55 + 0.03 s, 0.6, 0.98), else a plausible but worse option. Draws come from stream
`delegate` keyed (person id, QUALITY_KEY + seat index), apart from the actions' own draws.

Right rule, then mistake, by seat:
- CTO: a builder from a product well above full speed to a live product below its
  maintenance line, else a builder plan for the gap within the headcount cap; mistake: the
  second-best donor, or one hire fewer.
- CRO: a seller plan where capacity limits a sales-led segment, and its price a step up within
  the band; mistake: one hire fewer and no price move.
- CMO: marketing as % of revenue, split by brand gap and size; mistake: off by 20% toward the
  weakest product.
- COO: a support plan below the coverage target, a lease proposal for a crowded office;
  mistake: one hire fewer.
- CFO: a round or loan proposal below the runway threshold, early repayment above the cash
  threshold; mistake: repays 20% less.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import replace
from typing import Final

from tst.sim.actions import (
    Action,
    CreatePlan,
    MovePerson,
    RepayLoan,
    SetMarketing,
    SetPrice,
)
from tst.sim.data_models import SCORE_MAX, Balance, GameData
from tst.sim.finance import debt
from tst.sim.finance.fundraising import next_series, series_problem
from tst.sim.finance.statements import projected_net_burn
from tst.sim.geo.offices import office_members
from tst.sim.ledger import CASH, AccountCode, LedgerEntry, account_balance
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import Cents
from tst.sim.org.delegates import DelegateAction, DelegateRun, delegate_draws
from tst.sim.org.divisions import support_pools
from tst.sim.org.executives import acting_seats, true_score
from tst.sim.org.formulas import decision_quality
from tst.sim.org.models import Authority, ExecDecision, Proposal, ProposalKind
from tst.sim.org.rules import org_view
from tst.sim.products.estimates import shown_team
from tst.sim.products.models import SELLING, Product
from tst.sim.products.phases import builders_to_add, team_of
from tst.sim.products.team import Team
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_exec_decision, with_person_state, with_proposal

QUALITY_KEY = 1_000_000  # tunable-exempt: delegate-stream key offset for quality draws
BUILDER_ROLE = "software_engineer"
SELLER_ROLE = "account_executive"
SUPPORT_ROLE = "operations_manager"
PLAN_CHANNEL: Final = "any"
STEADY_PACE = 0.4  # tunable-exempt: 11.13's "steady" pace, the target for products in development
PCT = 100  # tunable-exempt: percent
BP = 10_000  # tunable-exempt: basis points
CHANGE_TOLERANCE = 0.05  # tunable-exempt: a marketing change below 5% is not worth an action


class _Seat:
    """One executive's month: the runner, the authority, and what to log."""

    def __init__(self, run: DelegateRun, a: Authority, holder: int, right: bool) -> None:
        self.run, self.a, self.holder, self.right = run, a, holder, right
        self.notes: list[tuple[str, bool]] = []

    @property
    def state(self) -> GameState:
        return self.run.state

    def act(self, action: Action, text: str, mistake: bool = False) -> bool:
        if self.run.attempt(self.a.company_id, action):
            self.notes.append((text, mistake))
            return True
        return False


# --- Helpers ---------------------------------------------------------------------------------


def _function_of(state: GameState, person_id: int, data: GameData) -> str:
    person = state.person(person_id)
    if person.is_founder:
        return "builder"
    e = state.employment_of(person_id)
    return data.role(e.role).product_function if e is not None else "none"


def _headcount(state: GameState, company: int, function: str, data: GameData) -> int:
    return sum(
        1
        for e in state.staff(company)
        if not state.person(e.person_id).is_founder
        and data.role(e.role).product_function == function
    )


def _open_need(state: GameState, company: int, roles: set[str]) -> int:
    """People still to come from active plans for these roles (13.10)."""
    need = 0
    for p in state.plans:
        if p.company_id == company and p.status == "active" and p.role in roles:
            pending = sum(1 for o in state.pending_offers(company) if o.plan_id == p.id)
            need += max(0, p.target - p.hired - pending) + pending
    return need


def _has_plan(state: GameState, company: int, role: str, unit_id: int | None) -> bool:
    return any(
        p.company_id == company and p.status == "active" and p.role == role and p.unit_id == unit_id
        for p in state.plans
    )


def _product_unit(state: GameState, product: Product) -> int | None:
    """Where a product's builders work: its first assigned unit, else the company root."""
    units = [u.id for u in state.active_units(product.company_id) if u.product_id == product.id]
    return min(units) if units else None


def _plan(seat: _Seat, role: str, unit: int | None, wanted: int, why: str, data: GameData) -> int:
    """Open a hiring plan for up to `wanted` (24.1), within the seat's headcount cap."""
    a, state = seat.a, seat.state
    company = a.company_id
    function = data.role(role).product_function
    roles = {r.key for r in data.roles if r.product_function == function}
    guards = dict(a.guardrails)
    cap = int(a.number("headcount_cap")) if "headcount_cap" in guards else None
    room = wanted if cap is None else cap - _headcount(state, company, function, data)
    room -= _open_need(state, company, roles) if cap is not None else 0
    hires = min(wanted, seat.run.balance.exec_authority.plan_hires, room)
    mistake = not seat.right
    if mistake:
        hires -= 1  # a slower pace (24.2)
    if hires < 1 or _has_plan(state, company, role, unit):
        return 0
    ratio = min(int(a.number("max_salary_ratio_bp")), seat.run.balance.delegates.max_ratio_bp)
    label = data.role(role).label.lower()
    plan = CreatePlan(seat.holder, seat.holder, role, hires, PLAN_CHANNEL, ratio, 0, unit)
    done = seat.act(
        plan, f"opened a plan for {hires} {label}{'s' if hires > 1 else ''} {why}", mistake
    )
    return hires if done else 0


# --- CTO -------------------------------------------------------------------------------------


def _cto(seat: _Seat, data: GameData) -> None:
    """Live products below their maintenance line first, then products in development below a
    steady pace: move a spare builder over, else hire (24.1)."""
    state, b = seat.state, seat.run.balance
    company = seat.a.company_id
    protected = set(seat.a.guard("protected_units"))  # type: ignore[arg-type]
    view = org_view(state, company)
    products = [
        p for p in state.company_products(company) if p.status in (*SELLING, "in_development")
    ]
    teams: dict[int, Team] = {}
    for p in products:
        team = team_of(state, view, p, b, data)
        teams[p.id] = shown_team(state, company, team, data.category(p.category), b)
    for p in sorted(products, key=lambda p: (p.status == "in_development", p.id)):
        scope = data.category(p.category).scope
        needed = b.products.rot_threshold * scope if p.status in SELLING else STEADY_PACE * scope
        output = teams[p.id].base_output(b)
        if output >= needed:
            continue
        target_unit = _product_unit(seat.state, p)
        if target_unit in protected:
            continue
        donors = []
        for q in products:
            q_scope = data.category(q.category).scope
            spare = teams[q.id].base_output(b) - b.exec_authority.move_margin * q_scope
            if q.id == p.id or spare <= 0:
                continue
            for builder in teams[q.id].builders:
                person = seat.state.person(builder.person_id)
                e = seat.state.employment_of(builder.person_id)
                if person.is_founder or e is None or e.unit_id in protected:
                    continue
                if builder.output <= spare:
                    donors.append((-builder.output, builder.person_id, q.name))
        donors.sort()
        if donors:
            pick = donors[0] if seat.right or len(donors) == 1 else donors[1]  # 24.2
            name = seat.state.person(pick[1])
            if seat.act(
                MovePerson(seat.holder, pick[1], target_unit),
                f"moved {name.first_name} {name.last_name} from {pick[2]} to {p.name}",
                mistake=not seat.right and len(donors) > 1,
            ):
                continue
        add = builders_to_add(output, len(teams[p.id].builders), needed)
        _plan(seat, BUILDER_ROLE, target_unit, max(1, add), f"for {p.name}", data)


# --- CRO -------------------------------------------------------------------------------------


def _cro(seat: _Seat, data: GameData) -> None:
    """Sellers where capacity limits a sales-led segment; that segment's price a step up, within
    the band around the player's price (24.1)."""
    state, b = seat.state, seat.run.balance
    company = seat.a.company_id
    anchors = {(pid, seg): cents for pid, seg, cents in seat.a.price_anchors}
    band = seat.a.number("price_band_pct") / PCT
    step = b.exec_authority.price_step_pct / PCT
    for p in state.company_products(company):
        if p.status not in SELLING:
            continue
        for seg in state.segments_of(p.id):
            if data.segment(seg.segment).reach != "sales" or not seg.capacity_limited:
                continue
            unit = _product_unit(seat.state, p)
            _plan(seat, SELLER_ROLE, unit, b.exec_authority.plan_hires, f"for {p.name}", data)
            anchor = anchors.get((p.id, seg.segment))
            if anchor is None or seg.price_cents is None or not seat.right:
                continue  # a mistake leaves the price where it is (24.2)
            ceiling = round(anchor * (1 + band))
            price = min(ceiling, round(seg.price_cents * (1 + step)))
            if price > seg.price_cents:
                seat.act(
                    SetPrice(seat.holder, p.id, seg.segment, price),
                    f"raised {p.name}'s {data.segment(seg.segment).label} price to "
                    f"${price / PCT:,.0f} while demand outran sales capacity",
                )


# --- CMO -------------------------------------------------------------------------------------


def _cmo(seat: _Seat, data: GameData, revenue: Cents) -> None:
    """Total marketing = % of revenue, split by brand gap x size (24.1)."""
    state = seat.state
    company = seat.a.company_id
    live = [p for p in state.company_products(company) if p.status in SELLING]
    if not live or revenue <= 0:
        return
    total = revenue * seat.a.number("marketing_pct_of_revenue") / PCT
    weights = {
        p.id: max(SCORE_MAX - p.brand, 1.0)
        * math.sqrt(1 + sum(s.customers for s in state.segments_of(p.id)))
        for p in live
    }
    whole = sum(weights.values())
    shares = {pid: w / whole for pid, w in weights.items()}
    if not seat.right and len(live) > 1:  # off by 20% toward the weakest product (24.2)
        best = max(shares, key=lambda k: shares[k])
        worst = min(shares, key=lambda k: shares[k])
        moved = shares[best] * seat.run.balance.exec_authority.mistake_budget_off
        shares[best] -= moved
        shares[worst] += moved
    for p in live:
        cents = round(total * shares[p.id])
        if abs(cents - p.marketing_budget_cents) <= CHANGE_TOLERANCE * max(cents, 1):
            continue
        seat.act(
            SetMarketing(seat.holder, p.id, cents),
            f"set {p.name}'s marketing to ${cents / PCT:,.0f} a month",
            mistake=not seat.right and len(live) > 1,
        )


# --- COO -------------------------------------------------------------------------------------


def _coo(seat: _Seat, data: GameData) -> None:
    """Support plans while coverage is below target; a lease proposal for a crowded office
    (24.1)."""
    state, b = seat.state, seat.run.balance
    company = seat.a.company_id
    pools = support_pools(state, org_view(state, company), b, data)
    target = seat.a.number("coverage_target")
    central = pools.get(None)
    if central is not None and central.coverage < target and central.need > 0:
        short = math.ceil(central.need * target) - central.support
        if short > 0:
            _plan(seat, SUPPORT_ROLE, None, short, "to cover support", data)
    for office_id, people in sorted(office_members(state, company).items()):
        office = state.office(office_id)
        if office is None or len(people) <= office.seats:
            continue
        city = data.city(office.city)
        seats = b.exec_authority.lease_seats
        _propose(
            seat,
            "lease",
            (("city", office.city), ("seats", seats)),
            f"a {seats}-seat lease in {city.label}: the {city.label} office has "
            f"{len(people)} people for {office.seats} seats",
        )


# --- CFO -------------------------------------------------------------------------------------


def _cfo(seat: _Seat, data: GameData) -> None:
    """Below the runway threshold, propose a round or a loan; above the cash threshold, repay
    debt early (24.1)."""
    state, b = seat.state, seat.run.balance
    company = seat.a.company_id
    cash = account_balance(seat.run.balances, company, CASH)
    burn = max(projected_net_burn(state, company, b, data), 0)
    if burn > 0 and cash < seat.a.number("runway_months") * burn:
        series = next_series(state, company)
        months = cash / burn
        if series is not None and series_problem(state, company, series, b) is None:
            lo, hi = (
                b.finance.round.typical_cents[series].lo,
                b.finance.round.typical_cents[series].hi,
            )
            target = int((lo + hi) // 2)
            _propose(
                seat,
                "round",
                (("series", series), ("target_cents", target)),
                f"raising a {series.upper() if len(series) == 1 else series} round of "
                f"${target // PCT:,}: runway is {months:.1f} months",
            )
            return
        for kind in ("bank_loan", "venture_debt"):
            terms = debt.terms(state, company, kind, b, data)
            if terms.problem is None and terms.max_cents >= b.debt.min_cents:
                amount = max(b.debt.min_cents, round(terms.max_cents * b.exec_authority.loan_share))
                _propose(
                    seat,
                    "loan",
                    (("loan_kind", kind), ("amount_cents", amount)),
                    f"borrowing ${amount // PCT:,} ({kind.replace('_', ' ')}): runway is "
                    f"{months:.1f} months",
                )
                return
        return
    spare = cash - seat.a.number("repay_above_months") * burn
    loans = [loan for loan in state.company_loans(company) if loan.active]
    if burn <= 0 or spare <= 0 or not loans:
        return
    loan = min(loans, key=lambda x: (-x.rate_bp, x.id))  # the dearest first
    share = b.exec_authority.repay_share * (
        1 - (0 if seat.right else b.exec_authority.mistake_budget_off)
    )
    amount = min(loan.balance_cents, round(spare * share))
    if amount >= b.debt.min_cents // PCT:
        seat.act(
            RepayLoan(seat.holder, loan.id, amount),
            f"repaid ${amount // PCT:,} of the {loan.instrument.replace('_', ' ')} early",
            mistake=not seat.right,
        )


# --- Proposals (24.1) -------------------------------------------------------------------------


def _propose(
    seat: _Seat, kind: ProposalKind, params: tuple[tuple[str, int | str], ...], text: str
) -> None:
    """A proposal for the player (major: it blocks Continue, 23.1), unless one of its kind is
    pending or was declined within a quarter."""
    state = seat.state
    company = seat.a.company_id
    quiet = seat.run.balance.exec_authority.report_months
    for p in state.proposals:
        if p.company_id != company or p.kind != kind:
            continue
        if p.status == "pending" or (
            p.status == "declined" and (p.resolved_turn or p.turn) > state.turn - quiet
        ):
            return
    pid, ids = state.next_ids.take("proposal")
    proposal = Proposal(
        pid, company, seat.a.seat, seat.holder, state.turn, kind, tuple(sorted(params)), text
    )
    seat.run.state = with_proposal(replace(state, next_ids=ids), proposal)
    person = state.person(seat.holder)
    seat.run.logs.append(
        inbox_item(
            state.turn,
            company,
            "exec_proposal",
            link_kind="person",
            link_id=seat.holder,
            name=f"{person.first_name} {person.last_name}",
            what=kind,
            detail=f"{person.first_name} proposes {text}.",
        )
    )
    seat.notes.append((f"proposed {text}", False))


# --- Phase 2 ---------------------------------------------------------------------------------


def run_executives(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...], tuple[DelegateAction, ...]]:
    """Phase 2, after the hiring delegates (ADR-0015): every executive with authority, the
    player's company only, seats in 24.1 order."""
    run = DelegateRun(state=state, balances=dict(balances), rng=rng, balance=balance, data=data)
    ea = balance.exec_authority
    lines: list[str] = []
    company = state.player.id
    for index, (a, holder) in enumerate(acting_seats(state, company)):
        ps = run.state.person_state(holder)
        if ps.energy is None:
            run.state = with_person_state(run.state, replace(ps, energy=ea.energy_per_month))
        score = true_score(run.state, holder, a.seat, balance)  # never shown (24.4)
        u = float(delegate_draws(rng, state.turn, holder, QUALITY_KEY + index).random())
        seat = _Seat(run, a, holder, u < decision_quality(score, ea.quality))
        match a.seat:
            case "cto":
                _cto(seat, data)
            case "cro":
                _cro(seat, data)
            case "cmo":
                history = run.state.company(company).mrr_history
                _cmo(seat, data, history[-1] if history else 0)  # last month's revenue
            case "coo":
                _coo(seat, data)
            case "cfo":
                _cfo(seat, data)
        person = run.state.person(holder)
        name = f"{person.first_name} {person.last_name}"
        for text, mistake in seat.notes:
            did, ids = run.state.next_ids.take("exec_decision")
            run.state = with_exec_decision(
                replace(run.state, next_ids=ids),
                ExecDecision(did, company, a.seat, holder, state.turn, text, mistake),
            )
            lines.append(f"{name} ({a.seat.upper()}) {text}{' (a misstep)' if mistake else ''}")
    if lines:
        run.logs.append(
            inbox_item(state.turn, company, "exec_decisions", summary="; ".join(lines) + ".")
        )
    return run.state, tuple(run.entries), tuple(run.logs), tuple(run.taken)
