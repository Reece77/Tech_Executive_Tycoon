"""Historical scenarios (docs/formulas.md 30.3, M15b sub-task 4): each start (staff, products,
research, debt) built on the world as it stood, and its goal judged every month: a goal that
is reached ends the scenario a success at once; at the deadline's month end it is judged
either way, and a game that ends before then fails it.

Staff are generated in the start month from stream `scenario` (43), key (index,) by their
position in the scenario's staff list (ADR-0013)."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

import numpy as np

from tst.sim.calendar import HISTORY_START_YEAR, TURN_ZERO, ym_to_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidModeError
from tst.sim.fabs.models import Fab
from tst.sim.family.setup import FamilySpec
from tst.sim.finance.models import Loan
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, LedgerBalances, LedgerEntry, LedgerLine, account_balance
from tst.sim.modes.config import ContractSpec, FabSpec, GoalSpec, HistoricalScenario
from tst.sim.modes.world import ModeSpec
from tst.sim.people.founder import FounderSpec
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
# tunable-exempt: the cash a scenario's start-up fab order is checked against (it is paid for
# by the starting equity, not cash)
DEBT_FREE_CASH: Final = 10**15  # tunable-exempt: a check amount, never posted
VEHICLES: Final = "vehicles"  # categories.yaml: cars (49)


def scenario_draw(rng: RngFactory, turn: int, *key: int) -> np.random.Generator:
    """Stream `scenario` (43), the one call site (ADR-0013): M15b's staff, key (index,), and
    M52's added rivals, keys past them (tst.sim.modes.custom)."""
    return rng.stream(turn, "scenario", *key)


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


def world_year(h: HistoricalScenario) -> int:
    """The year the scenario's world is played from (M50): 2008 for a start before 2010."""
    return HISTORY_START_YEAR if h.year < TURN_ZERO[0] else TURN_ZERO[0]


def founder_spec(h: HistoricalScenario, chosen: FounderSpec) -> FounderSpec:
    """The founder a scenario's new game builds (M51): the player's choice, with the
    scenario's region, and its age taken back to the world's first year (so the family's ages
    check against it: 45.1); `apply_start` sets the age at the start."""
    age = chosen.age
    if h.founder_age is not None:
        age = h.founder_age - (h.year - world_year(h))
    return replace(
        chosen,
        age=age,
        region=h.founder_region if h.founder_region is not None else chosen.region,
    )


def family_spec(h: HistoricalScenario) -> FamilySpec | None:
    """The scenario's family as the new game builds it, in the world's first year (M51)."""
    if h.family is None:
        return None
    back = h.year - world_year(h)
    return FamilySpec("children", tuple(a - back for a in h.family.child_ages))


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
    if h.founder_age is not None:  # M51: the founder's age at the start (past the new-game range)
        founder = state.founder_of(company.id)
        assert founder is not None
        born = turn - h.founder_age * MONTHS_A_YEAR
        state = with_person(state, replace(founder, birth_turn=born))
    gen = 0
    units: dict[str, int] = {}
    for spec in h.staff:
        if spec.unit is not None and spec.unit not in units:  # M51: a named team
            state, units[spec.unit] = _team(state, spec.unit)
        role = data.role(spec.role)
        for _ in range(spec.count):
            pid, ids = state.next_ids.take("person")
            eid, ids = ids.take("employment")
            state = replace(state, next_ids=ids)
            draw = scenario_draw(rng, turn, gen)
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
                    unit_id=units.get(spec.unit) if spec.unit is not None else None,
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
                status=p.status,
                quality=p.quality,
                feature_points=p.features,
                brand=p.brand,
                marketing_budget_cents=0,
                created_turn=turn,
                launched_turn=turn if p.status == "live" else None,
                first_customer_turn=turn if p.status == "live" else None,
            ),
        )
        if p.contract is not None:  # M51: its assembly contract, signed this month (26.2)
            state = _contract(state, pid, p.contract, balance, p.category)
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
    for fab_spec in h.fabs:  # M51: fabs already running (38.2)
        background = data.scenario(h.background)
        assert background is not None
        equity = background.starting_equity_account
        state, entry = _running_fab(state, fab_spec, units[fab_spec.unit], equity, balance, data)
        entries.append(entry)
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


def _team(state: GameState, name: str) -> tuple[GameState, int]:
    from tst.sim.org.models import OrgUnit
    from tst.sim.state import with_unit

    uid, ids = state.next_ids.take("unit")
    unit = OrgUnit(
        id=uid,
        company_id=state.player.id,
        kind="team",
        name=name,
        parent_id=None,
        leader_id=None,
        policy=None,
        created_turn=state.turn,
    )
    return with_unit(replace(state, next_ids=ids), unit), uid


