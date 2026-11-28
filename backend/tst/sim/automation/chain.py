"""The chain's area rules (docs/formulas.md 40.7, M27b): device production, supply and
commodities, exploration, mines and refineries, fabs and foundry customers, government affairs
and corporate development.

Each rule reads only what the company can see (its own production rows, contracts, desk-study
bands, displayed ranges, quotes; ADR-0007, ADR-0015), ranks its options, and acts through
`AutoRun.attempt` with the chain's own actions, which keeps the money limit, the month's budget
and the one-offs. A wrong draw (stream `automation`, 40.3) takes the area's stated mistake: an
order 20% off, a supplier, block, target or stage one place lower in the ranking, a contract
20% under the best price, or a month late. The chain modules' rules are called, never changed.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from tst.sim import dmath
from tst.sim.actions import Action
from tst.sim.automation import owners
from tst.sim.automation.models import AreaOwner
from tst.sim.automation.run import AutoRun
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import SimError
from tst.sim.exploration.pipeline import StageName
from tst.sim.fabs.models import FabMonth
from tst.sim.ledger import CASH, account_balance
from tst.sim.mining.models import Mine
from tst.sim.org.formulas import decision_quality
from tst.sim.products.models import SELLING
from tst.sim.state import GameState, group_companies, listed_id

WEEKS_A_MONTH: Final = 52 / 12  # tunable-exempt: calendar
MONTHS_A_YEAR: Final = 12  # tunable-exempt: calendar
MONTHS_A_QUARTER: Final = 3  # tunable-exempt: calendar
EPS: Final = 1e-9  # tunable-exempt: float tolerance
PCT: Final = 100  # tunable-exempt: percent
PLAN_CHANNEL: Final = "any"


def _right(run: AutoRun, owner: AreaOwner) -> bool:
    b = run.balance
    score = owners.true_area_score(run.state, owner.company_id, owner.area, owner.person_id, b)
    return run.draw() < decision_quality(score, b.automation.quality)


def _default(b: Balance, area: str, key: str) -> float:
    return float(owners.area_def(b, area).guardrails.get(key, 0.0))


def _rail(owner: AreaOwner, b: Balance, key: str) -> float:
    return owner.guardrail(key, _default(b, owner.area, key))


def _act(run: AutoRun, owner: AreaOwner, action: Action, text: str, mistake: bool) -> bool:
    """One decision: the action through the limit and one-off tests, logged as a decision or
    the area's misstep."""
    run.text = text
    if run.attempt(owner.company_id, action):
        run.decisions.append(("mistake" if mistake else "decision", text, run.last_cost, None))
        return True
    return False


def _pick[T](run: AutoRun, owner: AreaOwner, ranked: list[T]) -> tuple[T, bool]:
    """The best option, or on a wrong draw the next one (the mistake), as (option, mistake)."""
    right = _right(run, owner)
    if right or len(ranked) == 1:
        return ranked[0], False
    return ranked[1], True


def _late(run: AutoRun, owner: AreaOwner, what: str) -> bool:
    """A month-late mistake: True when the right rule acts this month."""
    if _right(run, owner):
        return True
    run.decisions.append(("mistake", f"left {what} for next month", 0, None))
    return False


def group_of(state: GameState) -> set[int]:
    return {c.id for c in group_companies(state, listed_id(state))} | {state.player.id}


# --- Shared: staffing a facility to its need (devices' plants, mines, refineries, fabs) -------


def _staff(run: AutoRun, owner: AreaOwner, kinds: Callable[[str], bool], data: GameData) -> None:
    """Each live or building facility of these kinds: a unit to staff it (an empty facility
    gets one of the company's units that staffs nothing and holds the kind's roles), and a
    hiring plan for the gap to its need (22.2's staff_per; 35.3 for mines)."""
    from tst.sim.actions import CreatePlan, StaffFacility
    from tst.sim.facilities.lifecycle import kind_of, staffing
    from tst.sim.mining.actions import StaffMine

    state, b = run.state, run.balance
    company = owner.company_id
    facilities = [
        f
        for f in state.company_facilities(company)
        if kinds(f.kind) and f.status not in ("closed", "mothballed")
    ]
    used = {f.unit_id for f in state.company_facilities(company) if f.unit_id is not None}
    for f in sorted(facilities, key=lambda f: f.id):
        k = kind_of(f, b)
        roles = tuple(k.staff_roles)
        if not roles:
            continue
        if f.unit_id is None:
            free = sorted(
                {
                    e.unit_id
                    for e in state.staff(company)
                    if e.unit_id is not None and e.unit_id not in used and e.role in roles
                }
            )
            if not free:
                continue
            unit = free[0]
            mine = any(m.id == f.id for m in state.mines)
            action: Action = (
                StaffMine(owner.person_id, f.id, unit)
                if mine
                else StaffFacility(owner.person_id, f.id, unit)
            )
            if _act(run, owner, action, f"staffed {_label(f.kind)} #{f.id}", False):
                used.add(unit)
            state = run.state
            continue
        need = staffing(state, f, b)
        planned = sum(
            p.target
            for p in state.plans
            if p.company_id == company and p.status == "active" and p.unit_id == f.unit_id
        )
        gap = need.needed - need.staff - planned
        if gap <= 0:
            continue
        ratio = b.delegates.max_ratio_bp
        plan = CreatePlan(
            owner.person_id, owner.person_id, roles[0], gap, PLAN_CHANNEL, ratio, 0, f.unit_id
        )
        label = data.role(roles[0]).label.lower()
        _act(
            run, owner, plan, f"opened a plan for {gap} {label}s at {_label(f.kind)} #{f.id}", False
        )
        state = run.state


