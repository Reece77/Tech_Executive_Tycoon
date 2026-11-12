"""The v3 scripted strategies (M23b): full_integrator, mineral_baron and foundry. Like the v1 and
v2 scripts (tst.balance.strategies, tst.balance.strategies_v2) they act only through
`Game.act`, so every rule applies, and they read only what a player sees (desk-study bands,
stage results, quotes), never a block's hidden truth. Their numbers describe the scripts, not
the game, so they live here rather than in balance.yaml.

Each plays steady_regions (the v2 base) and, once the company is at stage 3 and can carry it,
climbs its own ladder:

- **full_integrator**: a device line with a contract manufacturer, then its own mobile SoC on
  a foundry contract; lithium explored for in Oceania and mined by a minerals subsidiary that
  sells its concentrate to the parent at cost plus (31.6), converted in the parent's own plant;
  its own wafer plant and fab, whose
  chips go into its devices first and whose spare starts are sold as foundry slots. Aimed at
  the whole chain by year 15 (2025).
- **mineral_baron**: exploration for copper (Latin America) and lithium (Oceania) from
  stage 3, mines selling at spot.
- **foundry**: a pure-play fab business: a process research unit, then a mature-node fab in
  East Asia whose starts are sold to rival designers (spot slots, and from M23a foundry
  contracts).
"""

from __future__ import annotations

import math
from typing import Final

from tst.balance.game import PLAYER, Game
from tst.balance.strategies import Strategy, runway
from tst.balance.strategies_v2 import (
    BUILDER_ROLE,
    _unit,
    refill_energy,
    staff_unit,
    steady_regions,
)
from tst.sim.actions import (
    AssignUnit,
    CreateProduct,
    SetPrice,
)
from tst.sim.actions.facilities import BuildFacility, StaffFacility
from tst.sim.actions.hardware import SignManufacturingContract, SignWaferContract
from tst.sim.actions.research import StartProject
from tst.sim.contracts import termination as ct
from tst.sim.errors import SimError
from tst.sim.exploration.models import Project
from tst.sim.exploration.pipeline import (
    OrderDrilling,
    RelinquishProject,
    StartDeskStudy,
    StartStage,
    TakeLicence,
    holder_of,
)
from tst.sim.fabs import actions as fab_actions
from tst.sim.fabs import foundry as foundry_contracts
from tst.sim.fabs import market as fab_market
from tst.sim.fabs import supply as fab_supply
from tst.sim.fabs.actions import BuildFab
from tst.sim.facilities.models import Facility
from tst.sim.mining import actions as mine_actions
from tst.sim.mining import formulas as mine_formulas
from tst.sim.mining.actions import (
    BuildMine,
    FoundSubsidiary,
    SetMineSales,
    StaffMine,
    TransferAsset,
)
from tst.sim.refining import actions as refinery_actions
from tst.sim.refining.actions import BuildRefinery
from tst.sim.state import company_cash

# --- When a ladder starts ---------------------------------------------------------------------

LADDER_STAGE: Final = 3  # stage the v3 ladders start at (exploration, subsidiaries: 34.4, 35.1)
LADDER_RUNWAY: Final = 24  # months of runway (or profitable) a new rung needs


def ready_for(game: Game, cents: int, cover: float = 2.0) -> bool:
    """A new rung costing `cents`: stage 3 or more, profitable or 24 months of runway, and
    cash covering the cost `cover` times (by default twice: the script keeps half its cash for
    the software business)."""
    if game.state.player.stage < LADDER_STAGE:
        return False
    months = runway(game)
    if months is not None and months <= LADDER_RUNWAY:
        return False
    return game.cash >= cover * cents


def _mark(game: Game, key: str) -> None:
    """Record the month a rung was reached (the v3 targets read these notes)."""
    game.notes.setdefault(f"rung:{key}", game.state.turn)


def rung(game: Game, key: str) -> int | None:
    return game.notes.get(f"rung:{key}")


# --- Devices and chips (full_integrator) ------------------------------------------------------