def _running_fab(
    state: GameState,
    spec: FabSpec,
    unit_id: int,
    equity: str,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, LedgerEntry]:
    """A fab ordered as `BuildFab` orders one, then made as if built `age_months` ago: live,
    staffed by its team, its yield mature, its capex on the books (against the starting
    equity) less the depreciation since. The entry posts its net book value."""
    import tst.sim.actions  # noqa: F401  (fabs.actions imports the package first)
    from tst.sim.fabs import market as fm
    from tst.sim.fabs.actions import BuildFab, build_fab
    from tst.sim.fabs.models import CapexPart
    from tst.sim.fabs.plants import depreciation_total
    from tst.sim.ledger import ACCUMULATED_DEPRECIATION, PPE

    company = state.player.id
    founder = state.founder_of(company)
    assert founder is not None
    energy = state.person_state(founder.id)
    fid = state.next_ids.facility
    out = build_fab(
        state,
        BuildFab(founder.id, spec.node, spec.region, spec.capacity, country=spec.country),
        balance,
        data,
        {(company, CASH): DEBT_FREE_CASH},
    )
    state = with_person_state(out.state, energy)  # the start costs no energy
    facility = state.facility(fid)
    fab = fm.fab_of(state, fid)
    assert facility is not None and fab is not None
    built = state.turn - spec.age_months
    life = balance.facility.kinds["fab"].life_months
    fab = replace(
        fab,
        live_turn=built,
        tools_turn=None,
        yield_=balance.fab.yield_.mature,
        months_run=spec.age_months,
        parts=(CapexPart(facility.capex_cents, built),),
    )
    depreciated = depreciation_total(fab, state.turn - 1, life)
    facility = replace(
        facility,
        status="live",
        ordered_turn=built - fab.build_months,
        ready_turn=built,
        late_turn=built,
        capex_paid_cents=facility.capex_cents,
        depreciated_cents=depreciated,
        unit_id=unit_id,
    )
    from tst.sim.state import with_fab, with_facility

    state = with_fab(with_facility(state, facility), fab)
    lines = [LedgerLine(PPE, facility.capex_cents)]
    if depreciated:
        lines.append(LedgerLine(ACCUMULATED_DEPRECIATION, -depreciated))
    lines.append(LedgerLine(equity, -(facility.capex_cents - depreciated)))
    entry = LedgerEntry(
        turn=state.turn, company_id=company, memo="Fab brought forward", lines=tuple(lines)
    )
    return state, entry


def _contract(
    state: GameState, product_id: int, spec: ContractSpec, balance: Balance, category: str
) -> GameState:
    """A contract-manufacturing deal as `SignManufacturingContract` makes one (26.2)."""
    from tst.sim.actions.hardware import manufacturing_fee_cents
    from tst.sim.hardware.models import ProductionContract
    from tst.sim.money import to_millicents
    from tst.sim.state import with_production_contract

    fee = manufacturing_fee_cents(balance, category, spec.manufacturer, spec.city)
    cid, ids = state.next_ids.take("production_contract")
    contract = ProductionContract(
        id=cid,
        company_id=state.player.id,
        product_id=product_id,
        kind="assembly",
        supplier=spec.manufacturer,
        units=spec.units,
        price_millicents=to_millicents(fee),
        signed_turn=state.turn,
        end_turn=state.turn + spec.months - 1,
        city=spec.city,
    )
    return with_production_contract(replace(state, next_ids=ids), contract)


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


def _running(state: GameState, company_id: int, balance: Balance, data: GameData) -> list[Fab]:
    """The company's fabs live this month and running wafers (38.2)."""
    from tst.sim.fabs.plants import facility_of, is_live

    return [
        f
        for f in state.fabs
        if f.company_id == company_id
        and is_live(f, facility_of(state, f), state.turn)
        and f.month is not None
        and f.month.run > 0
    ]