def _label(kind: str) -> str:
    return kind.replace("_", " ")


# --- Device production (40.7; M27b sub-task 2) --------------------------------------------------


def device_products(state: GameState, company: int, b: Balance) -> list[int]:
    return [
        p.id
        for p in state.company_products(company)
        if p.category in b.hardware.bom and p.status in SELLING
    ]


def device_cover(state: GameState, product_id: int, b: Balance, turn: int) -> tuple[float, float]:
    """(demand a month, supply a month at `turn`): last month's units plus the demand lost to
    the capacity cap (the shown demand plan, 26.2), against the assembly contracts running then
    and the company's plants' share (pooled across its devices)."""
    from tst.sim.hardware import production as hp

    row = state.production_of(product_id)
    demand = (row.units + row.lost_units) if row is not None else 0.0
    product = state.product(product_id)
    if product is None:
        return demand, 0.0
    contracts = sum(
        c.units
        for c in state.production_contracts
        if c.product_id == product_id
        and c.kind == "assembly"
        and c.signed_turn <= turn <= c.end_turn
        and c.status == "active"
    )
    devices = max(1, len(device_products(state, product.company_id, b)))
    plants = sum(hp.runnable(state, f, b) for f in hp.live_plants(state, product.company_id, b))
    return demand, contracts + plants / devices


def cover_weeks(demand: float, supply: float) -> float | None:
    return supply / demand * WEEKS_A_MONTH if demand > EPS else None


