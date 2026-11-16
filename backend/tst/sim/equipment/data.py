"""What equipment.yaml and the state say about tools, as pure functions (docs/formulas.md 47.1-
47.2): a generation's capacity a year, a quarter's deliveries, prices with scarcity, throughput
and uptime.

Capacity a year is the history's shipments to its last year (2025), then the `SupplierYear` that
ASML's December rule set (tst.sim.equipment.capacity). A quarter delivers
`floor(C x (q + 1) / 4) - floor(C x q / 4)` tools (q = 0..3), so a year's quarters sum to its
capacity exactly.
"""

from __future__ import annotations

import math
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.equipment.config import (
    FIRST_YEAR,
    MONTHS,
    EquipmentFile,
    GenerationDef,
    year_series,
)
from tst.sim.equipment.models import SupplierYear
from tst.sim.state import GameState

QUARTERS: Final = 4  # tunable-exempt: calendar
QUARTER_MONTHS: Final = 3  # tunable-exempt: calendar


def equipment_file(data: GameData) -> EquipmentFile:
    if data.equipment is None:
        raise RuntimeError("equipment.yaml is not loaded")
    return data.equipment


def enabled(data: GameData) -> bool:
    return data.equipment is not None and data.nodes is not None


def year_of(turn: int) -> int:
    return FIRST_YEAR + turn // MONTHS


def year_turn(year: int) -> int:
    return (year - FIRST_YEAR) * MONTHS


def is_quarter_start(turn: int) -> bool:
    return turn % QUARTER_MONTHS == 0


def supplier_year(state: GameState, generation: str, year: int) -> SupplierYear | None:
    for s in state.supplier_years:
        if s.generation == generation and s.year == year:
            return s
    return None


def capacity(state: GameState, g: GenerationDef, year: int) -> int:
    """Tools of `g` ASML makes in `year` (module docstring)."""
    if year <= g.last_year:
        return g.shipments_in(year)
    rec = supplier_year(state, g.key, year)
    if rec is not None:
        return rec.capacity
    for y in range(year - 1, g.last_year, -1):
        prev = supplier_year(state, g.key, y)
        if prev is not None:
            return prev.capacity
    return g.shipments_in(g.last_year)


def quarter_tools(state: GameState, g: GenerationDef, turn: int) -> int:
    """Tools delivered in the quarter starting `turn` (0 off a quarter's first month)."""
    if not is_quarter_start(turn) or turn < g.first_shipment_turn:
        return 0
    cap = capacity(state, g, year_of(turn))
    q = (turn % MONTHS) // QUARTER_MONTHS
    return math.floor(cap * (q + 1) / QUARTERS) - math.floor(cap * q / QUARTERS)


def plan(g: GenerationDef, year: int, plan_growth: float) -> float:
    """ASML's capacity plan for `year`: linear from the last shipments to the plan's points,
    then growing `plan_growth` a year (47.1); the last shipments held without a plan."""
    last = g.last_year
    points = {
        last: float(g.shipments_in(last)),
        **{k: float(v) for k, v in g.capacity_plan.items()},
    }
    end = max(points)
    if year <= end:
        return year_series(points, year)
    return points[end] * dmath.pow(1 + plan_growth, year - end)


def base_price_cents(g: GenerationDef, turn: int, growth: float) -> float:
    """A tool's list price before scarcity: the data's (by year, linear) to its last point, then
    `growth` a year."""
    year = year_of(turn) + (turn % MONTHS) / MONTHS
    last = max(g.price_cents)
    if year <= last:
        return g.price_in(year)
    return float(g.price_in(last) * dmath.pow(1 + growth, year - last))


def open_tools(state: GameState, generation: str) -> int:
    return sum(
        o.remaining for o in state.tool_orders if o.generation == generation and o.status == "open"
    )


def scarcity(state: GameState, g: GenerationDef, balance: Balance) -> float:
    """1 to 2025; from equipment.start x (1 + scarcity x max(0, open / next year capacity - 1))."""
    eb = balance.equipment
    if state.turn < eb.start_turn:
        return 1.0
    nxt = max(1, capacity(state, g, year_of(state.turn) + 1))
    over = max(0.0, open_tools(state, g.key) / nxt - 1.0)
    return min(eb.price.max_scarcity, 1.0 + eb.price.scarcity * over)


def price_mult(state: GameState, generation: str) -> float:
    """ASML's response to the player's sales (47.4): the latest multiplier it set."""
    best: SupplierYear | None = None
    for s in state.supplier_years:
        if s.generation == generation and (best is None or s.year > best.year):
            best = s
    return 1.0 if best is None else best.price_mult


def price_cents(state: GameState, g: GenerationDef, balance: Balance) -> int:
    """A tool's price this month: list x scarcity x ASML's response."""
    base = base_price_cents(g, state.turn, balance.equipment.price.growth)
    return round(base * scarcity(state, g, balance) * price_mult(state, g.key))


def throughput(g: GenerationDef, turn: int) -> float:
    return g.model_in(year_of(turn)).wph


def uptime(g: GenerationDef, turn: int) -> float:
    return g.uptime_in(year_of(turn) + (turn % MONTHS) / MONTHS)


def generation_for(data: GameData, node: str) -> GenerationDef | None:
    """The queued generation a fab at `node` needs; a future node not listed takes the last
    queued generation (the newest tools)."""
    ef = equipment_file(data)
    g = ef.generation_for(node)
    if g is not None:
        return g
    assert data.nodes is not None
    if data.nodes.node(node) is None:
        return ef.queued()[-1]
    return None
