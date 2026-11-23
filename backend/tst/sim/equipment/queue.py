"""ASML's queue (docs/formulas.md 47.2).

**Orders.** Each December every rival buyer tops its open orders of each queued generation up to
`rival_order_share x next year's capacity x its share` (equipment.yaml `buyers`; from
`equipment.start` a Chinese foundry no rule blocks orders `china_share` instead of its zero
share). The player orders when it builds or converts a fab (the tools it lacks) or from the
Equipment screen (into its stock), any month.

**Allocation** ("queue order x buyer weight"). In each quarter's first month the quarter's tools
(tst.sim.equipment.data) go to open orders in order of their **place**

    place = month placed - history_months x min(1, delivered_5y / history_tools)
            - prepay_months x [prepaid] + jitter_months x (u - 0.5),

each order taking all it still needs before the next is served, `delivered_5y` the buyer's tools
from ASML in the last `history_years` (every generation) and `u` one uniform an order (stream
equipment, key (0, generation index), in id order). Ties go to the lower id. So a long-standing
buyer's December orders overtake a new buyer's orders placed up to `history_months` earlier, and
a new buyer waits behind a year or more of book. A blocked order (tst.sim.equipment.controls) is
lost first.

**Lead time** shown at ordering is a range: the same allocation run forward (no jitter, rivals'
December orders as above) with the order's place `estimate_months` earlier and later. It never
shows the place or the weight itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.equipment import controls as ec
from tst.sim.equipment import data as ed
from tst.sim.equipment.config import MONTHS, GenerationDef
from tst.sim.equipment.draws import ALLOCATION, gen
from tst.sim.equipment.models import Delivery, ToolOrder
from tst.sim.modes.models import world_start_turn
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

PLAYER: Final = ec.PLAYER
CHINA: Final = "china"  # tunable-exempt: countries.yaml key
DECEMBER: Final = 11  # tunable-exempt: calendar (turn % 12)
HORIZON_YEARS: Final = 12  # tunable-exempt: how far a lead-time estimate looks
NEVER: Final = 10**6  # tunable-exempt: a turn no game reaches
MID: Final = 0.5  # tunable-exempt: a uniform's middle (no jitter)


@dataclass(frozen=True, slots=True)
class Lead:
    """A lead-time range at ordering: the months until the last tool arrives."""

    low: int | None  # None: not within the horizon
    high: int | None


def buyer_key(order: ToolOrder) -> tuple[str, int | None]:
    return (order.buyer, order.company_id if order.buyer == PLAYER else None)


def history_tools(
    state: GameState, buyer: str, company_id: int | None, turn: int, years: int
) -> int:
    since = turn - years * MONTHS
    return sum(
        d.tools
        for d in state.tool_deliveries
        if d.buyer == buyer
        and (buyer != PLAYER or d.company_id == company_id)
        and d.turn >= since
        and d.source == "asml"
    )


def buyer_months(state: GameState, buyer: str, company_id: int | None, balance: Balance) -> float:
    """How many months the buyer's history moves its orders up (hidden)."""
    qb = balance.equipment.queue
    got = history_tools(state, buyer, company_id, state.turn, qb.history_years)
    return qb.history_months * min(1.0, got / qb.history_tools)


def place(order: ToolOrder, history: float, balance: Balance, shift: float = 0.0) -> float:
    """An order's place in the queue (module docstring); lower is served first."""
    qb = balance.equipment.queue
    p = order.placed_turn - history - shift + qb.jitter_months * (order.jitter - MID)
    if order.prepaid:
        p -= qb.prepay_months
    return p


def allocate(orders: list[ToolOrder], places: dict[int, float], tools: int) -> dict[int, int]:
    """The quarter's `tools` among `orders` in order of place (module docstring)."""
    got = {o.id: 0 for o in orders}
    for o in sorted(orders, key=lambda o: (places[o.id], o.id)):
        if tools <= 0:
            break
        n = min(tools, o.remaining)
        got[o.id] = n
        tools -= n
    return got


def next_order_id(state: GameState) -> int:
    return max((o.id for o in state.tool_orders), default=0) + 1


def _jitters(rng: RngFactory, turn: int, index: int, n: int) -> list[float]:
    if n == 0:
        return []
    return [float(x) for x in gen(rng, turn, ALLOCATION, index).random(n)]