def production(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Each device's cover (weeks of the shown demand plan that next month's supply covers)
    kept between the guardrails: below the low guardrail, a contract-manufacturer order with
    the best displayed fee for `order_weeks` of cover (within standard terms); above the high,
    contracts lapse at their end. Its plants are staffed to their need. Mistake: an order 20%
    off."""
    from tst.sim.actions.hardware import SignManufacturingContract, manufacturing_fee_cents
    from tst.sim.contracts import termination as ct
    from tst.sim.hardware import production as hp

    state, b = run.state, run.balance
    hb = b.hardware.contract
    lo = _rail(owner, b, "cover_low_weeks")
    target = max(lo, _rail(owner, b, "order_weeks"))
    _staff(run, owner, lambda k: k == b.hardware.plant_kind, data)
    for pid in device_products(run.state, owner.company_id, b):
        state = run.state
        demand, supply = device_cover(state, pid, b, state.turn + 1)
        weeks = cover_weeks(demand, supply)
        if weeks is None or weeks >= lo:
            continue
        product = state.product(pid)
        assert product is not None
        city = hb.cheap_city
        makers = sorted(
            hb.manufacturers,
            key=lambda m: (
                ct.offered(state, m, manufacturing_fee_cents(b, product.category, m, city), b),
                m,
            ),
        )
        want = math.ceil(demand * target / WEEKS_A_MONTH - supply)
        right = _right(run, owner)
        units = want if right else math.ceil(want * (1 - b.automation.mistake_off))
        units = max(1, min(hb.max_units, units))
        months = int(_rail(owner, b, "contract_months"))
        months = max(int(hb.months.lo), min(int(hb.months.hi), months))
        text = f"ordered {units:,} {product.name} a month from {makers[0]} for {months} months"
        _act(
            run,
            owner,
            SignManufacturingContract(owner.person_id, pid, makers[0], city, units, months),
            text,
            not right,
        )
    # Spare plant capacity sold as contract manufacturing (26.2) once the plants run.
    state = run.state
    plants = hp.live_plants(state, owner.company_id, b)
    if plants and not _has_cm_product(state, owner.company_id, b):
        used = sum(r.plant_units for r in state.production if r.company_id == owner.company_id)
        spare = sum(hp.runnable(state, f, b) for f in plants) - used
        if spare > EPS:
            from tst.sim.actions.hardware import SellPlantCapacity

            _act(
                run,
                owner,
                SellPlantCapacity(owner.person_id),
                "began selling spare plant capacity",
                False,
            )


def _has_cm_product(state: GameState, company: int, b: Balance) -> bool:
    from tst.sim.hardware.cm_market import cm_product

    return cm_product(state, company, b) is not None


# --- Supply and commodities (40.7; M27b sub-task 3) ---------------------------------------------


@dataclass(frozen=True, slots=True)
class Need:
    good: str
    month: float  # volume units a month at last month's production
    cover: float  # (deals over the next 12 months + own supply x 12) / (need x 12), at most 1+


def supply_needs(state: GameState, company: int, b: Balance, data: GameData) -> list[Need]:
    """Each commodity input's 12-month cover (M23c's planning view with M23r's own-supply
    count): running contracts and offtakes month by month, plus the group's own supply of the
    month just played held flat."""
    from tst.sim.commodities import costs

    if data.commodities is None:
        return []
    use = costs.company_use(state, company, b, data)
    group = group_of(state)
    out = []
    for good in sorted(use):
        month = use[good]
        if month <= EPS:
            continue
        deals = [
            d
            for d in state.commodity_deals
            if d.company_id == company and d.good == good and d.status == "active"
        ]
        dealt = sum(
            d.monthly_volume
            for i in range(1, MONTHS_A_YEAR + 1)
            for d in deals
            if d.signed_turn <= state.turn + i <= d.end_turn
        )
        own = sum(
            s.volume
            for s in state.own_supply
            if s.good == good
            and s.turn == state.turn - 1
            and s.buyer_id == company
            and s.seller_id in group
        )
        need = month * MONTHS_A_YEAR
        out.append(Need(good, month, (dealt + own * MONTHS_A_YEAR) / need))
    return out


def _bloc(state: GameState, company: int, b: Balance, data: GameData) -> str | None:
    from tst.sim.geopolitics import world

    if not world.enabled(data):
        return None
    country = world.company_country(state, state.company(company), b, data)
    return world.bloc_of(data, country, state.turn)


def supply_options(
    state: GameState, company: int, good: str, volume_year: float, b: Balance, data: GameData
) -> list[tuple[tuple[int, float, str], Action, str]]:
    """The ways to cover a gap, best first: the group's own mines (group supply), then
    offtakes from suppliers in the company's bloc (39), then the rest, by displayed price; a
    standard contract with the traders ranks by its price outside the bloc."""
    from tst.sim.actions.commodities import SignCommodityContract, SignOfftake
    from tst.sim.commodities.offtake import spot_price
    from tst.sim.contracts import termination as ct
    from tst.sim.geopolitics import supply as geo_supply
    from tst.sim.geopolitics import world
    from tst.sim.mining.actions import SetMineSales

    actor = 0  # filled in by the caller
    options: list[tuple[tuple[int, float, str], Action, str]] = []
    group = group_of(state)
    for m in sorted(state.mines, key=lambda m: m.id):
        if (
            m.company_id in group
            and m.commodity == good
            and m.is_open
            and m.buyer_id is None
            and m.company_id != company
        ):
            text = f"routed mine #{m.id}'s {good.replace('_', ' ')} to the group"
            options.append(
                ((0, 0.0, f"mine{m.id}"), SetMineSales(actor, m.id, company, "cost_plus"), text)
            )
    spot = spot_price(state, good, data, b)
    bloc = _bloc(state, company, b, data)
    years = int(b.offtake.years.lo)
    if data.suppliers is not None:
        for s in data.suppliers.suppliers:
            if not s.sells(good, state.turn):
                continue
            try:
                if geo_supply.banned_supplier(state, company, s.key, good, b, data):
                    continue
            except (SimError, TypeError, AttributeError, KeyError):
                pass
            country = geo_supply.supplier_country(data, s.key)
            allied = (
                bloc is not None
                and country is not None
                and world.bloc_of(data, country, state.turn) == bloc
            )
            price = ct.offered(state, s.key, spot, b)
            text = f"signed a {years}-year {good.replace('_', ' ')} offtake with {s.name}"
            options.append(
                (
                    (1 if allied else 2, price, s.key),
                    SignOfftake(actor, good, s.key, years, volume_year),
                    text,
                )
            )
    lo, hi = b.commodity.contract_months.lo, b.commodity.contract_months.hi
    months = int(max(lo, min(hi, MONTHS_A_YEAR)))  # the standard contract: a year
    price = ct.offered(state, f"traders:{good}", spot, b)
    text = f"signed a {months}-month {good.replace('_', ' ')} contract"
    options.append(
        ((2, price, "~contract"), SignCommodityContract(actor, good, months, volume_year), text)
    )
    options.sort(key=lambda o: o[0])
    return options


def supply(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Each input's 12-month cover kept within the band: below it, the best option of
    `supply_options` for the gap to the band's middle; above it, contracts lapse at their end
    (terminating stays a one-off). A chip product's wafers follow the same band. Mistake: a
    supplier one place lower in the ranking."""
    from dataclasses import replace

    state, b = run.state, run.balance
    lo, hi = _rail(owner, b, "cover_low"), _rail(owner, b, "cover_high")
    mid = (lo + hi) / 2
    for need in supply_needs(state, owner.company_id, b, data):
        if need.cover >= lo:
            continue
        volume_year = (mid - need.cover) * need.month * MONTHS_A_YEAR
        options = supply_options(run.state, owner.company_id, need.good, volume_year, b, data)
        if not options:
            continue
        (_, action, text), mistake = _pick(run, owner, options)
        action = replace(action, actor_id=owner.person_id)
        _act(run, owner, action, f"{text} (cover {need.cover:.0%})", mistake)
    _wafers(run, owner, lo, mid, data)