DEVICE: Final = ("Handset", "devices", ("consumer",))
DEVICE_PRICE: Final = 0.8  # x the consumer reference price (as M12b's device company)
DEVICE_TEAM: Final = 12  # hardware engineers in the device team
DEVICE_UNITS: Final = 20_000  # the first contract's units a month (as M12b's)
DEVICE_START_CENTS: Final = 5_000_000_000  # $50M of cash (x2, ready_for) before the device line
CONTRACT_MONTHS: Final = 24
RENEW_BEFORE: Final = 2  # months before a contract ends that the next is signed
UNITS_HEADROOM: Final = 1.2  # a renewal covers last month's units x this
MANUFACTURER: Final = ("foxconn", "shenzhen")
CHIP: Final = ("Handset SoC", "chips_mobile_soc", ("device_oems",))
CHIP_TEAM: Final = 8  # chip designers in the SoC team
CHIP_PRICE: Final = 10.0  # x the reference price: the SoC goes into the group's own devices
FOUNDRY: Final = "tsmc"
CHIPS_PER_WAFER: Final = 600  # good dies a wafer before yield (as M12b's device company)
DEVICE_ROLE: Final = "hardware_engineer"
CHIP_ROLE: Final = "chip_designer"


def _product(game: Game, category: str) -> int | None:
    p = next(
        (
            p
            for p in game.state.company_products(PLAYER)
            if p.category == category and p.status != "retired"
        ),
        None,
    )
    return p.id if p is not None else None


def _make_product(
    game: Game, spec: tuple[str, str, tuple[str, ...]], price: float, team: str
) -> int | None:
    name, category, segments = spec
    uid = _unit(game, team)
    pid = game.state.next_ids.product
    if uid is None or not game.act(CreateProduct(game.founder_id, name, category, segments)):
        return None
    cat = game.loaded.game_data.category(category)
    for segment in segments:
        ref = cat.market(segment).reference_price_cents
        game.act(SetPrice(game.founder_id, pid, segment, round(ref * price)))
    game.act(AssignUnit(game.founder_id, pid, uid))
    return pid


def _contracts(game: Game, product_id: int, kind: str) -> list[object]:
    return [
        c
        for c in game.state.production_contracts
        if c.product_id == product_id and c.kind == kind and c.end_turn >= game.state.turn
    ]


def _units_sold(game: Game, product_id: int) -> float:
    """Last month's units: new plus kept customers x units per customer (the device rows)."""
    g = game.loaded.game_data
    product = game.state.product(product_id)
    if product is None:
        return 0.0
    cat = g.category(product.category)
    total = 0.0
    for row in game.last_product_months:
        if row.product_id == product_id:
            per = cat.market(row.segment).units_per_customer or 1
            total += row.customers * per
    return total


def _device_units(game: Game, product_id: int) -> int:
    sold = _units_sold(game, product_id)
    cap = game.loaded.balance.hardware.contract.max_units
    return min(cap, max(DEVICE_UNITS, round(sold * UNITS_HEADROOM)))


def _renewal_due(game: Game, contracts: list[object]) -> bool:
    if not contracts:
        return True
    last = max(c.end_turn for c in contracts)  # type: ignore[attr-defined]
    return last - game.state.turn < RENEW_BEFORE and last < game.state.turn + RENEW_BEFORE


def devices_step(game: Game) -> None:
    """The device line: its team and product once ready_for($50M), a manufacturing contract
    whenever none runs (or the last ends within two months), sized to last month's units."""
    pid = _product(game, DEVICE[1])
    if pid is None:
        if not ready_for(game, DEVICE_START_CENTS):
            return
        refill_energy(game)
        pid = _make_product(game, DEVICE, DEVICE_PRICE, "Devices team")
        if pid is None:
            return
        _mark(game, "devices")
    staff_unit(game, "Devices team", DEVICE_ROLE, DEVICE_TEAM)
    if _own_assembly(game):
        return
    contracts = _contracts(game, pid, "assembly")
    if _renewal_due(game, contracts):
        maker, city = MANUFACTURER
        refill_energy(game)
        game.act(
            SignManufacturingContract(
                game.founder_id, pid, maker, city, _device_units(game, pid), CONTRACT_MONTHS
            )
        )


def _own_assembly(game: Game) -> bool:
    return any(
        f.company_id == PLAYER and f.kind == "assembly_plant" and f.status != "closed"
        for f in game.state.facilities
    )