def quarter(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[ToolOrder], list[tuple[ToolOrder, str]]]:
    """A quarter's allocation for every queued generation (in a quarter's first month).
    Returns the state, the orders that got tools (as updated) and the orders lost to a rule."""
    ef = ed.equipment_file(data)
    orders = {o.id: o for o in state.tool_orders}
    lost: list[tuple[ToolOrder, str]] = []
    served: list[ToolOrder] = []
    deliveries = list(state.tool_deliveries)
    for index, g in enumerate(ef.generations):
        if not g.queued:
            continue
        open_ = [o for o in orders.values() if o.generation == g.key and o.status == "open"]
        live: list[ToolOrder] = []
        for o in open_:
            why = ec.order_blocked(state, data, o)
            if why is not None:
                orders[o.id] = replace(o, status="lost", done_turn=state.turn)
                lost.append((orders[o.id], why))
            else:
                live.append(o)
        tools = ed.quarter_tools(state, g, state.turn)
        if not live or tools <= 0:
            continue
        live.sort(key=lambda o: o.id)
        us = _jitters(rng, state.turn, index, len(live))
        live = [replace(o, jitter=u) for o, u in zip(live, us, strict=True)]
        months = {buyer_key(o): buyer_months(state, o.buyer, o.company_id, balance) for o in live}
        places = {o.id: place(o, months[buyer_key(o)], balance) for o in live}
        got = allocate(live, places, tools)
        for o in live:
            n = got[o.id]
            if n <= 0:
                orders[o.id] = replace(orders[o.id], jitter=o.jitter)
                continue
            done = o.delivered + n >= o.tools
            new = replace(
                o,
                delivered=o.delivered + n,
                status="done" if done else "open",
                done_turn=state.turn if done else None,
            )
            orders[o.id] = new
            served.append(new)
            deliveries.append(
                Delivery(state.turn, o.buyer, g.key, n, o.company_id if o.buyer == PLAYER else None)
            )
    keep = state.turn - balance.equipment.queue.history_years * MONTHS
    state = replace(
        state,
        tool_orders=tuple(sorted(orders.values(), key=lambda o: o.id)),
        tool_deliveries=tuple(d for d in deliveries if d.turn >= keep),
    )
    return state, served, lost


def rival_targets(
    state: GameState, g: GenerationDef, year: int, balance: Balance, data: GameData
) -> dict[str, int]:
    """Each rival buyer's December target of open tools for `year` (module docstring)."""
    qb = balance.equipment.queue
    cap = ed.capacity(state, g, year)
    out: dict[str, int] = {}
    ef = ed.equipment_file(data)
    for buyer, share in g.buyers.items():
        country = ef.buyer_countries[buyer]
        s = share
        if country == CHINA and ed.year_turn(year) > balance.equipment.start_turn - 1:
            blocked = ec.blocking(state, data, g.key, country, name=ec.buyer_name(data, buyer))
            s = qb.china_share if blocked is None else 0.0
        out[buyer] = math.ceil(qb.rival_order_share * cap * s) if s > 0 else 0
    return out


def catch_up(state: GameState, balance: Balance, data: GameData) -> GameState:
    """A save from before M33 (no orders after turn 0): rivals' recent deliveries from
    equipment.yaml (their history weight) and this year's book, as at turn 0."""
    first = world_start_turn(state.mode)  # M50: a new game's first month, not turn 0
    if state.tool_orders or state.tool_deliveries or state.supplier_years or state.turn == first:
        return state
    ef = ed.equipment_file(data)
    qb = balance.equipment.queue
    deliveries = list(state.tool_deliveries)
    year = ed.year_of(state.turn)
    for g in ef.queued():
        for y in range(year - qb.history_years, year):
            for buyer, share in g.buyers.items():
                n = (
                    round(g.shipments_in(y) * share)
                    if y >= ed.year_of(g.first_shipment_turn)
                    else 0
                )
                if n > 0:
                    deliveries.append(Delivery(max(0, ed.year_turn(y)), buyer, g.key, n))
    state = replace(state, tool_deliveries=tuple(deliveries))
    return december_orders(state, balance, data, force=True)


