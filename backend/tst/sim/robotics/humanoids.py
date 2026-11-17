"""Humanoids (docs/formulas.md 53.2): capability, actuators' learning curve and what demand reads.

- **Capability** (0-100) = w_hardware x the product's quality + w_ai x its AI model's quality (an
  own live `ai_models` product named in its design, else `licensed_ai_quality`) + w_chips x its
  chips' quality (an own live `chips_ai_accelerator` product named in its design, else
  `bought_chip_quality`). Rivals' lines use their quality with the licensed and bought defaults.
- **Actuators** are a learning-curve cost: their first-year cost (robotics.yaml) falls
  `learning_rate` with each doubling of humanoids made since the era's arrival (from
  `base_units`). The index against the first year's cost is printed as M38's L3 measure.
- **Demand** reads the best capability (demand.world_month) and the player's lines earn feature
  points `capability_points` a point above 50 (`effects`).
- **Unit cost** (the BOM hook, tst.sim.hardware.production): base parts at the device BOM index
  (balance.yaml hardware.bom) plus the actuators; a licensed model's fee a unit is booked after
  the month's sales (`licence_entries`).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.ledger import CASH, PLATFORM_FEES, LedgerEntry, LedgerLine
from tst.sim.money import exact
from tst.sim.products.models import SELLING, Product
from tst.sim.robotics.data import MONTHS, TINY, era_turn, file, is_humanoid, year_at
from tst.sim.state import GameState, player_companies

AI_CATEGORY: Final = "ai_models"  # tunable-exempt: categories.yaml key of AI models
CHIP_CATEGORY: Final = "chips_ai_accelerator"  # tunable-exempt: categories.yaml key
HALF_SCORE: Final = 50.0  # tunable-exempt: capability points count above the middle of 0-100


def _live(state: GameState, product_id: int | None, company_id: int, category: str) -> float | None:
    if product_id is None:
        return None
    p = state.product(product_id)
    if p is None or p.company_id != company_id or p.category != category or p.status != "live":
        return None
    return p.quality


def capability(state: GameState, product: Product, balance: Balance) -> float:
    hb = balance.robotics.humanoids
    spec = state.humanoid_spec(product.id)
    ai = _live(state, spec.ai_product_id if spec else None, product.company_id, AI_CATEGORY)
    chip = _live(state, spec.chip_product_id if spec else None, product.company_id, CHIP_CATEGORY)
    w = hb.weights
    return (
        w.get("hardware", 0.0) * product.quality
        + w.get("ai", 0.0) * (ai if ai is not None else hb.licensed_ai_quality)
        + w.get("chips", 0.0) * (chip if chip is not None else hb.bought_chip_quality)
    )


def best_capability(state: GameState, balance: Balance, data: GameData) -> float:
    return max(
        (
            capability(state, p, balance)
            for p in state.products
            if is_humanoid(p, balance) and p.status in SELLING
        ),
        default=0.0,
    )


def labour_year_cents(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """A manufacturing worker's labour cost a year in the region (2010 cents)."""
    hours = balance.robotics.automation.hours_per_month * MONTHS
    return file(data).region(region).labour_at(year_at(state.turn)) * hours


def annual_cost_cents(balance: Balance, data: GameData) -> float:
    """A business humanoid's cost a year to its buyer: the reference price over its life, plus
    service."""
    hb = balance.robotics.humanoids
    price = data.category(balance.robotics.humanoid).market("logistics").reference_price_cents
    return price / (hb.life_months / MONTHS) + price * hb.service_share


def actuator_index(state: GameState, balance: Balance) -> float:
    """Actuators' cost over their first-year cost: (cumulative / base) ** log2(1 - rate)."""
    hb = balance.robotics.humanoids
    made = max(hb.base_units, hb.base_units + state.robotics_world.actuator_units)
    b = dmath.log(1 - hb.learning_rate) / dmath.log(2)
    return dmath.pow(made / hb.base_units, b)


def actuator_cents(state: GameState, balance: Balance, data: GameData) -> float:
    # money-exact: rate (actuators' cost a humanoid, rounded where a unit's BOM is posted)
    return file(data).humanoids.actuator_cents * actuator_index(state, balance)


def unit_extra_cents(state: GameState, product: Product, balance: Balance, data: GameData) -> float:
    """What the BOM hook adds to a humanoid's base parts: its actuators."""
    return actuator_cents(state, balance, data)


def made_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Phase 9 from the era's arrival: the world's humanoids made this month (real units: every
    humanoid market's replacements over robotics.scale) join the learning curve."""
    if era_turn(state, data) is None:
        return state
    rb = balance.robotics
    units = 0.0
    cat = data.category(rb.humanoid)
    rows = [(m.segment, m.addressable) for m in state.markets if m.category == rb.humanoid]
    rows += [
        (m.segment, m.addressable) for m in state.regional_markets if m.category == rb.humanoid
    ]
    for segment, addressable in rows:
        mdef = cat.market(segment)
        months = mdef.replacement_months or MONTHS
        units += addressable / months * mdef.units_per_customer
    if units <= TINY:
        return state
    world = replace(
        state.robotics_world, actuator_units=state.robotics_world.actuator_units + units / rb.scale
    )
    return replace(state, robotics_world=world)


def effects(state: GameState, balance: Balance, data: GameData) -> dict[tuple[int, str], float]:
    """Feature points by (product, region) for the player's live humanoid lines."""
    hb = balance.robotics.humanoids
    home = home_region_of(state, balance, data)
    players = {c.id for c in player_companies(state)}
    out: dict[tuple[int, str], float] = {}
    for p in state.products:
        if p.company_id not in players or not is_humanoid(p, balance) or p.status not in SELLING:
            continue
        pts = hb.capability_points * (capability(state, p, balance) - HALF_SCORE)
        regions = {home} if state.segments_of(p.id) else set()
        regions |= {rs.region for rs in state.regional_segments_of(p.id)}
        for r in regions:
            out[(p.id, r)] = pts
    return out


def licence_entries(state: GameState, balance: Balance) -> list[LedgerEntry]:
    """After the month's sales: a licensed AI model's fee on each humanoid the player sold."""
    hb = balance.robotics.humanoids
    out: list[LedgerEntry] = []
    for row in state.production:
        if row.turn != state.turn or row.units <= 0:
            continue
        product = state.product(row.product_id)
        if product is None or not is_humanoid(product, balance):
            continue
        spec = state.humanoid_spec(product.id)
        ai = _live(state, spec.ai_product_id if spec else None, product.company_id, AI_CATEGORY)
        if ai is not None:
            continue
        cents = round(exact(row.units) * exact(hb.licence_cents))
        if cents > 0:
            out.append(
                LedgerEntry(
                    state.turn,
                    product.company_id,
                    f"AI model licence: {product.name}",
                    (LedgerLine(PLATFORM_FEES, cents), LedgerLine(CASH, -cents)),
                )
            )
    return out