def _wafers_for(game: Game, units: float) -> int:
    y = game.loaded.balance.chips.chip_yield.base
    return max(1, math.ceil(units * UNITS_HEADROOM / (CHIPS_PER_WAFER * y)))


def chip_step(game: Game) -> None:
    """The group's own SoC once its device is live: a chip team, the chip priced for its own
    devices (CHIP_PRICE), and a foundry contract sized to the devices whenever none runs."""
    device = _product(game, DEVICE[1])
    if device is None or game.state.product(device).status not in ("live", "sunset"):  # type: ignore[union-attr]
        return
    pid = _product(game, CHIP[1])
    if pid is None:
        refill_energy(game)
        pid = _make_product(game, CHIP, CHIP_PRICE, "Chip team")
        if pid is None:
            return
        _mark(game, "chip")
    staff_unit(game, "Chip team", CHIP_ROLE, CHIP_TEAM)
    contracts = _contracts(game, pid, "wafer")
    if _renewal_due(game, contracts):
        units = max(_units_sold(game, device), DEVICE_UNITS)
        chip = game.state.product(pid)
        b, g = game.loaded.balance, game.loaded.game_data
        if (
            chip is not None
            and fab_supply.fab_chips(game.state, chip, b, g) >= units * UNITS_HEADROOM
        ):
            return  # the group's own fab makes them (38.2: own chips first)
        refill_energy(game)
        game.act(
            SignWaferContract(
                game.founder_id, pid, FOUNDRY, _wafers_for(game, units), CONTRACT_MONTHS
            )
        )


# --- Exploration and mines (full_integrator, mineral_baron) -----------------------------------

GEOLOGIST_ROLE: Final = "geologist"
GEOLOGISTS: Final = 4  # a stage runs on one geologist (exploration.stages_per_geologist)
EXPLORE_CENTS: Final = 5_000_000_000  # $50M (x2, ready_for) before exploring a commodity
PROJECTS_AT_ONCE: Final = 4  # licensed projects in the pipeline per commodity
HOLES: Final = 40  # a programme to an indicated resource (M18's balance runs)
MINE_ROLE: Final = "mining_engineer"
PROCESS_ROLE: Final = "process_engineer"
FAB_ROLE: Final = "fab_engineer"
MINE_CASH_MULT: Final = 1.5  # a mine's estimate x this in cash: the top of a definitive study's
# public overrun band (mining.overrun.definitive [0, 0.5]); the draw itself is hidden
MINE_COVER: Final = 1.25  # cash x this before founding a mine (a mine is the ladder's big bet)
# A cheap scoping study to screen the project, then the definitive study its 40-hole measured
# resource allows (exploration.feasibility.min_category): pre-feasibility adds 8 months only.
STUDIES: Final = ("scoping", "definitive")


def _projects(game: Game, region: str, commodity: str) -> list[Project]:
    """The group's projects in `region`, where the scripts explore for `commodity` only (a
    survey may read another commodity's anomaly: sampling then looks for `commodity`)."""
    del commodity  # one commodity a region (LITHIUM, COPPER)
    groups = _group(game)
    return [
        p
        for p in game.state.projects
        if p.company_id in groups and p.region == region and p.status != "relinquished"
    ]


def _group(game: Game) -> set[int]:
    return {PLAYER} | {c.id for c in game.state.companies if c.parent_id == PLAYER}


def _desk(game: Game, region: str, commodity: str) -> tuple[str, ...] | None:
    """The bands of the company's desk study of `commodity` in `region`; starts one if none."""
    study = next(
        (
            s
            for s in game.state.desk_studies
            if s.company_id == PLAYER and s.region == region and s.commodity == commodity
        ),
        None,
    )
    if study is None:
        refill_energy(game)
        game.act(StartDeskStudy(game.founder_id, region, commodity))
        return None
    return study.bands if study.done else None


def _licence_next(game: Game, region: str, commodity: str, bands: tuple[str, ...]) -> None:
    """A licence on the best-banded free block not tried before (high, then medium)."""
    tried = {(p.region, p.block) for p in game.state.projects if p.company_id in _group(game)}
    for band in ("high", "medium"):
        for block, b in enumerate(bands):
            if b != band or (region, block) in tried:
                continue
            if holder_of(game.state, region, block) is not None:
                continue
            refill_energy(game)
            if game.act(TakeLicence(game.founder_id, region, block)):
                return