def december_orders(
    state: GameState, balance: Balance, data: GameData, *, force: bool = False
) -> GameState:
    """Rivals' December orders for next year (and at turn 0, or `force`, for this year), every
    queued generation shipping by then."""
    turn = state.turn
    now = turn == world_start_turn(state.mode) or force  # M50: the world's first month
    if turn % MONTHS != DECEMBER and not now:
        return state
    year = ed.year_of(turn) + (0 if now else 1)
    ef = ed.equipment_file(data)
    orders = list(state.tool_orders)
    next_id = next_order_id(state)
    for g in ef.queued():
        if ed.year_turn(year + 1) <= g.first_shipment_turn:
            continue
        for buyer, target in rival_targets(state, g, year, balance, data).items():
            have = sum(
                o.remaining
                for o in orders
                if o.buyer == buyer and o.generation == g.key and o.status == "open"
            )
            want = target - have
            if want <= 0:
                continue
            orders.append(
                ToolOrder(
                    id=next_id,
                    buyer=buyer,
                    generation=g.key,
                    tools=want,
                    placed_turn=turn,
                    country=ef.buyer_countries[buyer],
                    price_cents=ed.price_cents(state, g, balance),
                )
            )
            next_id += 1
    cut = turn - balance.equipment.queue.history_years * MONTHS
    orders = [o for o in orders if o.status == "open" or (o.done_turn or turn) >= cut]
    return replace(state, tool_orders=tuple(orders))


# --- lead-time estimates -----------------------------------------------------------------------


def estimate_turn(
    state: GameState,
    order: ToolOrder,
    balance: Balance,
    data: GameData,
    shift: float = 0.0,
) -> int | None:
    """When `order` (not yet in the state, or in it) would get its last tool: the allocation run
    forward without jitter, rivals ordering as each December, the order's place `shift` months
    earlier. None beyond the horizon or while a rule blocks it."""
    if ec.order_blocked(state, data, order) is not None:
        return None
    g = ed.equipment_file(data).generation(order.generation)
    orders = [
        o
        for o in state.tool_orders
        if o.generation == g.key and o.status == "open" and o.id != order.id
    ]
    orders.append(order)
    orders = [replace(o, jitter=MID) for o in orders if ec.order_blocked(state, data, o) is None]
    end = state.turn + HORIZON_YEARS * MONTHS
    sim = replace(state, tool_orders=tuple(orders))
    months = {buyer_key(o): buyer_months(state, o.buyer, o.company_id, balance) for o in orders}
    t = state.turn
    while t <= end:
        sim = replace(sim, turn=t)
        if t % MONTHS == DECEMBER and t > state.turn:
            sim = _rival_topup(sim, g, balance, data)
            for o in sim.tool_orders:
                months.setdefault(buyer_key(o), balance.equipment.queue.history_months)
        tools = ed.quarter_tools(sim, g, t)
        live = [o for o in sim.tool_orders if o.status == "open"]
        if tools > 0 and live:
            places = {
                o.id: place(o, months[buyer_key(o)], balance, shift if o.id == order.id else 0.0)
                for o in live
            }
            got = allocate(live, places, tools)
            updated = []
            for o in sim.tool_orders:
                n = got.get(o.id, 0)
                if n:
                    done = o.delivered + n >= o.tools
                    o = replace(o, delivered=o.delivered + n, status="done" if done else "open")
                updated.append(o)
            sim = replace(sim, tool_orders=tuple(updated))
            mine = next(o for o in sim.tool_orders if o.id == order.id)
            if mine.status == "done":
                return t
        t += 1
    return None


def _rival_topup(state: GameState, g: GenerationDef, balance: Balance, data: GameData) -> GameState:
    year = ed.year_of(state.turn) + 1
    orders = list(state.tool_orders)
    nid = max((o.id for o in orders), default=0) + 1
    for buyer, target in rival_targets(state, g, year, balance, data).items():
        have = sum(o.remaining for o in orders if o.buyer == buyer and o.status == "open")
        if target - have > 0:
            orders.append(
                ToolOrder(
                    nid,
                    buyer,
                    g.key,
                    target - have,
                    state.turn,
                    jitter=MID,
                    country=ed.equipment_file(data).buyer_countries[buyer],
                )
            )
            nid += 1
    return replace(state, tool_orders=tuple(orders))


def lead(state: GameState, order: ToolOrder, balance: Balance, data: GameData) -> Lead:
    """The range shown at ordering, in months from now (module docstring)."""
    spread = balance.equipment.queue.estimate_months
    fast = estimate_turn(state, order, balance, data, spread)
    slow = estimate_turn(state, order, balance, data, -spread)
    return Lead(
        None if fast is None else fast - state.turn,
        None if slow is None else slow - state.turn,
    )