def best_node_gap(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> int | None:
    """Nodes between the leading edge and the company's newest node in volume (None: no fab
    runs)."""
    from tst.sim.fabs import market as fm

    timeline = fm.timeline(state, balance, data)
    running = _running(state, company_id, balance, data)
    if not running:
        return None
    return min(timeline.behind(f.node, state.turn) for f in running)


def node_volume(
    state: GameState, company_id: int, node: str, balance: Balance, data: GameData
) -> float:
    """Wafer starts run this month on the company's live fabs at `node` or newer."""
    from tst.sim.fabs import market as fm

    timeline = fm.timeline(state, balance, data)
    least = timeline.generation(node)
    return sum(
        f.month.run
        for f in _running(state, company_id, balance, data)
        if f.month is not None and timeline.generation(f.node) >= least
    )


def family_succeeded(state: GameState, balance: Balance) -> bool:
    """A child of the family's first head is the head and runs the company (head mode
    "founder", not a professional CEO: 45.5), and the family holds control (45.6)."""
    from tst.sim.family import rules
    from tst.sim.family.models import CHILD

    family = state.family
    if family is None or family.head_id == family.id or family.head_mode != "founder":
        return False
    child = any(m.person_id == family.head_id and m.relation == CHILD for m in state.family_members)
    return child and rules.family_bp(state) >= balance.family.control_bp


def cars_a_year(state: GameState, company_id: int) -> int:
    """Cars the company sold in the last 12 months (49: the vehicle history rows)."""
    mine = {p.id for p in state.company_products(company_id) if p.category == VEHICLES}
    return round(
        sum(
            m.units
            for m in state.vehicle_months
            if m.product_id in mine and m.turn > state.turn - MONTHS_A_YEAR
        )
    )


def own_developer_share(state: GameState, company_id: int, region: str | None) -> float:
    """The best developer share any of the company's own platforms holds in a region (44.2),
    or in `region` alone."""
    best = 0.0
    for p in state.platforms:
        if p.owner_id != company_id or p.ended_turn is not None:
            continue
        for r in state.platform_regions:
            if r.platform_id == p.id and (region is None or r.region == region):
                best = max(best, r.dev_share)
    return best


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
    balance: Balance,
) -> bool:
    """Whether the goal holds now. `final`: the deadline's judgement, for the goals judged
    only then (solvency and profit)."""
    cid = state.player.id
    if goal.kind == "arr":
        return _arr_cents(state, cid) >= (goal.arr_dollars or 0) * CENTS_A_DOLLAR
    if goal.kind == "customers":
        assert goal.category is not None
        return _customers(state, cid, goal.category, goal.segment) >= (goal.customers or 0)
    if goal.kind == "unit_share":
        assert goal.category is not None
        return _units_share(state, cid, goal.category, data) >= (goal.share or 0)
    if goal.kind == "family_succession":  # M51 (63.1): at the deadline
        return final and family_succeeded(state, balance)
    if goal.kind == "fab_catch_up":  # M51 (63.1): both at once, in any month
        gap = best_node_gap(state, cid, balance, data)
        profit = _trailing_operating(state, cid)
        return (
            gap is not None
            and gap <= (goal.node_gap or 0)
            and profit is not None
            and profit > 0
            and len(state.company(cid).op_history) >= MONTHS_A_YEAR
        )
    if goal.kind == "node_volume":  # M51 (63.1)
        assert goal.node is not None
        return node_volume(state, cid, goal.node, balance, data) > 0
    if goal.kind == "vehicles_year":  # M51 (63.1)
        return cars_a_year(state, cid) >= (goal.units or 0)
    if goal.kind == "platform_share":  # M51 (63.1)
        return own_developer_share(state, cid, goal.region) >= (goal.share or 0)
    if not final:
        return False
    if goal.kind == "solvent_margin":
        from tst.sim.score import trailing_margin

        margin = trailing_margin(state, cid)
        return account_balance(balances, cid, CASH) >= 0 and margin is not None and margin > 0
    if goal.kind == "solvent_series":  # M51 (63.1): solvent, with the round closed since the start
        raised = any(
            r.series == goal.series and r.status == "closed" and (r.closed_turn or 0) >= start_turn
            for r in state.company_rounds(cid)
        )
        return account_balance(balances, cid, CASH) >= 0 and raised
    # profit_no_down_round
    profit = _trailing_operating(state, cid)
    down = any(
        r.down_round and (r.closed_turn or 0) >= start_turn
        for r in state.company_rounds(cid)
        if r.status == "closed"
    )
    return profit is not None and profit > 0 and not down


def bonus_reached(goal: GoalSpec, state: GameState) -> bool | None:
    """The goal's bonus (M15r addendum d), shown on the result screen and never judged:
    the player caused `bonus_era` first. None when the goal has no bonus."""
    if goal.bonus_era is None:
        return None
    arrival = state.era_arrival(goal.bonus_era)
    return arrival is not None and arrival.company_id == state.player.id


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
    if h.goal is None:  # M52 (66.1): a custom scenario with no goal is open play, no verdict
        return state
    meta = state.save_meta
    if meta.game_state != "active":
        return replace(state, mode=replace(mode, result="failure", result_turn=state.turn))
    final = state.turn >= deadline_turn(h)
    ok = reached(h.goal, state, balances, data, mode.start_turn, final=final, balance=balance)
    if not ok and not final:
        return state
    return replace(
        state,
        mode=replace(mode, result="success" if ok else "failure", result_turn=state.turn),
        save_meta=replace(meta, game_state=DONE, ended_turn=state.turn),
    )