def _advance(game: Game, p: Project, commodity: str) -> None:
    """The project's next stage, as a player reads its results: give up on a weak or empty
    survey, a sample or estimate with no grade, or a study whose mid NPV is negative."""
    if p.status != "active" or p.stage is not None or p.holes_left or p.paused_until:
        return
    founder = game.founder_id
    refill_energy(game)
    if p.reading is None:
        game.act(StartStage(founder, p.id, "survey"))
        return
    if p.reading == "none":
        game.act(RelinquishProject(founder, p.id))
        return
    if p.sample_center is None:
        game.act(StartStage(founder, p.id, "sampling", commodity))
        return
    drilled = sum(1 for h in game.state.holes if h.project_id == p.id)
    if drilled < HOLES:
        game.act(OrderDrilling(founder, p.id, HOLES - drilled))
        return
    if p.category is None or p.est_holes < drilled:
        game.act(StartStage(founder, p.id, "estimate"))
        return
    if p.level is not None and (p.npv_mid_cents or 0) <= 0:
        game.act(RelinquishProject(founder, p.id))
        return
    done = STUDIES.index(p.level) if p.level in STUDIES else -1
    if done + 1 < len(STUDIES):
        if not game.act(StartStage(founder, p.id, STUDIES[done + 1])):
            game.act(RelinquishProject(founder, p.id))  # the resource will not carry the study
        return
    if p.permit_start is None:
        game.act(StartStage(founder, p.id, "permitting"))


def explore_step(game: Game, region: str, commodity: str) -> None:
    """Geologists, a desk study, and up to PROJECTS_AT_ONCE licensed projects taken stage by
    stage toward a permit (34.2)."""
    staff_unit(game, "Exploration", GEOLOGIST_ROLE, GEOLOGISTS)
    if not any(e.unit_id == _unit(game, "Exploration") for e in game.state.staff(PLAYER)):
        return
    bands = _desk(game, region, commodity)
    if bands is None:
        return
    _mark(game, f"explore:{commodity}")
    live = [p for p in _projects(game, region, commodity) if p.status == "active"]
    for p in sorted(live, key=lambda p: p.id):
        _advance(game, p, commodity)
    if len(live) < PROJECTS_AT_ONCE and not _permitted(game, region, commodity):
        _licence_next(game, region, commodity, bands)


def _permitted(game: Game, region: str, commodity: str) -> list[Project]:
    return [p for p in _projects(game, region, commodity) if p.status == "permitted"]


def _mines(game: Game, commodity: str | None = None) -> list[object]:
    groups = _group(game)
    return [
        m
        for m in game.state.mines
        if m.company_id in groups
        and m.status != "closed"
        and (commodity is None or m.commodity == commodity)
    ]


def _crew(game: Game, mine: object, i: int) -> None:
    """A unit of mining engineers in the parent sized to the mine (35.3: any company of the
    group may employ them), set to staff it."""
    b = game.loaded.balance
    need = mine_formulas.staff_needed(mine.capacity_t, b.mining.staff_per_kt)  # type: ignore[attr-defined]
    uid = staff_unit(game, f"Mine crew {i + 1}", MINE_ROLE, need)
    facility = game.state.facility(mine.id)  # type: ignore[attr-defined]
    if uid is not None and facility is not None and facility.unit_id != uid:
        refill_energy(game)
        game.act(StaffMine(game.founder_id, mine.id, uid))  # type: ignore[attr-defined]


