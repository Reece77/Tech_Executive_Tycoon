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
  as soon as it is cleared; pharma with AI discovery joins it when M42 merges.
- **cloud_first** (22, 46): hosting as the main business: from the first month cash covers it,
  the smallest general data centre in the home region; its capacity sold as cloud hosting
  (0.9x the reference price, marketing 5% of the product's revenue, at least $50,000 a month);
  a new data centre whenever sold and own CU pass 80% of what is built, sized to the gap; from
  stage 4 sited by power with a plant behind the meter when it would queue (power_hyperscaler's
  siting). **cloud_first_grid** is the same company on the grid only: T1's comparison, so the
  ratio measures power directly (M35b's follow-up).
- **dynasty** (52): any of the above played to December 2069 with a family (M37's dynasty runs).

space_and_defence (56, 57) is added when M40 and M44 merge.
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
from tst.sim.medical import coverage
from tst.sim.medical import data as md
from tst.sim.medical.actions import DesignDevice, RequestCoverage, SetMedicalSupport, SubmitDevice
from tst.sim.power import plants, siting
from tst.sim.power.actions import BuildPlant
from tst.sim.robotics import robotaxi as rt
from tst.sim.robotics.actions import AddRobotaxis, BuildDepot, OpenZone, SetHumanoidSpec
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


def ev_integrator(game: Game) -> None:
    """full_integrator with a car line from 2026 on its own cells from stage 4."""
    full_integrator(game)
    car_step(game)


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


def robotics_first(game: Game) -> None:
    """devices_regions, then industrial robots from 2026, humanoids once their market opens, and
    robotaxis once its own autonomy research and AI model reach L4."""
    devices_regions(game)
    if line_step(game, ROBOT) is None:
        return
    hid = line_step(game, replace(HUMANOID, segments=_segments(game, HUMANOID.category)))
    if game.state.turn >= AUTONOMY_FROM:
        _research(game, AUTONOMY_UNIT, AUTONOMY_ROLE, AUTONOMY_STAFF, "autonomy")
        ai = _ai_model(game)
        if _live(game, hid) and _live(game, ai) and "humanoid_spec" not in game.notes:
            refill_energy(game)
            if hid is not None and game.act(
                SetHumanoidSpec(game.founder_id, hid, ai_product_id=ai)
            ):
                game.notes["humanoid_spec"] = game.state.turn
        _robotaxis(game)


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


def _answer_medical(game: Game) -> None:
    """A class I recall is answered with its first choice (M41's entrant)."""
    from tst.sim.medical import quality

    for event in game.state.open_events(PLAYER):
        if event.status == "open" and event.template_id == quality.CLASS_I_RECALL:
            game.act(ChooseEvent(game.founder_id, event.id, "A"))


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
}
V5_ARMS: Final[dict[str, Strategy]] = {"cloud_first_grid": cloud_first_grid}
