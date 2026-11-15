"""ASML's December rule (docs/formulas.md 47.1), from `equipment.start`.

Each December (and, for the first year after the history, in `equipment.start`'s month) ASML sets
each queued generation's capacity for next year on its order book: when open orders exceed
`expand_backlog_years` x this year's capacity it builds to its plan (equipment.yaml
`capacity_plan`, linear from the last shipments, then `plan_growth` a year), never shrinking;
otherwise capacity grows `hold_growth`. After a year in which the player sold its own tools,
ASML's newest generation grows `accelerate` more and every generation's price multiplier falls
`sales.asml_cut` (to at most `asml_cut_max` below list): ASML's response (47.4). The new year's
record is public from the December it is set (41.9: capex intentions only once announced).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.equipment import data as ed
from tst.sim.equipment.config import MONTHS, GenerationDef
from tst.sim.equipment.models import SupplierYear
from tst.sim.state import GameState

DECEMBER = 11  # tunable-exempt: calendar (turn % 12)


def _sold_last_year(state: GameState) -> bool:
    """The player sold own tools in the 12 months before this one (its December sales are
    after this December's rule, so they count the next December)."""
    return any(
        d.source == "own" and d.buyer != "player" and state.turn - MONTHS <= d.turn < state.turn
        for d in state.tool_deliveries
    )


def next_capacity(
    state: GameState, g: GenerationDef, year: int, balance: Balance, newest: bool, sold: bool
) -> int:
    cb = balance.equipment.capacity
    now = ed.capacity(state, g, year - 1)
    book = ed.open_tools(state, g.key)
    if book > cb.expand_backlog_years * max(1, now):
        target = max(float(now), ed.plan(g, year, cb.plan_growth))
    else:
        target = now * (1 + cb.hold_growth)
    if newest and sold:
        target *= 1 + cb.accelerate
    return max(now, round(target))


def december(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Set next year's capacity (module docstring). In `equipment.start`'s month it also sets
    that year's, if the history ends before it."""
    eb = balance.equipment
    turn = state.turn
    first = turn == eb.start_turn
    if turn < eb.start_turn - 1 or (turn % MONTHS != DECEMBER and not first):
        return state
    ef = ed.equipment_file(data)
    queued = ef.queued()
    years = []
    if first:
        years.append(ed.year_of(turn))
    if turn % MONTHS == DECEMBER and turn >= eb.start_turn:
        years.append(ed.year_of(turn) + 1)
    records = list(state.supplier_years)
    for year in years:
        sold = _sold_last_year(state)
        for g in queued:
            if year <= g.last_year or ed.supplier_year(state, g.key, year) is not None:
                continue
            cap = next_capacity(state, g, year, balance, g is queued[-1], sold)
            prev = ed.price_mult(state, g.key)
            mult = prev
            if sold:
                mult = max(1 - eb.sales.asml_cut_max, prev * (1 - eb.sales.asml_cut))
            rec = SupplierYear(g.key, year, cap, mult)
            records.append(rec)
            state = replace(state, supplier_years=tuple(records))
    return replace(state, supplier_years=tuple(records))