def build_mines(game: Game, region: str, commodity: str, owner_name: str | None = None) -> None:
    """A mine on each permitted project the company can pay for (the estimate x 1.6 in cash).
    With `owner_name`, the project first moves into that group company (35.1), founded when
    missing with cash for the project's book value and the mine (there is no later injection:
    FoundSubsidiary's cash is the subsidiary's capital). Every mine crewed."""
    b, g = game.loaded.balance, game.loaded.game_data
    for p in _permitted(game, region, commodity):
        if any(m.project_id == p.id for m in game.state.mines):
            continue
        design = mine_actions.design_capacity_t(p) / b.exploration.feasibility.life_years
        capacity = mine_formulas.capacity_bounds(design, b.mining)[0]  # the smallest mine
        try:
            q = mine_actions.quote(game.state, p, capacity, b, g)
        except SimError:  # a quote the rules refuse: not this month
            continue
        cash_need = round(q.estimate_cents * MINE_CASH_MULT)
        if owner_name is not None and p.company_id == PLAYER:
            region = p.region
            capital = round((p.spent_cents + cash_need) * SUBSIDIARY_BUFFER)
            if not ready_for(game, capital, MINE_COVER):
                continue
            owner = subsidiary(game, owner_name, region, capital)
            if owner is None:
                continue
            refill_energy(game)
            if not game.act(TransferAsset(game.founder_id, owner, project_id=p.id)):
                continue
        elif not ready_for(game, cash_need, MINE_COVER):
            continue
        refill_energy(game)
        if game.act(BuildMine(game.founder_id, p.id, capacity)):
            _mark(game, f"mine:{commodity}")
    for i, m in enumerate(sorted(_mines(game), key=lambda m: m.id)):  # type: ignore[attr-defined]
        _crew(game, m, i)


SUBSIDIARY_BUFFER: Final = 1.15  # the subsidiary's capital: its first build's needs x this


def subsidiary_id(game: Game, name: str) -> int | None:
    found = next(
        (c for c in game.state.companies if c.parent_id == PLAYER and c.name.endswith(name)), None
    )
    return found.id if found is not None else None


def subsidiary(game: Game, name: str, region: str, cents: int) -> int | None:
    """The group company called `name`, founded (35.1) with `cents` when missing."""
    existing = subsidiary_id(game, name)
    if existing is not None:
        return existing
    cid = max(c.id for c in game.state.companies) + 1
    refill_energy(game)
    full = f"{game.state.player.name} {name}"
    if not game.act(FoundSubsidiary(game.founder_id, full, region, cents)):
        return None
    _mark(game, f"subsidiary:{name}")
    return cid


# --- Refineries, wafers and fabs --------------------------------------------------------------

REFINERY_CASH_MULT: Final = 1.3  # a plant's estimate x this in cash (the overrun is hidden)


def _facilities(game: Game, kind: str) -> list[Facility]:
    groups = _group(game)
    return [
        f
        for f in game.state.facilities
        if f.company_id in groups and f.kind == kind and f.status != "closed"
    ]


def _staff_plants(game: Game, kind: str, role: str, label: str) -> None:
    """A unit of `role` in the parent for each plant of `kind`, sized to its need."""
    b = game.loaded.balance
    k = b.facility.kinds[kind]
    for i, f in enumerate(sorted(_facilities(game, kind), key=lambda f: f.id)):
        need = math.ceil(f.capacity / k.staff_per)
        uid = staff_unit(game, f"{label} {i + 1}", role, need)
        if uid is not None and f.unit_id != uid:
            refill_energy(game)
            game.act(StaffFacility(game.founder_id, f.id, uid))


def build_refinery(
    game: Game, recipe: str, region: str, capacity: int, company: int | None = None
) -> bool:
    """One plant of `recipe` once the company can pay for it (estimate x 1.3, twice over)."""
    b, g = game.loaded.balance, game.loaded.game_data
    kind = b.refining.recipes[recipe].kind
    if _facilities(game, kind):
        return True
    owner = company if company is not None else PLAYER
    q = refinery_actions.quote(game.state, owner, recipe, region, capacity, b, g)
    need = round(q.quote.capex_cents * REFINERY_CASH_MULT)
    if owner == PLAYER and not ready_for(game, need):
        return False
    if owner != PLAYER and company_cash(game.balances, owner) < q.quote.monthly_capex_cents:
        return False  # the subsidiary was founded with its plant's capital
    refill_energy(game)
    ok = game.act(BuildRefinery(game.founder_id, recipe, region, capacity, company_id=company))
    if ok:
        _mark(game, f"refinery:{recipe}")
    return ok


FAB_REGION: Final = "east_asia"
FAB_SIZE: Final = 10_000  # wafer starts a month (the smallest fab)
FAB_NODES: Final = ("n28", "n40", "n65")  # mature nodes the scripts build, newest first
FAB_CASH_MULT: Final = 1.3  # the fab's estimate x this in cash (the overrun is hidden)
WAFER_PLANT_SIZE: Final = 120_000  # wafers a year: 10,000 a month, one fab's starts


