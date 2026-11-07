"""Historical scenarios (docs/formulas.md 30.3, M15b sub-task 4): each start (staff, products,
research, debt) built on the world as it stood, and its goal judged every month: a goal that
is reached ends the scenario a success at once; at the deadline's month end it is judged
either way, and a game that ends before then fails it.

Staff are generated in the start month from stream `scenario` (43), key (index,) by their
position in the scenario's staff list (ADR-0013)."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import ym_to_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidModeError
from tst.sim.finance.models import Loan
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, LedgerBalances, LedgerEntry, account_balance
from tst.sim.modes.config import GoalSpec, HistoricalScenario
from tst.sim.modes.world import ModeSpec
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.people.reveal import new_reveal_state
from tst.sim.products.models import SELLING, Product, ProductSegment
from tst.sim.research.models import ResearchLead
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_company,
    with_employment,
    with_loan,
    with_person,
    with_person_state,
    with_product,
    with_product_segment,
    with_research_lead,
    with_reveal,
)

DEBT: Final = "2500_debt"  # accounts.yaml: loans' principal (20.3)
CENTS_A_DOLLAR: Final = 100  # tunable-exempt: cents in a dollar
MONTHS_A_YEAR: Final = 12  # tunable-exempt: calendar
DONE: Final = "scenario_done"


def scenario(data: GameData, key: str) -> HistoricalScenario:
    found = data.historical_scenario(key)
    if found is None:
        raise InvalidModeError(f"no historical scenario {key!r}")
    return found


def scenario_spec(key: str, data: GameData) -> ModeSpec:
    """The ModeSpec of a historical scenario: its year and cash, all rivals, historical eras."""
    h = scenario(data, key)
    return ModeSpec(
        kind="scenario", start_year=h.year, cash_cents=h.cash_dollars * CENTS_A_DOLLAR, scenario=key
    )


def deadline_turn(h: HistoricalScenario) -> int:
    return ym_to_turn(*h.deadline)


def apply_start(
    state: GameState, key: str, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...]]:
    """The scenario's company in its start month: stage, staff, products, research leads and
    loans (with their cash). Returns the state and the loans' entries."""
    h = scenario(data, key)
    company = state.player
    turn = state.turn
    state = with_company(state, replace(company, stage=h.stage, stage_history=((h.stage, turn),)))
    gen = 0
    for spec in h.staff:
        role = data.role(spec.role)
        for _ in range(spec.count):
            pid, ids = state.next_ids.take("person")
            eid, ids = ids.take("employment")
            state = replace(state, next_ids=ids)
            draw = rng.stream(turn, "scenario", gen)
            gen += 1
            person = generate_person(
                draw,
                data,
                balance,
                turn,
                role,
                spec.level,
                balance.founder.default_region,
                person_id=pid,
                city=company.hq_city,
            )
            state = with_person(state, person)
            state = with_employment(
                state,
                Employment(
                    id=eid,
                    person_id=pid,
                    company_id=company.id,
                    role=spec.role,
                    level=spec.level,
                    salary_cents=person.salary_expectation_cents
                    or role.salary_band_mid_cents[spec.level],
                    equity_bp=0,
                    start_turn=turn,
                    end_turn=None,
                    status="active",
                ),
            )
            state = with_person_state(state, PersonState(person_id=pid))
            state = with_reveal(
                state,
                new_reveal_state(
                    observer_company_id=company.id,
                    person=person,
                    turn=turn,
                    rng=rng,
                    data=data,
                    balance=balance,
                    knows_exactly=False,
                ),
            )
    first_product: int | None = None
    for p in h.products:
        pid, ids = state.next_ids.take("product")
        state = replace(state, next_ids=ids)
        first_product = first_product if first_product is not None else pid
        state = with_product(
            state,
            Product(
                id=pid,
                company_id=company.id,
                category=p.category,
                name=p.name,
                status="live",
                quality=p.quality,
                feature_points=p.features,
                brand=p.brand,
                marketing_budget_cents=0,
                created_turn=turn,
                launched_turn=turn,
                first_customer_turn=turn,
            ),
        )
        for segment, seg in sorted(p.segments.items()):
            state = with_product_segment(
                state,
                ProductSegment(
                    pid, segment, round(seg.price_dollars * CENTS_A_DOLLAR), seg.customers
                ),
            )
    if first_product is not None:  # the root team works on the first product (11.3)
        state = with_company(state, replace(state.player, root_product_id=first_product))
    for lead in h.research:
        state = with_research_lead(state, ResearchLead(company.id, lead.domain, lead.lead))
    entries: list[LedgerEntry] = []
    for loan in h.loans:
        lid, ids = state.next_ids.take("loan")
        state = replace(state, next_ids=ids)
        principal = loan.principal_dollars * CENTS_A_DOLLAR
        lender = next(x for x in data.lenders if x.key == loan.lender)
        state = with_loan(
            state,
            Loan(
                id=lid,
                company_id=company.id,
                instrument=lender.instrument,
                lender=loan.lender,
                principal_cents=principal,
                balance_cents=principal,
                rate_bp=loan.rate_bp,
                signed_turn=turn,
                term_months=loan.term_months,
                interest_only_months=loan.interest_only_months,
            ),
        )
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=company.id,
                memo=f"Loan from {lender.name}",
                debit=CASH,
                credit=DEBT,
                amount=principal,
            )
        )
    return state, tuple(entries)