def wafer_need(
    state: GameState, product_id: int, b: Balance, data: GameData
) -> tuple[float, float]:
    """(starts a month the chip needed last month, starts covered next month by wafer
    contracts and the group's fabs)."""
    from tst.sim.chips import chips
    from tst.sim.fabs import supply as fab_supply

    product = state.product(product_id)
    row = state.production_of(product_id)
    if product is None or row is None:
        return 0.0, 0.0
    t = chips.type_of(product, data, b)
    y = chips.chip_yield(state, product.company_id, b, data)
    per = max(EPS, t.per_wafer * y)
    need = (row.units + row.internal_units + row.lost_units) / per
    turn = state.turn + 1
    contracts = sum(
        c.units
        for c in state.production_contracts
        if c.product_id == product_id
        and c.kind == "wafer"
        and c.status == "active"
        and c.signed_turn <= turn <= c.end_turn
    )
    own = fab_supply.fab_chips(state, product, b, data) / per
    return need, contracts + own


def _wafers(run: AutoRun, owner: AreaOwner, lo: float, mid: float, data: GameData) -> None:
    from tst.sim.actions.hardware import SignWaferContract
    from tst.sim.chips import chips
    from tst.sim.contracts import termination as ct
    from tst.sim.facilities.config import month_to_turn

    b = run.balance
    wb = b.chips.contract
    for p in run.state.company_products(owner.company_id):
        state = run.state
        if p.status not in SELLING or not chips.is_chip(p, data):
            continue
        need, covered = wafer_need(state, p.id, b, data)
        if need <= EPS or covered / need >= lo:
            continue
        t_key = data.category(p.category).chip_type or ""
        ranked = []
        for key in sorted(wb.foundries):
            try:
                price = chips.index_wafer_cents(state, t_key, b, data, key)
            except (SimError, KeyError, AttributeError):
                continue
            start = wb.foundries[key].from_
            if start is not None and state.turn < month_to_turn(start):
                continue
            ranked.append((ct.offered(state, key, price, b), key))
        if not ranked:
            continue
        ranked.sort()
        (_, foundry), mistake = _pick(run, owner, ranked)
        wafers = max(1, min(wb.max_wafers, math.ceil(need * mid - covered)))
        months = int(wb.months.lo) * 2 if wb.months.lo * 2 <= wb.months.hi else int(wb.months.lo)
        text = f"contracted {wafers:,} wafer starts a month for {p.name} from {foundry}"
        _act(
            run,
            owner,
            SignWaferContract(owner.person_id, p.id, foundry, wafers, months),
            f"{text} (cover {covered / need:.0%})",
            mistake,
        )


# --- Exploration (40.7; M27b sub-task 4) --------------------------------------------------------

STUDIES: Final[tuple[StageName, ...]] = ("scoping", "definitive")  # the screen, then the study
MISTAKE_STUDY: Final[StageName] = "pre_feasibility"  # the second-best study: 8 months more


def exploration_spent(state: GameState, company: int) -> int:
    """What the area committed over the last 12 months (its decisions' commitments)."""
    return sum(
        d.commitment_cents
        for d in state.area_decisions
        if d.company_id == company
        and d.area == "exploration"
        and d.kind in ("decision", "mistake")
        and d.turn > state.turn - MONTHS_A_YEAR
    )


