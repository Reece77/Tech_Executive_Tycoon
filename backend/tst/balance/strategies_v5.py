"""The v5 scripted strategies (M43 sub-task 4). Like the v1-v4 scripts they act only through
`Game.act`, so every rule applies, and they read only what a player sees (quotes, the build
screens' rows, approvals and clearances), never a hidden draw. Their numbers describe the
scripts, not the game, so they live here rather than in balance.yaml.

- **ev_integrator** (49): full_integrator (devices, its own SoC, lithium, a fab) and, from cars'
  first month (`vehicles.start`, 2026) once cash covers it, a car line: an LFP car at 0.9x the
  reference price on a contract manufacturer in San Francisco (as M38's maker), $1M a month of
  marketing; from stage 4 its own LFP cell plant in North America sized to the line, the car
  switched to own cells once the plant runs.
- **robotics_first** (53): devices_regions and, from robotics' first month (2026), an industrial
  robot line sold to the three industries on a contract manufacturer; a humanoid line once the
  humanoid market opens (its era); from 2026 an autonomy research unit and an AI model, and a
  robotaxi service with a depot and cars in San Francisco once its research and model reach L4.
- **life_sciences** (50): devices_regions and, from 2024 once cash covers it, a wearable
  (arrhythmia detection) and then a radiology triage SaMD, each designed, filed with the FDA and
  the EU at once, given clinical education and post-market surveillance, and asked for coverage
  as soon as it is cleared; from 2026 pharma with AI discovery (pharma_step: M42's sensible
  company, a programme every six months while fewer than six are in development).
- **cloud_first** (22, 46): hosting as the main business: from the first month cash covers it,
  the smallest general data centre in the home region; its capacity sold as cloud hosting
  (0.9x the reference price, marketing 5% of the product's revenue, at least $50,000 a month);
  a new data centre whenever sold and own CU pass 80% of what is built, sized to the gap; from
  stage 4 sited by power with a plant behind the meter when it would queue (power_hyperscaler's
  siting). **cloud_first_grid** is the same company on the grid only: T1's comparison, so the
  ratio measures power directly (M35b's follow-up).
- **dynasty** (52): any of the above played to December 2069 with a family (M37's dynasty runs).

- **space_and_defence** (56, 57): devices_regions (devices and its own SoC), then from 2026 a
  satellite broadband line, its own satellite plant and a four-shell constellation (M40's: 300 kg
  satellites, a 5-year life, launches bought, insured), licensed in every region but East Asia;
  and government bids in devices, chips and space on every announced tender open to it, at 0.9x
  the tender's value with a capture team, six engineers and the plant asked for Top Secret
  (M44's bidder).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final

from tst.balance.game import PLAYER, Game
from tst.balance.strategies import Strategy
from tst.balance.strategies_v2 import (
    DC_KIND,
    DC_ROLE,
    _unit,
    refill_energy,
    staff_unit,
    steady_regions,
)
from tst.balance.strategies_v3 import (
    CONTRACT_MONTHS,
    RENEW_BEFORE,
    UNITS_HEADROOM,
    _facilities,
    _mark,
    _product,
    _staff_plants,
    _units_sold,
    devices_regions,
    full_integrator,
    ready_for,
)
from tst.balance.strategies_v4 import CLOUD_PRICE, _plant_for, _sited
from tst.sim.actions import AssignUnit, CreateProduct, SetMarketing, SetPrice
from tst.sim.actions.events import ChooseEvent
from tst.sim.actions.facilities import BuildFacility, SellCapacity, StaffFacility
from tst.sim.actions.hardware import SignManufacturingContract
from tst.sim.actions.research import StartProject
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities import compute, lifecycle
from tst.sim.government.actions import PlaceBid, RequestClearance, SponsorFacilityClearance
from tst.sim.medical import coverage
from tst.sim.medical import data as md
from tst.sim.medical.actions import DesignDevice, RequestCoverage, SetMedicalSupport, SubmitDevice
from tst.sim.pharma import pipeline
from tst.sim.pharma.actions import FileDrug, StartProgramme, StartTrial, StopProgramme
from tst.sim.power import plants, siting
from tst.sim.power.actions import BuildPlant
from tst.sim.robotics import robotaxi as rt
from tst.sim.robotics.actions import AddRobotaxis, BuildDepot, OpenZone, SetHumanoidSpec
from tst.sim.space.actions import ApplyLicence, PlanConstellation
from tst.sim.vehicles.actions import BuildCellPlant, SetVehicleSpec

# --- A unit-sale line on a contract (cars, robots, medical devices) ----------------------------


@dataclass(frozen=True, slots=True)
class Line:
    name: str
    category: str
    segments: tuple[str, ...]
    price: float  # x each segment's reference price
    team: str
    role: str
    staff: int
    units: int  # the first contract's units a month
    city: str  # where the contract manufacturer makes it
    start: int  # the first month it may start
    cash_cents: int  # cash (x2, ready_for) before it starts
    marketing_cents: int = 0  # a month, from launch
    maker: str = "foxconn"


def _make(game: Game, line: Line) -> int | None:
    uid = _unit(game, line.team)
    pid = game.state.next_ids.product
    if uid is None:
        return None
    refill_energy(game)
    if not game.act(CreateProduct(game.founder_id, line.name, line.category, line.segments)):
        return None
    cat = game.loaded.game_data.category(line.category)
    for segment in line.segments:
        ref = cat.market(segment).reference_price_cents
        game.act(SetPrice(game.founder_id, pid, segment, round(ref * line.price)))
    game.act(AssignUnit(game.founder_id, pid, uid))
    return pid


def _live(game: Game, pid: int | None) -> bool:
    p = game.state.product(pid) if pid is not None else None
    return p is not None and p.status in ("live", "sunset")


def line_step(game: Game, line: Line) -> int | None:
    """The line's team and product once its month has come and cash covers it, its marketing
    from launch, and a manufacturing contract whenever none runs (or the last ends within two
    months), sized to last month's units. Returns the product's id."""
    pid = _product(game, line.category)
    if pid is None:
        if game.state.turn < line.start or not ready_for(game, line.cash_cents):
            return None
        pid = _make(game, line)
        if pid is None:
            return None
        _mark(game, line.category)
    staff_unit(game, line.team, line.role, line.staff)
    product = game.state.product(pid)
    if product is None:
        return None
    if (
        line.marketing_cents
        and _live(game, pid)
        and product.marketing_budget_cents < (line.marketing_cents)
    ):
        game.act(SetMarketing(game.founder_id, pid, line.marketing_cents))
    contracts = [
        c
        for c in game.state.production_contracts
        if c.product_id == pid and c.kind == "assembly" and c.end_turn >= game.state.turn
    ]
    due = not contracts or max(c.end_turn for c in contracts) - game.state.turn < RENEW_BEFORE
    if due:
        cap = game.loaded.balance.hardware.contract.max_units
        units = min(cap, max(line.units, round(_units_sold(game, pid) * UNITS_HEADROOM)))
        refill_energy(game)
        game.act(
            SignManufacturingContract(
                game.founder_id, pid, line.maker, line.city, units, CONTRACT_MONTHS
            )
        )
    return pid


# --- Budgets: a new line is funded from its own budget ------------------------------------------

LINE_BUDGETS: dict[str, int] = {}  # category -> cents a month, filled below from each line


def fund_lines(game: Game) -> None:
    """A v5 line's marketing is its own budget, and steady's 20% of revenue is split over the
    other products only (rule 2: steady splits one budget equally over every product, so a car
    line took a share of every app's marketing; M43 measured -$2.6B of app revenue on seed 3)."""
    from tst.balance.strategies import STEADY_MARKETING, STEADY_MARKETING_MIN, last_revenue

    products = [p for p in game.state.company_products(PLAYER) if p.status != "retired"]
    own = [p for p in products if p.category in LINE_BUDGETS]
    if not own:
        return
    rest = [p for p in products if p.category not in LINE_BUDGETS]
    share = max(STEADY_MARKETING_MIN, round(STEADY_MARKETING * last_revenue(game) / len(rest)))
    targets = [(p, share) for p in rest] + [(p, LINE_BUDGETS[p.category]) for p in own]
    for p, cents in targets:
        if p.marketing_budget_cents != cents:
            refill_energy(game)
            game.act(SetMarketing(game.founder_id, p.id, cents))


# --- ev_integrator ------------------------------------------------------------------------------

CAR: Final = Line(
    name="Volta One",
    category="vehicles",
    segments=("consumer",),
    price=0.9,  # M38's maker
    team="Car team",
    role="hardware_engineer",
    staff=20,  # M38's maker
    units=3_000,  # M38's contract
    city="san_francisco",
    start=ym_to_turn(2026, 1),  # vehicles.start (checked in tests)
    cash_cents=50_000_000_000,  # $500M (x2) before a car line
    marketing_cents=100_000_000,  # $1M a month (M38's maker)
)
PACK_KWH: Final = 60.0  # M38's car
CHARGE_KW: Final = 150.0
CELL_REGION: Final = "north_america"
CELL_MWH: Final = 100  # the smallest plant: about 1,600 cars of 60 kWh a month (M38)
CELL_STAGE: Final = 4  # vehicles.cell_plant.stage
CELL_CASH_MULT: Final = 1.3  # the plant's quote x this in cash (its overrun is hidden)
CELL_ROLE: Final = "process_engineer"  # M38's crew
BOUGHT_CELLS: Final = "catl"


def _spec(game: Game, pid: int, cells: str) -> None:
    key = f"cells:{cells}"
    if key in game.notes:
        return
    refill_energy(game)
    if game.act(
        SetVehicleSpec(game.founder_id, pid, PACK_KWH, "lfp", CHARGE_KW, "l2", "licensed", cells)
    ):
        game.notes[key] = game.state.turn
        _mark(game, key)


def _cell_plant_live(game: Game) -> bool:
    turn = game.state.turn
    return any(f.live_capacity(turn) > 0 for f in _facilities(game, "cell_plant"))


def car_step(game: Game) -> None:
    pid = line_step(game, CAR)
    if pid is None:
        return
    _spec(game, pid, "own" if _cell_plant_live(game) else BOUGHT_CELLS)
    if not _facilities(game, "cell_plant") and game.state.player.stage >= CELL_STAGE:
        b, g = game.loaded.balance, game.loaded.game_data
        q = lifecycle.quote(game.state, PLAYER, "cell_plant", CELL_REGION, CELL_MWH, b, g)
        if ready_for(game, round(q.capex_cents * CELL_CASH_MULT)):
            refill_energy(game)
            if game.act(BuildCellPlant(game.founder_id, CELL_REGION, CELL_MWH, "lfp")):
                _mark(game, "cell_plant")
    _staff_plants(game, "cell_plant", CELL_ROLE, "Cell crew")


LINE_BUDGETS[CAR.category] = CAR.marketing_cents


def ev_integrator(game: Game) -> None:
    """full_integrator with a car line from 2026 on its own cells from stage 4."""
    full_integrator(game)
    car_step(game)
    fund_lines(game)


# --- robotics_first -----------------------------------------------------------------------------

ROBOT: Final = Line(
    name="Arm One",
    category="industrial_robots",
    segments=("automotive", "electronics", "general_industry"),
    price=0.9,
    team="Robot team",
    role="hardware_engineer",
    staff=16,
    units=200,
    city="shenzhen",
    start=ym_to_turn(2026, 1),  # robotics.start (checked in tests)
    cash_cents=10_000_000_000,  # $100M (x2)
    marketing_cents=20_000_000,  # $200k a month
)
HUMANOID: Final = Line(
    name="Atlas Home",
    category="humanoid_robots",
    segments=(),  # the category's open segments (set when it is made)
    price=0.9,
    team="Humanoid team",
    role="hardware_engineer",
    staff=20,
    units=200,
    city="shenzhen",
    start=ym_to_turn(2026, 1),
    cash_cents=20_000_000_000,  # $200M (x2)
    marketing_cents=50_000_000,  # $500k a month
)
AUTONOMY_UNIT: Final = "Autonomy research"
AUTONOMY_ROLE: Final = "data_scientist"  # ml_research weighs most (tech_frontier.yaml)
AUTONOMY_STAFF: Final = 30
AUTONOMY_FROM: Final = ym_to_turn(2026, 1)
AI_MODEL: Final = ("Pilot", "ai_models", ("mid_market", "enterprise"))
AI_RESEARCH_UNIT: Final = "AI research"  # L4 needs an AI model of quality 80 (vehicles.levels)
AI_RESEARCH_STAFF: Final = 20
AI_STAGE: Final = 3  # the AI model's team starts at this stage
AI_CASH_CENTS: Final = 5_000_000_000  # $50M (x2, ready_for), as the device line
AI_TEAM: Final = "AI team"
AI_STAFF: Final = 12
MOBILITY: Final = ("Volta Ride", "mobility", ())
ZONE_CITY: Final = "san_francisco"
ZONE_SIZE: Final = "large"  # M39's zone
DEPOT_CARS: Final = 300  # M39's depot
FLEET: Final = 300  # cars, as M39's larger run


def _segments(game: Game, category: str) -> tuple[str, ...]:
    return tuple(m.segment for m in game.loaded.game_data.category(category).markets)


def _research(game: Game, unit: str, role: str, staff: int, domain: str) -> None:
    uid = staff_unit(game, unit, role, staff)
    if uid is None:
        return
    active = [
        p
        for p in game.state.research_projects
        if p.company_id == PLAYER and p.status == "active" and p.unit_id == uid
    ]
    if not active and any(e.unit_id == uid for e in game.state.staff(PLAYER)):
        refill_energy(game)
        game.act(StartProject(game.founder_id, uid, domain))


def _ai_model(game: Game) -> int | None:
    pid = _product(game, AI_MODEL[1])
    if pid is not None:
        staff_unit(game, AI_TEAM, "data_scientist", AI_STAFF)
        return pid
    uid = _unit(game, AI_TEAM)
    if uid is None:
        return None
    pid = game.state.next_ids.product
    name, category, segments = AI_MODEL
    refill_energy(game)
    if not game.act(CreateProduct(game.founder_id, name, category, segments)):
        return None
    cat = game.loaded.game_data.category(category)
    for s in segments:
        game.act(SetPrice(game.founder_id, pid, s, cat.market(s).reference_price_cents))
    game.act(AssignUnit(game.founder_id, pid, uid))
    return pid


def _robotaxis(game: Game) -> None:
    b = game.loaded.balance
    if not rt.can_drive_l4(game.state, PLAYER, b):
        return
    pid = _product(game, MOBILITY[1])
    if pid is None:
        name, category, segments = MOBILITY
        pid = game.state.next_ids.product
        refill_energy(game)
        if not game.act(CreateProduct(game.founder_id, name, category, segments)):
            return
        _mark(game, "mobility")
    if not _live(game, pid):
        return
    if "depot" not in game.notes:
        refill_energy(game)
        if game.act(BuildDepot(game.founder_id, ZONE_CITY, DEPOT_CARS)):
            game.notes["depot"] = game.state.turn
    zone = next((z for z in game.state.zones if z.company_id == PLAYER), None)
    if zone is None:
        refill_energy(game)
        if game.act(OpenZone(game.founder_id, pid, ZONE_CITY, ZONE_SIZE)):
            _mark(game, "zone")
        return
    if "fleet" not in game.notes and zone.status in ("applied", *rt.OPEN):
        refill_energy(game)
        if game.act(AddRobotaxis(game.founder_id, zone.id, FLEET)):
            game.notes["fleet"] = game.state.turn


LINE_BUDGETS[ROBOT.category] = ROBOT.marketing_cents
LINE_BUDGETS[HUMANOID.category] = HUMANOID.marketing_cents


def robotics_first(game: Game) -> None:
    """devices_regions, then industrial robots from 2026, humanoids once their market opens, and
    robotaxis once its own autonomy research and AI model reach L4. The AI model starts at stage 3
    once cash covers it: a new model takes years to reach launch quality."""
    devices_regions(game)
    if game.state.player.stage >= AI_STAGE and (
        _product(game, AI_MODEL[1]) is not None or ready_for(game, AI_CASH_CENTS)
    ):
        _ai_model(game)
    if line_step(game, ROBOT) is None:
        return
    hid = line_step(game, replace(HUMANOID, segments=_segments(game, HUMANOID.category)))
    if game.state.turn >= AUTONOMY_FROM:
        _research(game, AUTONOMY_UNIT, AUTONOMY_ROLE, AUTONOMY_STAFF, "autonomy")
        _research(game, AI_RESEARCH_UNIT, "data_scientist", AI_RESEARCH_STAFF, "ai")
        ai = _ai_model(game)
        if _live(game, hid) and _live(game, ai) and "humanoid_spec" not in game.notes:
            refill_energy(game)
            if hid is not None and game.act(
                SetHumanoidSpec(game.founder_id, hid, ai_product_id=ai)
            ):
                game.notes["humanoid_spec"] = game.state.turn
        _robotaxis(game)
    fund_lines(game)


# --- life_sciences ------------------------------------------------------------------------------

WEARABLE: Final = Line(
    name="Pulse",
    category="wearables_diagnostics",
    segments=("consumer",),
    price=1.0,
    team="Medical devices",
    role="hardware_engineer",
    staff=12,
    units=20_000,
    city="shenzhen",
    start=ym_to_turn(2024, 1),
    cash_cents=5_000_000_000,  # $50M (x2)
    marketing_cents=20_000_000,
)
WEARABLE_USE: Final = "arrhythmia_detection"
SAMD: Final = ("Read", "samd", "radiology_triage")
SAMD_TEAM: Final = "Clinical AI"
SAMD_STAFF: Final = 8
TRAINING_CENTS: Final = 5_000_000  # $50k a month of clinical education (M41's entrant)
COVERAGE_REGIONS: Final = ("north_america", "europe")


def _file(game: Game, pid: int, use: str) -> None:
    """Design, then file with the FDA and the EU at once, support it, and ask for coverage as
    soon as it is cleared (M41's sensible entrant)."""
    f = game.founder_id
    key = f"filed:{pid}"
    if key not in game.notes:
        refill_energy(game)
        if not game.act(DesignDevice(f, pid, use)):
            return
        game.act(SetMedicalSupport(f, pid, TRAINING_CENTS, True))
        game.act(SubmitDevice(f, pid, md.FDA))
        game.act(SubmitDevice(f, pid, md.EU))
        game.notes[key] = game.state.turn
    d = game.loaded.game_data
    for region in COVERAGE_REGIONS:
        c = coverage.coverage_of(game.state, pid, region)
        if (c is None or c.status == "denied") and coverage.cleared_in(game.state, pid, region, d):
            refill_energy(game)
            game.act(RequestCoverage(f, pid, region))


LINE_BUDGETS[WEARABLE.category] = WEARABLE.marketing_cents
LINE_BUDGETS[SAMD[1]] = WEARABLE.marketing_cents  # clinical AI, as the wearable


def life_sciences(game: Game) -> None:
    """devices_regions, then medical devices from 2024: a wearable, then clinical AI."""
    devices_regions(game)
    pid = line_step(game, WEARABLE)
    if pid is None:
        return
    _file(game, pid, WEARABLE_USE)
    name, category, use = SAMD
    sid = _product(game, category)
    if sid is None:
        if not ready_for(game, WEARABLE.cash_cents):
            return
        uid = _unit(game, SAMD_TEAM)
        sid = game.state.next_ids.product
        refill_energy(game)
        if uid is None or not game.act(
            CreateProduct(game.founder_id, name, category, _segments(game, category))
        ):
            return
        cat = game.loaded.game_data.category(category)
        for m in cat.markets:
            game.act(SetPrice(game.founder_id, sid, m.segment, m.reference_price_cents))
        game.act(AssignUnit(game.founder_id, sid, uid))
        _mark(game, "samd")
    staff_unit(game, SAMD_TEAM, "software_engineer", SAMD_STAFF)
    _file(game, sid, use)
    _answer_medical(game)
    pharma_step(game)
    fund_lines(game)


PHARMA_FROM: Final = ym_to_turn(2026, 1)  # pharma.start (checked in tests)
PHARMA_CASH_CENTS: Final = 20_000_000_000  # $200M (x2, ready_for) before each new programme
PHARMA_ACTIVE: Final = 6  # programmes in development at once
PHARMA_GAP: Final = 6  # months between new programmes
INDICATIONS: Final = ("obesity", "type2_diabetes", "lung_cancer", "psoriasis_ibd", "lipids")
DRUG_REGULATORS: Final = ("fda_drugs", "ema")
IN_DEVELOPMENT: Final = ("active", "ready", "failed")
DISCOVERY_UNIT: Final = "Drug discovery"
DISCOVERY_ROLE: Final = "research_scientist"  # pharma.discovery.roles
DISCOVERY_STAFF: Final = 12


def pharma_step(game: Game) -> None:
    """Pharma with AI discovery from 2026 (55): a drug discovery research unit and an AI model
    (AI discovery opens once either is strong enough), a new small-molecule programme every six
    months while fewer than six are in development and cash covers it; each next trial at the
    standard design as soon as the last reads out; filed with the FDA and the EMA after Phase
    III; a failed readout or a second complete response letter stops it (M42's sensible
    company)."""
    if game.state.turn < PHARMA_FROM:
        return
    f = game.founder_id
    _research(game, DISCOVERY_UNIT, DISCOVERY_ROLE, DISCOVERY_STAFF, "drug_discovery")
    _ai_model(game)
    b, g = game.loaded.balance, game.loaded.game_data
    ai = pipeline.ai_ready(game.state, PLAYER, b, g)  # the screen shows whether it is open
    mine = [p for p in game.state.pharma_programmes if p.company_id == PLAYER]
    developing = [p for p in mine if p.status in IN_DEVELOPMENT]
    started = game.notes.get("pharma_last", -PHARMA_GAP)
    if (
        len(developing) < PHARMA_ACTIVE
        and game.state.turn - started >= PHARMA_GAP
        and ready_for(game, PHARMA_CASH_CENTS)
    ):
        indication = INDICATIONS[len(mine) % len(INDICATIONS)]
        refill_energy(game)
        if game.act(StartProgramme(f, f"Volta-{len(mine) + 1}", indication, "small_molecule", ai)):
            game.notes["pharma_last"] = game.state.turn
            _mark(game, "pharma")
    for p in developing:
        reviews = [r for r in game.state.pharma_reviews if r.programme_id == p.id]
        if any(r.status == "review" for r in reviews):
            continue
        refill_energy(game)
        crls = sum(1 for r in reviews if r.status == "crl")
        if p.status == "failed" or crls > 1:
            game.act(StopProgramme(f, p.id))
        elif p.status == "ready" and pipeline.next_trial(p) is not None:
            game.act(StartTrial(f, p.id))
        elif p.status == "ready":
            for regulator in DRUG_REGULATORS:
                done = [r for r in reviews if r.regulator == regulator]
                if not done or (all(r.status == "crl" for r in done) and len(done) < 2):
                    game.act(FileDrug(f, p.id, regulator))


def _answer_medical(game: Game) -> None:
    """A class I recall is answered with its first choice (M41's entrant)."""
    from tst.sim.medical import quality

    for event in game.state.open_events(PLAYER):
        if event.status == "open" and event.template_id == quality.CLASS_I_RECALL:
            game.act(ChooseEvent(game.founder_id, event.id, "A"))


# --- space_and_defence -------------------------------------------------------------------------

SPACE_FROM: Final = ym_to_turn(2026, 1)  # space.start (checked in tests)
SPACE_CASH_CENTS: Final = 100_000_000_000  # $1B (x2, ready_for) before the constellation
BROADBAND: Final = ("Orbit Broadband", "satellite_broadband")
BROADBAND_TEAM: Final = "Satellite team"
SAT_PLANT: Final = 25  # satellites a month (M40's constellation)
SAT_ROLE: Final = "manufacturing_engineer"
SHELLS: Final = 4  # M40's constellation: 300 kg satellites, a 5-year life, 25 built and 2
SAT_KG: Final = 300.0  # launches bought a month, insured
SAT_LIFE: Final = 60
SAT_BUILD: Final = 25
SAT_LAUNCHES: Final = 2
NO_LICENCE: Final = ("east_asia",)  # M40's script licenses every other region
CAPTURE_TEAM: Final = "Capture"
CAPTURE: Final = 3  # sellers on every capture team (M44's bidder)
CLEARED_TEAM: Final = "Cleared engineers"
CLEARED: Final = 6  # staff asked for Top Secret (M44's bidder)
BID_PRICE: Final = 0.9  # x the tender's value (M44's bidder)
BID_AREAS: Final = ("devices", "chips", "space")


def _space(game: Game) -> int | None:
    """The broadband line, its satellite plant, constellation and licences from 2026."""
    b, g = game.loaded.balance, game.loaded.game_data
    pid = _product(game, BROADBAND[1])
    if pid is None:
        if game.state.turn < SPACE_FROM or not ready_for(game, SPACE_CASH_CENTS):
            return None
        uid = _unit(game, BROADBAND_TEAM)
        pid = game.state.next_ids.product
        name, category = BROADBAND
        segments = tuple(s for s in _segments(game, category) if s != b.space.d2d_segment)
        refill_energy(game)
        if uid is None or not game.act(CreateProduct(game.founder_id, name, category, segments)):
            return None
        cat = g.category(category)
        for seg in segments:
            game.act(SetPrice(game.founder_id, pid, seg, cat.market(seg).reference_price_cents))
        game.act(AssignUnit(game.founder_id, pid, uid))
        _mark(game, "broadband")
    staff_unit(game, BROADBAND_TEAM, "hardware_engineer", 12)
    kind = b.space.plant_kind
    home = compute.home_region_of(game.state, b, g)
    if not _facilities(game, kind):
        refill_energy(game)
        if game.act(BuildFacility(game.founder_id, kind, home, SAT_PLANT)):
            _mark(game, "satellite_plant")
    _staff_plants(game, kind, SAT_ROLE, "Satellite plant crew")
    if not any(c.company_id == PLAYER for c in game.state.space.constellations):
        refill_energy(game)
        plan = PlanConstellation(
            game.founder_id,
            "Orbit",
            "broadband",
            pid,
            SHELLS,
            SAT_KG,
            SAT_LIFE,
            SAT_BUILD,
            SAT_LAUNCHES,
        )
        if game.act(plan):
            _mark(game, "constellation")
    held = {x.region for x in game.state.space.licences if x.company_id == PLAYER}
    for region in g.region_keys:
        if region not in held and region not in NO_LICENCE:
            refill_energy(game)
            game.act(ApplyLicence(game.founder_id, region))
    return pid


def _government(game: Game) -> None:
    """Bids on every announced tender open to it in its areas, at 0.9x the tender's value with
    a capture team, and Top Secret asked for six engineers and the satellite plant (M44)."""
    from tst.sim.government.data import announced, area_of, file
    from tst.sim.government.sourcing import requirements

    if game.state.turn < SPACE_FROM:
        return
    b, g = game.loaded.balance, game.loaded.game_data
    staff_unit(game, CAPTURE_TEAM, "account_executive", CAPTURE)
    cleared_uid = staff_unit(game, CLEARED_TEAM, "hardware_engineer", CLEARED)
    team = tuple(
        e.person_id for e in game.state.staff(PLAYER) if e.unit_id == _unit(game, CAPTURE_TEAM)
    )
    if "clearances" not in game.notes and cleared_uid is not None:
        people = tuple(e.person_id for e in game.state.staff(PLAYER) if e.unit_id == cleared_uid)
        if len(people) >= CLEARED:
            refill_energy(game)
            if game.act(RequestClearance(game.founder_id, people, "top_secret")):
                game.notes["clearances"] = game.state.turn
    plant = next(iter(_facilities(game, game.loaded.balance.space.plant_kind)), None)
    if plant is not None and "facility_clearance" not in game.notes:
        refill_energy(game)
        if game.act(SponsorFacilityClearance(game.founder_id, plant.id)):
            game.notes["facility_clearance"] = game.state.turn
    products = {
        area_of(p, g): p.id
        for p in game.state.company_products(PLAYER)
        if p.status == "live" and area_of(p, g) in BID_AREAS
    }
    f = file(g)
    bid_on = {x.tender_id for x in game.state.gov_bids if x.company_id == PLAYER}
    turn = game.state.turn
    for t in game.state.tenders:
        pid = products.get(t.area)
        if pid is None or t.id in bid_on or t.status != "open" or turn >= t.close_turn:
            continue
        if not announced(t, turn) or "us_aligned" not in f.government(t.government).open_to:
            continue
        product = game.state.product(pid)
        if requirements(game.state, game.state.player, product, t, b, g):
            continue  # the tender's page lists what it needs: cleared staff, a cleared site
        refill_energy(game)
        if game.act(PlaceBid(game.founder_id, t.id, pid, round(t.value_cents * BID_PRICE), team)):
            _mark(game, "bid")


BROADBAND_MARKETING: Final = 50_000_000  # $500k a month: the constellation's own budget
LINE_BUDGETS[BROADBAND[1]] = BROADBAND_MARKETING


def space_and_defence(game: Game) -> None:
    """devices_regions (its devices and own SoC), then from 2026 a broadband constellation from
    its own satellite plant, and government bids in devices, chips and space."""
    devices_regions(game)
    _space(game)
    _government(game)
    fund_lines(game)


# --- cloud_first --------------------------------------------------------------------------------

FILL: Final = 0.8  # build when sold and own CU pass this share of what is built
GROW: Final = 1.5  # ... sized to this x the CU in use, less what is built
CLOUD_SHARE: Final = 0.05  # marketing as a share of the product's revenue last month
CLOUD_FLOOR: Final = 5_000_000  # $50,000 a month (sell_cloud's)
CLOUD_CASH_MULT: Final = 1.5  # a data centre's quote x this in cash (ready_for's cover)


def _in_use(game: Game) -> float:
    """CU the company uses: its own products' needs and the hosting it sold (22.1, 22.3)."""
    b, g = game.loaded.balance, game.loaded.game_data
    kind = b.facility.kinds[DC_KIND]
    own = sum(
        n.units for n in compute.needs(game.state, PLAYER, b, g) if n.good == kind.output_good
    )
    return own + sum(u for _, u in compute.sold_units(game.state, PLAYER, b, g))


def _staff_dcs(game: Game) -> None:
    b = game.loaded.balance
    kind = b.facility.kinds[DC_KIND]
    for i, f in enumerate(sorted(_facilities(game, DC_KIND), key=lambda f: f.id)):
        uid = staff_unit(
            game, f"{kind.label} {i + 1}", DC_ROLE, math.ceil(f.capacity / kind.staff_per)
        )
        if uid is not None and f.unit_id != uid:
            game.act(StaffFacility(game.founder_id, f.id, uid))


def _build_dc(game: Game, size: int, power: bool) -> None:
    b, g = game.loaded.balance, game.loaded.game_data
    state = game.state
    home = compute.home_region_of(state, b, g)
    sited = power and plants.plants_unlocked(state, PLAYER, b)
    site = _sited(game, size)[0] if sited and _sited(game, size) else None
    region, city = (site.region, site.city) if site is not None else (home, None)
    q = lifecycle.quote(state, PLAYER, DC_KIND, region, size, b, g)
    if not ready_for(game, round(q.capex_cents * CLOUD_CASH_MULT), cover=1.0):
        return
    refill_energy(game)
    before = {f.id for f in game.state.facilities}
    if not game.act(BuildFacility(game.founder_id, DC_KIND, region, size, city=city)):
        return
    _mark(game, "dc")
    if site is None or site.queue_hi is None:
        return
    (fid,) = {f.id for f in game.state.facilities} - before
    plant, mw = _plant_for(game, site.region, siting.draw_mw(DC_KIND, size, b, g))
    refill_energy(game)
    if game.act(BuildPlant(game.founder_id, plant, mw, site.region, site.city, fid)):
        _mark(game, "plant")


def _sell(game: Game) -> None:
    turn = game.state.turn
    if not any(f.live_capacity(turn) > 0 for f in _facilities(game, DC_KIND)):
        return
    g = game.loaded.game_data
    cloud = compute.capacity_product(game.state, PLAYER, g)
    if cloud is None:
        refill_energy(game)
        if not game.act(SellCapacity(game.founder_id)):
            return
        cloud = compute.capacity_product(game.state, PLAYER, g)
        if cloud is None:
            return
        _mark(game, "cloud")
        for m in g.category(cloud.category).markets:
            game.act(
                SetPrice(
                    game.founder_id,
                    cloud.id,
                    m.segment,
                    round(m.reference_price_cents * CLOUD_PRICE),
                )
            )
    revenue = sum(r.revenue_cents for r in game.last_product_months if r.product_id == cloud.id)
    budget = max(CLOUD_FLOOR, round(revenue * CLOUD_SHARE))
    if abs(cloud.marketing_budget_cents - budget) > budget // 10:  # tunable-exempt: a 10% band
        refill_energy(game)
        game.act(SetMarketing(game.founder_id, cloud.id, budget))


def _cloud_first(game: Game, power: bool) -> None:
    steady_regions(game)
    _staff_dcs(game)
    b = game.loaded.balance
    kind = b.facility.kinds[DC_KIND]
    built = sum(f.capacity for f in _facilities(game, DC_KIND))
    sizes = sorted(kind.sizes or b.facility.sizes)
    use = _in_use(game)
    if built == 0:
        _build_dc(game, sizes[0], power)
    elif use > FILL * built:
        gap = use * GROW - built
        _build_dc(game, next((s for s in sizes if s >= gap), sizes[-1]), power)
    _sell(game)


def cloud_first(game: Game) -> None:
    """Hosting as the main business, its data centres sited by power from stage 4."""
    _cloud_first(game, power=True)


def cloud_first_grid(game: Game) -> None:
    """cloud_first on the grid only: T1's comparison for cloud_first."""
    _cloud_first(game, power=False)


V5: Final[dict[str, Strategy]] = {
    "ev_integrator": ev_integrator,
    "life_sciences": life_sciences,
    "robotics_first": robotics_first,
    "cloud_first": cloud_first,
    "space_and_defence": space_and_defence,
}
V5_ARMS: Final[dict[str, Strategy]] = {"cloud_first_grid": cloud_first_grid}
