"""A car's design and what it costs (docs/formulas.md 49.1, 49.2, 49.4).

- **Range** = pack kWh x usable share x the year's km a kWh (vehicles.yaml) x the chemistry's
  range factor.
- **Feature points** (on top of the development team's features, 11.4): range and charging
  speed against the market's expectation (`vehicles.spec`), charging coverage for a car that
  charges at the expected speed, the autonomy level its cars run in the region, its platform
  (`vehicles.software.platform_points`) and an exclusive own charging network.
- **Autonomy** (49.4): a design aims for a level; it reaches the highest level at or below it
  whose autonomy lead (over the domain's baseline) and AI-model quality the company has, and in
  a region runs the highest of those the region has approved and has not suspended for it.
- **A unit's bill of materials** (49.1): the pack (kWh x the month's cell price x the chemistry's
  and supplier's factors, plus pack integration at the market's), the drive (motors and power
  electronics by year), chips for its level (bought at the device-OEM price, or the company's own
  chip at its unit cost) and the body at `hardware.bom.vehicles` x the vehicle_bom index (held at
  December 2025 after it). Assembly is 26.2's (plants' cost a car run, or the contract's fee).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from tst.sim.chips import chips
from tst.sim.data_models import Balance, GameData
from tst.sim.products.models import Product
from tst.sim.state import GameState
from tst.sim.vehicles.config import LEVELS, OWN, interp
from tst.sim.vehicles.data import TINY, file, year_at
from tst.sim.vehicles.models import VehicleSpec

NO_LEVEL: Final = "none"
AI_CATEGORY: Final = "ai_models"  # tunable-exempt: categories.yaml key whose quality autonomy needs
DEFAULT_CHARGE_KW: Final = 150.0  # tunable-exempt: a new design's default (vehicles.spec bounds it)
DEFAULT_PACK_KWH: Final = 60.0  # tunable-exempt: a new design's default


def default_spec(product_id: int, data: GameData) -> VehicleSpec:
    """A new design: a 60 kWh NMC pack, 150 kW charging, L2, a licensed platform, CATL cells."""
    maker = file(data).cell_makers[0].key
    return VehicleSpec(
        product_id=product_id,
        pack_kwh=DEFAULT_PACK_KWH,
        chemistry="nmc",
        charge_kw=DEFAULT_CHARGE_KW,
        autonomy="l2",
        platform="licensed",
        cells=maker,
    )


def spec_of(state: GameState, product: Product, data: GameData) -> VehicleSpec:
    return state.vehicle_spec(product.id) or default_spec(product.id, data)


def range_km(spec: VehicleSpec, turn: int, balance: Balance, data: GameData) -> float:
    v = file(data)
    km = interp(v.km_per_kwh, year_at(turn))
    chem = v.battery.chemistries[spec.chemistry]
    return spec.pack_kwh * balance.vehicles.spec.usable * km * chem.range_mult


def _clamp(x: float, cap: float) -> float:
    return max(-cap, min(cap, x))


def range_points(spec: VehicleSpec, turn: int, balance: Balance, data: GameData) -> float:
    sb = balance.vehicles.spec
    expected = interp(file(data).range_expected_km, year_at(turn))
    return _clamp(
        sb.range_points * (range_km(spec, turn, balance, data) / expected - 1), sb.range_cap
    )


def charge_points(spec: VehicleSpec, turn: int, balance: Balance, data: GameData) -> float:
    sb = balance.vehicles.spec
    expected = interp(file(data).charge_expected_kw, year_at(turn))
    return _clamp(sb.charge_points * (spec.charge_kw / expected - 1), sb.charge_cap)


# --- Autonomy ---------------------------------------------------------------------------------


def best_ai_quality(state: GameState, company_id: int) -> float:
    return max(
        (
            p.quality
            for p in state.company_products(company_id)
            if p.category == AI_CATEGORY and p.status == "live"
        ),
        default=0.0,
    )


def capable_level(state: GameState, spec: VehicleSpec, company_id: int, balance: Balance) -> str:
    """The highest level at or below the design's aim that the company's autonomy lead and AI
    quality allow (49.4)."""
    vb = balance.vehicles
    lead = state.research_lead(company_id, vb.domain)
    ai = best_ai_quality(state, company_id)
    best = NO_LEVEL
    for key in LEVELS[: LEVELS.index(spec.autonomy) + 1]:
        level = vb.levels.get(key)
        if level is None:
            continue
        if lead + TINY >= level.lead and (level.ai_quality <= 0 or ai >= level.ai_quality):
            best = key
    return best


def approved(state: GameState, region: str, level: str, balance: Balance, data: GameData) -> bool:
    """A region allows the level: no approval needed, the data's approval month has passed, or a
    seeded approval after the history (49.4)."""
    spec = balance.vehicles.levels.get(level)
    if spec is None or not spec.approval:
        return True
    for g in file(data).regulators:
        if g.region != region:
            continue
        for a in g.approvals:
            from tst.sim.facilities.config import month_to_turn

            if a.level == level and month_to_turn(a.month) <= state.turn:
                return True
    return any(
        r == region and lv == level and t <= state.turn for r, lv, t in state.vehicle_world.approved
    )


def suspended(state: GameState, company_id: int, region: str, level: str) -> bool:
    return any(
        s.company_id == company_id
        and s.region == region
        and s.level == level
        and s.until_turn > state.turn
        for s in state.vehicle_world.suspensions
    )


def level_in(
    state: GameState,
    product: Product,
    region: str,
    balance: Balance,
    data: GameData,
    capable: str | None = None,
) -> str:
    """The level the product's cars run in a region: the capable level, stepped down to one the
    region approves and has not suspended for the company."""
    spec = spec_of(state, product, data)
    top = (
        capable if capable is not None else capable_level(state, spec, product.company_id, balance)
    )
    for key in reversed(LEVELS[: LEVELS.index(top) + 1]):
        if key not in balance.vehicles.levels:
            continue
        if approved(state, region, key, balance, data) and not suspended(
            state, product.company_id, region, key
        ):
            return key
    return NO_LEVEL


# --- Cost of a unit -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UnitCost:
    """A car's bill of materials at this month's prices (cents), by line."""

    cells: float  # the pack's cells at the market (own cells' saving is settled after sale)
    integration: float  # pack integration
    drive: float
    chips: float
    body: float

    @property
    def battery(self) -> float:
        return self.cells + self.integration

    @property
    def total(self) -> float:
        return self.cells + self.integration + self.drive + self.chips + self.body


def cell_cents(state: GameState, spec: VehicleSpec, balance: Balance, data: GameData) -> float:
    """A kWh of the design's cells bought this month: the market price x the chemistry's factor
    x the supplier's (own cells are priced at the market and settled after sale, 49.2)."""
    from tst.sim.vehicles import cells

    v = file(data)
    # money-exact: rate (a kWh's price; the posted amount is rounded once at sale)
    chem = v.battery.chemistries[spec.chemistry].cost_mult
    price = cells.market_cents(state, balance, data) * chem  # money-exact: rate
    if spec.cells != OWN:
        price *= v.cell_maker(spec.cells).price_mult
    return price