def exploration(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Within the yearly budget the player sets (0: off until set): the licensed projects run
    stage by stage (survey, sampling, drilling, estimate, a scoping then a definitive study,
    permitting), a project whose displayed grade range falls wholly below the guardrail
    (x the commodity's median grade) or whose study's mid NPV is not positive is given up, a
    licence renewed before it lapses, and the best free block the desk studies show licensed
    while a front has fewer than `projects` live. The development decision (BuildMine) is
    proposed once a permit is in: a one-off. Mistake: the second-best block or study."""
    from tst.sim.exploration.pipeline import (
        OrderDrilling,
        RelinquishProject,
        RenewLicence,
        StartStage,
        TakeLicence,
        holder_of,
    )

    state, b = run.state, run.balance
    company = owner.company_id
    budget = owner.budget_cents
    if budget <= 0:
        return

    def room() -> int:
        return budget - exploration_spent(run.state, company) - run.committed

    projects = sorted(
        (
            p
            for p in state.projects
            if p.company_id == company and p.status in ("active", "permitted")
        ),
        key=lambda p: p.id,
    )
    for p in projects:
        state = run.state
        if p.status == "permitted":
            _propose_mine(run, owner, p.id, data)
            continue
        if room() <= 0:
            break
        if p.stage is not None or p.holes_left or p.paused_until:
            continue
        if (
            p.expires_turn - state.turn <= MONTHS_A_QUARTER
            and p.renewals < b.exploration.licence.renewals
        ):
            _act(
                run,
                owner,
                RenewLicence(owner.person_id, p.id),
                f"renewed project #{p.id}'s licence",
                False,
            )
            continue
        if _below_grade(state, p, owner, b, data) or (
            p.level is not None and (p.npv_mid_cents or 0) <= 0
        ):
            _act(
                run,
                owner,
                RelinquishProject(owner.person_id, p.id),
                f"gave up project #{p.id}",
                False,
            )
            continue
        if p.reading is None:
            _act(
                run,
                owner,
                StartStage(owner.person_id, p.id, "survey"),
                f"surveyed project #{p.id}",
                False,
            )
            continue
        if p.reading == "none":
            _act(
                run,
                owner,
                RelinquishProject(owner.person_id, p.id),
                f"gave up project #{p.id} (no anomaly)",
                False,
            )
            continue
        commodity = p.commodity or _front_commodity(state, p, company)
        if p.sample_center is None:
            if commodity is not None:
                _act(
                    run,
                    owner,
                    StartStage(owner.person_id, p.id, "sampling", commodity),
                    f"sampled project #{p.id}",
                    False,
                )
            continue
        drilled = sum(1 for h in state.holes if h.project_id == p.id)
        holes = int(_rail(owner, b, "holes"))
        if drilled < holes:
            _act(
                run,
                owner,
                OrderDrilling(owner.person_id, p.id, holes - drilled),
                f"ordered {holes - drilled} holes at project #{p.id}",
                False,
            )
            continue
        if p.category is None or p.est_holes < drilled:
            _act(
                run,
                owner,
                StartStage(owner.person_id, p.id, "estimate"),
                f"estimated project #{p.id}",
                False,
            )
            continue
        done = STUDIES.index(p.level) if p.level in STUDIES else (1 if p.level else -1)
        if done + 1 < len(STUDIES):
            stage: StageName = STUDIES[done + 1]
            mistake = False
            if stage == "definitive":
                right = _right(run, owner)
                stage, mistake = (stage, False) if right else (MISTAKE_STUDY, True)
            _act(
                run,
                owner,
                StartStage(owner.person_id, p.id, stage),
                f"began a {stage.replace('_', '-')} study at project #{p.id}",
                mistake,
            )
            continue
        if p.permit_start is None:
            _act(
                run,
                owner,
                StartStage(owner.person_id, p.id, "permitting"),
                f"applied for project #{p.id}'s permit",
                False,
            )
    # New licences on the best free blocks the desk studies show, a front at a time.
    cap = int(_rail(owner, b, "projects"))
    for study in sorted(run.state.desk_studies, key=lambda s: s.id):
        state = run.state
        if study.company_id != company or not study.done or room() <= 0:
            continue
        live = [
            p
            for p in state.projects
            if p.company_id == company and p.region == study.region and p.status == "active"
        ]
        if len(live) >= cap:
            continue
        tried = {(p.region, p.block) for p in state.projects if p.company_id in group_of(state)}
        ranked = [
            block
            for band in ("high", "medium")
            for block, x in enumerate(study.bands)
            if x == band
            and (study.region, block) not in tried
            and holder_of(state, study.region, block) is None
        ]
        if not ranked:
            continue
        block, mistake = _pick(run, owner, ranked)
        _act(
            run,
            owner,
            TakeLicence(owner.person_id, study.region, block, company_id=company),
            f"licensed block {block} in {data.region(study.region).label}",
            mistake,
        )


def _front_commodity(state: GameState, p: object, company: int) -> str | None:
    """The commodity of the desk study that found the project's region (the front)."""
    region = getattr(p, "region", None)
    study = next(
        (s for s in state.desk_studies if s.company_id == company and s.region == region), None
    )
    return study.commodity if study is not None else None


def _below_grade(state: GameState, p: object, owner: AreaOwner, b: Balance, data: GameData) -> bool:
    """The displayed grade range (34.2's estimate) wholly below min_grade x the commodity's
    median grade."""
    center, hw = getattr(p, "est_grade_center", None), getattr(p, "est_grade_hw", None)
    commodity = getattr(p, "commodity", None)
    if center is None or hw is None or commodity is None or data.geology is None:
        return False
    geo = next((c for c in data.geology.commodities if c.key == commodity), None)
    if geo is None:
        return False
    return dmath.exp(center + hw) < _rail(owner, b, "min_grade") * geo.grade_median


def _propose_mine(run: AutoRun, owner: AreaOwner, project_id: int, data: GameData) -> None:
    """A permitted project's development decision: the smallest mine the study allows, a
    one-off proposal with the study's mid NPV as its central case."""
    from tst.sim.mining import actions as mine_actions
    from tst.sim.mining import formulas as mine_formulas
    from tst.sim.mining.actions import BuildMine

    state, b = run.state, run.balance
    p = next((x for x in state.projects if x.id == project_id), None)
    if p is None or any(m.project_id == project_id for m in state.mines):
        return
    try:
        design = mine_actions.design_capacity_t(p) / b.exploration.feasibility.life_years
        capacity = mine_formulas.capacity_bounds(design, b.mining)[0]
        q = mine_actions.quote(state, p, capacity, b, data)
    except (SimError, AssertionError):
        return
    # money-exact: display
    npv = (p.npv_mid_cents or 0) / 100
    run.text = (
        f"build a {capacity:,.0f} t a year mine at project #{p.id} (study NPV mid ${npv:,.0f})"
    )
    run.central = p.npv_mid_cents
    run.propose(BuildMine(owner.person_id, p.id, capacity), q.estimate_cents, "it is a one-off")
    run.central = None


# --- Mines and refineries (40.7; M27b sub-task 5) -----------------------------------------------


def _plant_kinds(b: Balance) -> set[str]:
    return {r.kind for r in b.refining.recipes.values()} - {"fab", "wafer_plant"}


def _group_buyer(state: GameState, mine: Mine, b: Balance, data: GameData) -> int | None:
    """A group company other than the mine's that needs its product: one with a live plant
    whose input is the mine commodity's concentrate (36.1), or that uses the good, the
    player's company first."""
    from tst.sim.commodities import costs
    from tst.sim.refining.plants import live_refineries, recipe_of

    commodity = mine.commodity
    owner = mine.company_id
    group = group_of(state)
    needs: set[int] = set()
    for ref, facility in live_refineries(state):
        if facility.company_id not in group or facility.company_id == owner:
            continue
        r = recipe_of(ref, b)
        spec = b.refining.goods.get(r.input_good) if r.input_good else None
        if spec is not None and spec.source == commodity:
            needs.add(facility.company_id)
    if data.commodities is not None:
        for cid in group:
            if cid != owner and costs.company_use(state, cid, b, data).get(commodity, 0.0) > EPS:
                needs.add(cid)
    if not needs:
        return None
    return state.player.id if state.player.id in needs else min(needs)


def mines(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Mines and refineries: staffed to their need; each mine at the safety guardrail
    (default normal, 35.3); output routed to the group's needs first (cost plus, 31.6), then
    contracts for the uncommitted volume, then spot. Closures, sales and expansions are
    one-offs. Mistake: routing a month late."""
    from tst.sim.mining.actions import SetMineSafety, SetMineSales, SignMineSale
    from tst.sim.mining.config import SAFETY

    b = run.balance
    company = owner.company_id
    kinds = _plant_kinds(b) | {"mine"}
    _staff(run, owner, lambda k: k in kinds, data)
    rail = int(_rail(owner, b, "safety"))  # an index into mining's levels: 1 = normal
    safety = SAFETY[max(0, min(len(SAFETY) - 1, rail))]
    for m in sorted(run.state.mines, key=lambda m: m.id):
        state = run.state
        if m.company_id != company or not m.is_open:
            continue
        if m.safety != safety:
            _act(
                run,
                owner,
                SetMineSafety(owner.person_id, m.id, safety),
                f"set mine #{m.id}'s safety to {safety}",
                False,
            )
        buyer = _group_buyer(run.state, m, b, data)
        if buyer is not None and m.buyer_id != buyer:
            if _late(run, owner, f"mine #{m.id}'s routing"):
                name = run.state.company(buyer).name
                _act(
                    run,
                    owner,
                    SetMineSales(owner.person_id, m.id, buyer, "cost_plus"),
                    f"routed mine #{m.id}'s output to {name} at cost plus",
                    False,
                )
            continue
        if buyer is None and m.buyer_id is None and m.status == "producing":
            committed = sum(
                d.volume_t_year
                for d in state.mine_deals
                if d.mine_id == m.id and d.end_turn >= state.turn
            )
            free = m.capacity_t * _rail(owner, b, "contract_share") - committed
            if free > EPS and _late(run, owner, f"mine #{m.id}'s sales contract"):
                _act(
                    run,
                    owner,
                    SignMineSale(owner.person_id, m.id, "contract", free, months=MONTHS_A_YEAR),
                    f"contracted {free:,.0f} t a year of mine #{m.id}'s output",
                    False,
                )


# --- Fabs and foundry customers (40.7; M27b sub-task 6) -----------------------------------------


def fabs(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Wafer starts go to own and group demand first (the engine's allocation, 38.2); spare
    starts go under foundry contracts at the most each designer pays (the node's slot price,
    as the fab card shows), if that is at or above the margin guardrail over the cost a start,
    up to the player's cap on the contracted share, a designer up to its share (M23a); the rest
    sells at spot. The margin is over the cash cost a start (`cash_cost_per_start`). Fabs and
    wafer plants are staffed. Upgrades, conversions and new nodes are one-offs. Mistake: a
    contract 20% under the best price."""
    from tst.sim.contracts import termination as ct
    from tst.sim.fabs import foundry as fc
    from tst.sim.fabs import market as fm
    from tst.sim.fabs.foundry import SignFoundryContract

    b = run.balance
    fb = b.contracts.foundry
    company = owner.company_id
    _staff(run, owner, lambda k: k in ("fab", "wafer_plant"), data)
    margin = _rail(owner, b, "margin")
    share = min(_rail(owner, b, "contracted_share"), fb.max_share)
    for facility in sorted(run.state.company_facilities(company), key=lambda f: f.id):
        if facility.kind != "fab" or facility.status != "live":
            continue
        state = run.state
        fab = fm.fab_of(state, facility.id)
        if fab is None or fab.month is None:
            continue
        cap = float(facility.capacity)
        own = fab.month.own
        cost = cash_cost_per_start(fab.month)
        for customer in fc.customers(data):
            state = run.state
            running = fc.running(state, facility.id)
            total = sum(c.monthly_starts for c in running)
            theirs = sum(c.monthly_starts for c in running if c.customer == customer)
            room = min(cap * share, cap - own) - total
            starts = math.floor(min(cap * fb.customer_share - theirs, room))
            if starts < 1:
                continue
            best = (
                # money-exact: rate
                fc.slot_price_cents(state, fab, b, data)
                * fb.max_price
                / float(ct.premium(state, customer, b))
            )
            best *= 1 - EPS
            # money-exact: estimate: a price floor only compared, never posted
            if best < cost * (1 + margin):
                continue
            right = _right(run, owner)
            price = best if right else best * (1 - b.automation.mistake_off)
            months = int(fb.months.hi)
            text = (
                f"contracted {starts:,} starts a month of fab #{facility.id} to {customer} "
                f"at ${price / 100:,.0f}"
            )
            _act(
                run,
                owner,
                SignFoundryContract(owner.person_id, facility.id, customer, starts, months, price),
                text,
                not right,
            )


def cash_cost_per_start(month: FabMonth) -> float:
    """The fab card's cost a start less depreciation (sunk: the spot slots that take the rest
    pay less than any contract), over the starts it ran last month."""
    run = month.own + month.sold + month.contracted
    cash = month.fixed_cents + month.materials_cents + month.power_cents + month.staff_cents
    # money-exact: rate: a unit price in float cents, rounded where posted
    return cash / max(1.0, run)


# --- Government affairs (40.7; M27b sub-task 7) -------------------------------------------------


def blocked(state: GameState, company: int, b: Balance, data: GameData) -> list[tuple[int, str]]:
    """(product, country) pairs where a licence could open a blocked sale (39)."""
    from tst.sim.geopolitics import world
    from tst.sim.geopolitics.actions import licence_rules
    from tst.sim.geopolitics.sales import restricting

    if not world.enabled(data):
        return []
    out = []
    for p in state.company_products(company):
        if p.status not in SELLING or not restricting(state, p, b, data):
            continue
        for c in world.countries_of(data).countries:
            if licence_rules(state, p.id, c.key, b, data):
                out.append((p.id, c.key))
    return out


def government(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Lobbying by region within the yearly budget the player sets (split evenly over the
    regions where the company sells, at the budget's monthly rate); licence applications
    for blocked sales and tools; a compliant variant proposed (a product decision). Taking a
    local partner and the grey route stay one-offs, and a delegate never takes the grey route.
    Mistake: a month late."""
    from tst.sim.actions.founder import SetLobbying
    from tst.sim.geopolitics.actions import LaunchVariant, RequestLicence, is_variant_product

    state, b = run.state, run.balance
    company = owner.company_id
    found = blocked(state, company, b, data)
    if found and not _late(run, owner, "the licence applications"):
        return
    asked: set[int] = set()
    for pid, country in found:
        product = run.state.product(pid)
        name = product.name if product else f"#{pid}"
        _act(
            run,
            owner,
            RequestLicence(owner.person_id, pid, country),
            f"applied for a licence to sell {name} in {country}",
            False,
        )
        if (
            product is not None
            and pid not in asked
            and is_variant_product(product.category, b, data)
        ):
            asked.add(pid)
            run.text = f"launch a compliant variant of {name}"
            run.propose(LaunchVariant(owner.person_id, pid), 0, "it is a product decision")
    _tool_licences(run, owner, data)
    budget = owner.budget_cents
    if budget <= 0 or company != run.state.player.id:
        return
    regions = sorted(
        {r.region for p in run.state.company_products(company) for r in run.state.regions_of(p.id)}
        | {b.founder.default_region}
    )
    dollars = budget // MONTHS_A_YEAR // len(regions) // PCT
    from tst.sim.state import influence_of

    for region in regions:
        record = influence_of(run.state, company, region)
        now = record.spend_cents if record is not None else 0
        if now == dollars * PCT:
            continue
        _act(
            run,
            owner,
            SetLobbying(owner.person_id, region, dollars),
            f"set lobbying in {data.region(region).label} to ${dollars:,} a month",
            False,
        )


def _tool_licences(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """A tool licence for each country the company's fabs sit in, where a biting licence rule
    covers their tools (the action refuses where none is needed or one is pending)."""
    from tst.sim.geopolitics import world
    from tst.sim.geopolitics.fabs import RequestToolLicence

    state = run.state
    if not world.enabled(data):
        return
    fabs = [f for f in state.company_facilities(owner.company_id) if f.kind == "fab"]
    for country in sorted({world.facility_country(state, f, data) for f in fabs}):
        _act(
            run,
            owner,
            RequestToolLicence(owner.person_id, country),
            f"applied for a tool licence in {country}",
            False,
        )


# --- Corporate development (40.7; M27b sub-task 8) ----------------------------------------------


def corp_targets(
    state: GameState, company: int, balances: object, b: Balance, data: GameData
) -> list[tuple[float, int, int]]:
    """Affordable independent rivals sharing a category with the company's selling products,
    ranked by customers in those categories per dollar of displayed value (28.1), best
    first: (score, target id, estimate)."""
    from tst.sim.mna import deals

    cash = account_balance(balances, company, CASH)  # type: ignore[arg-type]
    mine = {p.category for p in state.company_products(company) if p.status in SELLING}
    out = []
    for c in state.companies:
        if not c.is_rival or not c.alive or c.parent_id is not None or c.id == company:
            continue
        if deals.open_deal(state, c.id) is not None:
            continue
        theirs = [
            p for p in state.company_products(c.id) if p.status in SELLING and p.category in mine
        ]
        if not theirs:
            continue
        try:
            estimate = deals.estimate_cents(state, company, c.id, balances, b, data)  # type: ignore[arg-type]
        except (SimError, KeyError, ZeroDivisionError):
            continue
        if estimate <= 0 or estimate > cash:
            continue
        customers = sum(s.customers for p in theirs for s in state.segments_of(p.id))
        # money-exact: ratio: customers a cent, only ranked
        out.append((customers / estimate, c.id, estimate))
    out.sort(key=lambda t: (-t[0], t[1]))
    return out


def corp_dev(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """Each quarter, within the yearly screening budget the player sets (0: off), diligence
    on the best target not yet screened (StartDiligence), and a bid at the diligenced
    displayed range's midpoint pitched as a proposal (every bid is a one-off), with the range
    in its text. Mistake: the second-best target."""
    from tst.sim.mna import formulas as mf
    from tst.sim.mna import valuation
    from tst.sim.mna.deals import BidForCompany, StartDiligence
    from tst.sim.state import target_file

    state, b = run.state, run.balance
    company = owner.company_id
    if state.turn % MONTHS_A_QUARTER != 0 or owner.budget_cents <= 0:
        return
    spent = sum(
        d.commitment_cents
        for d in state.area_decisions
        if d.company_id == company
        and d.area == "corp_dev"
        and d.kind in ("decision", "mistake")
        and d.turn > state.turn - MONTHS_A_YEAR
    )
    ranked = corp_targets(state, company, run.balances, b, data)
    if not ranked:
        return

    def done(tid: int) -> bool:
        f = target_file(state, company, tid)
        return (
            f is not None
            and f.diligence_done_turn is not None
            and f.diligence_done_turn <= state.turn
        )

    def started(tid: int) -> bool:
        f = target_file(state, company, tid)
        return f is not None and f.diligence_turn is not None

    screened = [t for t in ranked if done(t[1]) and not _bid_asked(state, company, t[1], b)]
    if screened:
        _, tid, _ = screened[0]
        lo, hi = valuation.value_range_cents(state, tid, run.balances, b, data, diligenced=True)
        mid = mf.midpoint_cents((lo, hi))
        name = state.company(tid).name
        run.text = (
            f"bid ${mid / 100:,.0f} for {name} (displayed value ${lo / 100:,.0f}-${hi / 100:,.0f})"
        )
        run.propose(BidForCompany(owner.person_id, tid, mid), mid, "it is a one-off")
    fresh = [t for t in ranked if not started(t[1])]
    if not fresh:
        return
    (_, tid, estimate), mistake = _pick(run, owner, fresh)
    cost = mf.diligence_cost_cents(estimate, b.mna)
    if spent + cost > owner.budget_cents:
        return
    _act(
        run,
        owner,
        StartDiligence(owner.person_id, tid),
        f"began diligence on {state.company(tid).name}",
        mistake,
    )


def _bid_asked(state: GameState, company: int, target_id: int, b: Balance) -> bool:
    """A bid for the target already waits, or was declined or expired within
    automation.repropose_months (40.2)."""
    import json

    from tst.sim.automation import scope

    quiet = b.automation.repropose_months
    for p in state.proposals:
        if p.kind != "auto" or scope.acting_for(p) != company:
            continue
        action = json.loads(str(dict(p.params).get("action", "{}")))
        if action.get("kind") != "bid_for_company" or action.get("target_id") != target_id:
            continue
        if p.status in ("pending", "approved") or (p.resolved_turn or p.turn) > state.turn - quiet:
            return True
    return False


def relevant(state: GameState, company: int, area: str, b: Balance, data: GameData) -> bool:
    """A chain area has something to run in the company now (Automate everything hands out
    only these, so it does not spend the founder's energy on idle areas)."""
    from tst.sim.chips import chips

    facilities = {f.kind for f in state.company_facilities(company) if f.status != "closed"}
    selling = [p for p in state.company_products(company) if p.status in SELLING]
    match area:
        case "production":
            return bool(device_products(state, company, b)) or b.hardware.plant_kind in facilities
        case "supply":
            return bool(supply_needs(state, company, b, data)) or any(
                chips.is_chip(p, data) for p in selling
            )
        case "exploration":
            return any(s.company_id == company for s in state.desk_studies) or any(
                p.company_id == company and p.status in ("active", "permitted")
                for p in state.projects
            )
        case "mines":
            return any(m.company_id == company and m.is_open for m in state.mines) or bool(
                facilities & _plant_kinds(b)
            )
        case "fabs":
            return bool(facilities & {"fab", "wafer_plant"})
        case "government":
            return "fab" in facilities or bool(blocked(state, company, b, data))
        case "corp_dev":
            return any(f.acquirer_id == company for f in state.target_files) or any(
                d.acquirer_id == company for d in state.deals
            )
    return True


RULES: dict[str, Callable[[AutoRun, AreaOwner, GameData], None]] = {
    "production": production,
    "supply": supply,
    "exploration": exploration,
    "mines": mines,
    "fabs": fabs,
    "government": government,
    "corp_dev": corp_dev,
}