# --- Goals ----------------------------------------------------------------------------------


def _arr_cents(state: GameState, company_id: int) -> int:
    history = state.company(company_id).mrr_history
    return (history[-1] if history else 0) * MONTHS_A_YEAR


def _customers(state: GameState, company_id: int, category: str, segment: str | None) -> float:
    total = 0.0
    for p in state.company_products(company_id):
        if p.category != category or p.status not in SELLING:
            continue
        total += sum(
            s.customers for s in state.segments_of(p.id) if segment is None or s.segment == segment
        )
        total += sum(
            r.customers
            for r in state.regional_segments_of(p.id)
            if segment is None or r.segment == segment
        )
    return total


def _units_share(state: GameState, company_id: int, category: str, data: GameData) -> float:
    """The company's share of the category's units: customers x units per customer by segment."""
    per = {m.segment: m.units_per_customer for m in data.category(category).markets}
    mine = everyone = 0.0
    for p in state.products:
        if p.category != category or p.status not in SELLING:
            continue
        units = sum(s.customers * per.get(s.segment, 1.0) for s in state.segments_of(p.id)) + sum(
            r.customers * per.get(r.segment, 1.0) for r in state.regional_segments_of(p.id)
        )
        everyone += units
        if p.company_id == company_id:
            mine += units
    return mine / everyone if everyone > 0 else 0.0


def _trailing_operating(state: GameState, company_id: int) -> int | None:
    history = state.company(company_id).op_history[-MONTHS_A_YEAR:]
    return sum(history) if history else None


def reached(
    goal: GoalSpec,
    state: GameState,
    balances: LedgerBalances,
    data: GameData,
    start_turn: int,
    *,
    final: bool,
) -> bool:
    """Whether the goal holds now. `final`: the deadline's judgement, for the goals judged
    only then (solvency and profit)."""
    cid = state.player.id
    if goal.kind == "era_or_arr":
        arrival = state.era_arrival(goal.era) if goal.era else None
        first = arrival is not None and arrival.company_id == cid
        return first or _arr_cents(state, cid) >= (goal.arr_dollars or 0) * CENTS_A_DOLLAR
    if goal.kind == "customers":
        assert goal.category is not None
        return _customers(state, cid, goal.category, goal.segment) >= (goal.customers or 0)
    if goal.kind == "unit_share":
        assert goal.category is not None
        return _units_share(state, cid, goal.category, data) >= (goal.share or 0)
    if not final:
        return False
    if goal.kind == "solvent_margin":
        from tst.sim.score import trailing_margin

        margin = trailing_margin(state, cid)
        return account_balance(balances, cid, CASH) >= 0 and margin is not None and margin > 0
    # profit_no_down_round
    profit = _trailing_operating(state, cid)
    down = any(
        r.down_round and (r.closed_turn or 0) >= start_turn
        for r in state.company_rounds(cid)
        if r.status == "closed"
    )
    return profit is not None and profit > 0 and not down


def judge(
    state: GameState, balances: LedgerBalances, balance: Balance, data: GameData
) -> GameState:
    """Phase 11, before the scores' snapshot: a scenario's verdict. Success as soon as a
    reach goal holds; at the deadline's month end, success or failure; a game that ended
    otherwise (bankrupt, removed) is a failure."""
    mode = state.mode
    if mode is None or mode.kind != "scenario" or mode.result is not None or mode.scenario is None:
        return state
    h = scenario(data, mode.scenario)
    meta = state.save_meta
    if meta.game_state != "active":
        return replace(state, mode=replace(mode, result="failure", result_turn=state.turn))
    final = state.turn >= deadline_turn(h)
    ok = reached(h.goal, state, balances, data, mode.start_turn, final=final)
    if not ok and not final:
        return state
    return replace(
        state,
        mode=replace(mode, result="success" if ok else "failure", result_turn=state.turn),
        save_meta=replace(meta, game_state=DONE, ended_turn=state.turn),
    )