def chip_cents(
    state: GameState, company_id: int, level: str, balance: Balance, data: GameData
) -> float:
    """The chips a car at `level` carries: the company's own live chip of a type at its unit cost,
    else bought at the device-OEM price (26.3)."""
    spec = balance.vehicles.levels[level]
    total = 0.0
    for chip_type, count in spec.chips.items():
        own = next(
            (
                p
                for p in state.company_products(company_id)
                if p.status == "live"
                and data.category(p.category).chip_type == chip_type
                and chips.wafer_contracts(state, p.id)
            ),
            None,
        )
        unit = (
            chips.contract_unit_cents(state, own, balance, data)
            if own is not None
            else float(chips.bought_price_cents(data, balance, chip_type))
        )
        total += count * unit
    return total


def body_cents(state: GameState, balance: Balance, data: GameData) -> float:
    bom = balance.hardware.bom[balance.vehicles.category]
    assert data.components is not None
    good = data.components.good(bom.good)
    turn = min(state.turn, balance.vehicles.start_turn - 1, good.last_turn)
    # money-exact: rate (a car's body at the index, cents a unit)
    return bom.base_cents * good.index_at(turn)


def unit_cost(
    state: GameState, product: Product, balance: Balance, data: GameData, level: str | None = None
) -> UnitCost:
    spec = spec_of(state, product, data)
    v = file(data)
    year = year_at(min(state.turn, balance.vehicles.start_turn - 1))
    share = v.battery.cell_share_at(year)
    # money-exact: rate (cents a car)
    cells = spec.pack_kwh * cell_cents(state, spec, balance, data)
    from tst.sim.vehicles import cells as cell_market

    # money-exact: rate (cents a car)
    integration = spec.pack_kwh * cell_market.market_cents(state, balance, data) * (1 / share - 1)
    if spec.cells == OWN:  # in-house pack assembly on the group's cells (49.2)
        integration *= 1 - balance.vehicles.cell_plant.integration_saving
    drive = interp(balance.vehicles.bom.drive_cents, year_at(state.turn))
    run = level if level is not None else capable_level(state, spec, product.company_id, balance)
    return UnitCost(
        cells=cells,
        integration=integration,
        drive=drive,
        chips=chip_cents(state, product.company_id, run, balance, data),
        body=body_cents(state, balance, data),
    )