def build_fab(game: Game, nodes: tuple[str, ...] = FAB_NODES) -> bool:
    """A fab on the newest of `nodes` the company may run and pay for (FabQuote.allowed, the
    estimate x 1.3 twice over), in East Asia."""
    b, g = game.loaded.balance, game.loaded.game_data
    if _facilities(game, "fab"):
        return True
    for node in nodes:
        try:
            q = fab_actions.quote(game.state, PLAYER, node, FAB_REGION, FAB_SIZE, b, g)
        except SimError:  # an unknown node in this data
            continue
        if not q.allowed:
            continue
        if not ready_for(game, round(q.capex_cents * FAB_CASH_MULT)):
            return False
        refill_energy(game)
        if game.act(BuildFab(game.founder_id, node, FAB_REGION, FAB_SIZE)):
            _mark(game, "fab")
            return True
    return False


# --- The strategies ---------------------------------------------------------------------------

MINERALS: Final = "Minerals"  # the full integrator's mining subsidiary
LITHIUM: Final = ("oceania", "lithium_carbonate")
COPPER: Final = ("latin_america", "copper")
CONVERTER: Final = ("li_converter", 10_000)  # t a year: the smallest converter


def _transfer_sales(game: Game, owner: int) -> None:
    """Each mine of the group sells to the parent at cost plus (31.6)."""
    for m in _mines(game):
        if m.buyer_id != PLAYER:  # type: ignore[attr-defined]
            refill_energy(game)
            if game.act(SetMineSales(game.founder_id, m.id, PLAYER, "cost_plus")):  # type: ignore[attr-defined]
                _mark(game, "transfer")


def _resourced(game: Game, region: str, commodity: str) -> bool:
    """A project in `region` with a resource estimate (revealed: the estimate stage's result)."""
    return any(p.category is not None for p in _projects(game, region, commodity))


def full_integrator(game: Game) -> None:
    """steady_regions, then from stage 3 the whole chain: devices, its own SoC, a minerals
    subsidiary mining lithium for the parent at cost plus, the parent's converter, a wafer
    plant and a fab (30.6's integrator carried down the chain; M23b). Exploration starts with
    the device line, and the converter once a deposit has a resource estimate: it buys
    concentrate at spot until the group's mine replaces it (M23a's group supply, 36.2)."""
    steady_regions(game)
    devices_step(game)
    chip_step(game)
    if game.state.player.stage < LADDER_STAGE:
        return
    region, commodity = LITHIUM
    if _mines(game, commodity) or ready_for(game, EXPLORE_CENTS):
        explore_step(game, region, commodity)
    build_mines(game, region, commodity, MINERALS)
    if _mines(game, commodity) or _resourced(game, region, commodity):
        recipe, size = CONVERTER  # in the parent (its crew is the parent's)
        build_refinery(game, recipe, region, size)
        _staff_plants(game, "li_converter", PROCESS_ROLE, "Converter crew")
    owner = subsidiary_id(game, MINERALS)
    if owner is not None:
        _transfer_sales(game, owner)
    if _product(game, CHIP[1]) is not None:
        build_refinery(game, "wafer_plant", FAB_REGION, WAFER_PLANT_SIZE)
        _staff_plants(game, "wafer_plant", PROCESS_ROLE, "Wafer crew")
        build_fab(game)
        _staff_plants(game, "fab", FAB_ROLE, "Fab crew")
        sign_foundry_contracts(game)


def mineral_baron(game: Game) -> None:
    """steady_regions, then from stage 3 exploration for copper (Latin America) and lithium
    (Oceania) and a mine on every permitted project it can pay for, selling at spot."""
    steady_regions(game)
    for region, commodity in (COPPER, LITHIUM):
        if not _mines(game, commodity) and not ready_for(game, EXPLORE_CENTS):
            continue
        explore_step(game, region, commodity)
        build_mines(game, region, commodity)


PROCESS_TEAM: Final = 6  # process researchers (as research_heavy's early unit)
PROCESS_RESEARCH_ROLE: Final = "process_engineer"


def _process_research(game: Game) -> None:
    domain = game.loaded.balance.refining.domain
    uid = staff_unit(game, "Process research", PROCESS_RESEARCH_ROLE, PROCESS_TEAM)
    if uid is None:
        return
    projects = [
        p for p in game.state.research_projects if p.company_id == PLAYER and p.status == "active"
    ]
    if not any(p.unit_id == uid for p in projects) and any(
        e.unit_id == uid for e in game.state.staff(PLAYER)
    ):
        game.act(StartProject(game.founder_id, uid, domain))


FOUNDRY_MONTHS: Final = 36  # a foundry contract's term (the longest contracts.foundry.months)
FOUNDRY_FILL: Final = (
    0.8  # contract this share of a fab's capacity (contracts.foundry.max_share 0.9)
)


def _own_starts(game: Game, fab_id: int) -> float:
    """Starts the group's own SoCs need from this fab: the devices' units over the fab's good
    chips a start for the SoC, x headroom (0 without a chip on this fab)."""
    pid, device = _product(game, CHIP[1]), _product(game, DEVICE[1])
    chip = game.state.product(pid) if pid is not None else None
    if chip is None or device is None:
        return 0.0
    b, g = game.loaded.balance, game.loaded.game_data
    shares = fab_supply.product_shares(game.state, chip, b, g)
    per = max((x.chips_per_start for x in shares if x.facility_id == fab_id), default=0.0)
    if per <= 0:
        return 0.0
    return max(_units_sold(game, device), DEVICE_UNITS) / per * UNITS_HEADROOM


def sign_foundry_contracts(game: Game) -> None:
    """Contract a live group fab's starts to the chip incumbents (M23a's foundry contracts):
    each designer up to its share cap, the fab to FOUNDRY_FILL of capacity less the starts the
    group's own chips need, at the most a designer pays (the node's slot price, which the fab
    card shows)."""
    b, g = game.loaded.balance, game.loaded.game_data
    fb = b.contracts.foundry
    for facility in _facilities(game, "fab"):
        if facility.status != "live":
            continue
        fab = fab_market.fab_of(game.state, facility.id)
        if fab is None:
            continue
        cap = float(facility.capacity)
        for customer in foundry_contracts.customers(g):
            running = foundry_contracts.running(game.state, fab.facility_id)
            total = sum(c.monthly_starts for c in running)
            own = sum(c.monthly_starts for c in running if c.customer == customer)
            room = min(cap * FOUNDRY_FILL, cap - _own_starts(game, fab.facility_id)) - total
            starts = math.floor(min(cap * fb.customer_share - own, room))
            if starts < 1:
                continue
            slot = foundry_contracts.slot_price_cents(game.state, fab, b, g) * fb.max_price
            price = slot / float(ct.premium(game.state, customer, b)) * 0.999
            refill_energy(game)
            game.act(
                foundry_contracts.SignFoundryContract(
                    game.founder_id, fab.facility_id, customer, starts, FOUNDRY_MONTHS, price
                )
            )


def foundry(game: Game) -> None:
    """steady_regions, then from stage 3 a process research unit and a mature-node fab in East
    Asia, its starts under foundry contracts to rival designers (M23a), the rest sold as
    38.2's slots."""
    steady_regions(game)
    if game.state.player.stage < LADDER_STAGE:
        return
    _process_research(game)
    build_fab(game)
    _staff_plants(game, "fab", FAB_ROLE, "Fab crew")
    sign_foundry_contracts(game)


def devices_regions(game: Game) -> None:
    """I1-I2's like-for-like baseline (M23b, proposed): steady_regions with full_integrator's
    device line and its own SoC, both on contracts (a contract manufacturer and a foundry),
    and no chain of its own. Measured, not among the strategies whose wins I3 counts."""
    steady_regions(game)
    devices_step(game)
    chip_step(game)


V3: Final[dict[str, Strategy]] = {
    "full_integrator": full_integrator,
    "mineral_baron": mineral_baron,
    "foundry": foundry,
}

V3_ARMS: Final[dict[str, Strategy]] = {"devices_regions": devices_regions}

# keep BUILDER_ROLE and BuildFacility importable for a later rung (own assembly plant)
_ = (BUILDER_ROLE, BuildFacility)
