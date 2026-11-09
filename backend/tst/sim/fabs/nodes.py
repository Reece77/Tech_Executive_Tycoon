"""Process nodes and rival foundries (docs/formulas.md 38.1, 38.3): when each foundry reaches
each node, the leading edge, nodes' wafer prices and capital, and the foundries' capacity.

**History, then seeded.** To December 2025 every date and capacity is nodes.yaml's, the same on
every seed. After it, future nodes arrive in seeded windows (stream `era_window`, appended
keys), each rival foundry reaches a node its own lag behind the first (its research pace; a
foundry with `stops_at` or an `euv_gate` goes no further), and capacity grows by a seeded rate a
year. Everything is a pure function of the master seed (draws at turn 0), so nothing is stored
and a save made before M21 gets the same timeline. Engine only where it looks ahead: a future
node's month never reaches the API before it arrives (ADR-0007; `public_*` below).
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Final

from tst.sim.fabs.config import FabBalance, FoundryDef, NodesFile
from tst.sim.fabs.draws import FUTURE, GROWTH, LAG, fab_draws, node_window_draw
from tst.sim.facilities.config import month_to_turn
from tst.sim.rng import RngFactory

MONTHS: Final = 12
FIRST_YEAR: Final = 2010  # tunable-exempt: turn 0 is January 2010 (calendar definition)
HISTORY_END: Final = month_to_turn("2025-12")
NEVER: Final = 10**9  # tunable-exempt: a turn no game reaches


@dataclass(frozen=True, slots=True)
class Timeline:
    """The whole node timeline of one seed (engine only)."""

    keys: tuple[str, ...]  # nodes in generation order (historical, then future)
    reach: dict[tuple[str, str], int]  # (foundry, node) -> first-volume turn
    arrival: dict[str, int]  # node -> the first foundry's first-volume turn
    wafer_cents: dict[str, float]  # node -> market price at its reference
    capital_cents: dict[str, float]  # node -> capital per wafer-per-year
    price_turn: dict[str, int]  # node -> the turn its wafer_cents was read
    growth: dict[tuple[str, int], float]  # (foundry, year) -> capacity growth after 2025

    def generation(self, node: str) -> int:
        return self.keys.index(node)

    def leading(self, turn: int) -> str:
        """The newest node in volume anywhere by `turn` (65 nm before anything else)."""
        best = self.keys[0]
        for k in self.keys:
            if self.arrival[k] <= turn:
                best = k
        return best

    def behind(self, node: str, turn: int) -> int:
        """Generations `node` is behind the leading edge in `turn` (0 at the edge or ahead)."""
        return max(0, self.generation(self.leading(turn)) - self.generation(node))

    def reached(self, foundry: str, turn: int) -> tuple[str, ...]:
        return tuple(k for k in self.keys if self.reach.get((foundry, k), NEVER) <= turn)

    def foundry_has(self, foundry: str, node: str, turn: int) -> bool:
        return self.reach.get((foundry, node), NEVER) <= turn

    def median(self, turn: int, lag_months: int) -> str:
        """A chip category's median node (38.4): the newest whose first volume was at least
        `lag_months` ago."""
        return self.leading(turn - lag_months)


_CACHE: dict[tuple[int, int, int], Timeline] = {}


def _lerp(r_lo: float, r_hi: float, u: float) -> float:
    return r_lo + (r_hi - r_lo) * u


def build(seed: int, nodes: NodesFile, fb: FabBalance) -> Timeline:
    rng = RngFactory(seed)
    keys = nodes.node_keys()
    reach: dict[tuple[str, str], int] = {}
    for f in nodes.foundries:
        for n in nodes.nodes:
            month = f.reaches.get(n.key) or n.first.get(f.key)
            if month is not None:
                reach[(f.key, n.key)] = month_to_turn(month)
    arrival = {n.key: min(t for (_, k), t in reach.items() if k == n.key) for n in nodes.nodes}
    wafer = {n.key: float(n.wafer_cents) for n in nodes.nodes}
    capital = {n.key: float(n.capital_cents) for n in nodes.nodes}
    price_turn = {n.key: month_to_turn(n.price_month) for n in nodes.nodes}
    prev = nodes.nodes[-1].key
    for j, fut in enumerate(nodes.future):
        u = node_window_draw(rng, j)
        arrival[fut.key] = fut.start_turn + min(fut.months - 1, math.floor(u * fut.months))
        w, c = (float(x) for x in fab_draws(rng, 0, FUTURE, j).random(2))
        wafer[fut.key] = wafer[prev] * _lerp(fb.future_wafer_mult.lo, fb.future_wafer_mult.hi, w)
        capital[fut.key] = capital[prev] * _lerp(
            fb.future_capital_mult.lo, fb.future_capital_mult.hi, c
        )
        price_turn[fut.key] = arrival[fut.key]
        prev = fut.key
    for i, f in enumerate(nodes.foundries):
        if not _can_go_on(f):
            continue
        for fut in nodes.future:
            if _blocked(f, fut.key, keys):
                break
            g = keys.index(fut.key)
            u = float(fab_draws(rng, 0, LAG, i, g).random())
            reach[(f.key, fut.key)] = arrival[fut.key] + round(_lerp(f.lag.lo, f.lag.hi, u))
    # the first to a future node arrives at the scheduled month: the leader's lag counts
    for fut in nodes.future:
        got = [t for (_, k), t in reach.items() if k == fut.key]
        if got:
            arrival[fut.key] = min(got)
    growth: dict[tuple[str, int], float] = {}
    last_year = FIRST_YEAR + HISTORY_END // MONTHS
    for i, f in enumerate(nodes.foundries):
        gen = fab_draws(rng, 0, GROWTH, i)
        for y, u in enumerate(gen.random(_GROWTH_YEARS)):
            growth[(f.key, last_year + 1 + y)] = _lerp(
                fb.capacity.growth.lo, fb.capacity.growth.hi, float(u)
            )
    return Timeline(keys, reach, arrival, wafer, capital, price_turn, growth)


_GROWTH_YEARS: Final = 60  # tunable-exempt: years of capacity draws after 2025 (past any game)


def _can_go_on(f: FoundryDef) -> bool:
    return f.stops_at is None


def _blocked(f: FoundryDef, node: str, keys: tuple[str, ...]) -> bool:
    """A foundry with an EUV gate goes no further than it (38.3: SMIC without EUV tools)."""
    return f.euv_gate is not None and keys.index(node) > keys.index(f.euv_gate)


def timeline(seed: int, nodes: NodesFile, fb: FabBalance) -> Timeline:
    """The seed's timeline, memoized (a pure function of its arguments)."""
    key = (seed, id(nodes), id(fb))
    got = _CACHE.get(key)
    if got is None:
        if len(_CACHE) > _CACHE_SIZE:
            _CACHE.clear()
        got = _CACHE[key] = build(seed, nodes, fb)
    return got


_CACHE_SIZE: Final = 64  # tunable-exempt: memo entries kept


# --- Capacity (38.3) -------------------------------------------------------------------------


def _year_points(f: FoundryDef) -> list[tuple[int, float]]:
    return sorted((month_to_turn(f"{y}-01"), v) for y, v in f.capacity.items())


def history_capacity(f: FoundryDef, turn: int) -> float:
    """Thousand wafer starts a month, linear between the year points (held at the ends)."""
    pts = _year_points(f)
    if turn <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in itertools.pairwise(pts):
        if turn <= t1:
            return v0 + (v1 - v0) * (turn - t0) / (t1 - t0)
    return pts[-1][1]


def capacity(tl: Timeline, f: FoundryDef, turn: int, fb: FabBalance) -> float:
    """A foundry's capacity: history to December 2025, then its seeded growth (38.3)."""
    if turn <= HISTORY_END:
        return history_capacity(f, turn)
    return history_capacity(f, HISTORY_END) * _grown(tl, f.key, turn, None)


def expected_capacity(f: FoundryDef, turn: int, fb: FabBalance) -> float:
    """What the market expects: history, then the mean growth (the price's reference)."""
    if turn <= HISTORY_END:
        return history_capacity(f, turn)
    mean = (fb.capacity.growth.lo + fb.capacity.growth.hi) / 2
    growth = float((1 + mean) ** ((turn - HISTORY_END) / MONTHS))
    return history_capacity(f, HISTORY_END) * growth


def _grown(tl: Timeline, foundry: str, turn: int, rate: float | None) -> float:
    months = turn - HISTORY_END
    years, part = divmod(months, MONTHS)
    first = FIRST_YEAR + HISTORY_END // MONTHS + 1
    out = 1.0
    for y in range(years):
        out *= 1 + tl.growth[(foundry, first + y)]
    if part:
        out *= (1 + tl.growth[(foundry, first + years)]) ** (part / MONTHS)
    return out


def open_share(f: FoundryDef, turn: int) -> float:
    """The share of a foundry's capacity open to customers (an IDM's opens late)."""
    if f.open_from is not None and turn >= month_to_turn(f.open_from.month):
        return f.open_from.share
    return f.open_share


def market_capacity(tl: Timeline, nodes: NodesFile, turn: int, fb: FabBalance) -> float:
    return sum(capacity(tl, f, turn, fb) * open_share(f, turn) for f in nodes.foundries)


def market_expected(nodes: NodesFile, turn: int, fb: FabBalance) -> float:
    return sum(expected_capacity(f, turn, fb) * open_share(f, turn) for f in nodes.foundries)


def price_factor(
    tl: Timeline, nodes: NodesFile, turn: int, fb: FabBalance, player_slots: float
) -> float:
    """The foundry market's price factor (38.3): (expected / actual)^elasticity, actual being
    the rivals' open capacity plus the player's sold slots (thousand starts a month). Exactly
    1 through 2025 when the player sells none: M12b's prices (38.5 target 6)."""
    if turn <= HISTORY_END and player_slots <= 0:
        return 1.0
    actual = market_capacity(tl, nodes, turn, fb) + player_slots
    expected = market_expected(nodes, turn, fb)
    if actual <= 0:
        return fb.capacity.bounds.hi
    value = float((expected / actual) ** fb.capacity.elasticity)
    return min(fb.capacity.bounds.hi, max(fb.capacity.bounds.lo, value))


def allocation_factor(
    tl: Timeline, nodes: NodesFile, turn: int, fb: FabBalance, player_slots: float
) -> float:
    """Allocation in the foundry market x this (38.3): 1 through 2025 without the player's
    slots; after it, short when the rivals' capacity lags what the market expects."""
    if turn <= HISTORY_END and player_slots <= 0:
        return 1.0
    expected = market_expected(nodes, turn, fb)
    if expected <= 0:
        return 1.0
    actual = market_capacity(tl, nodes, turn, fb) + player_slots
    value = float((actual / expected) ** fb.capacity.elasticity)
    return min(fb.capacity.bounds.hi, max(fb.capacity.bounds.lo, value))


# --- EUV supply (38.2) -----------------------------------------------------------------------


def euv_shipments(nodes: NodesFile, year: int) -> float:
    """EUV tools ASML ships in a year: history, then its growth (0 before EUV)."""
    s = nodes.euv.shipments
    if year < min(s):
        return 0.0
    if year in s:
        return float(s[year])
    last = max(s)
    return s[last] * (1 + nodes.euv.shipments_growth) ** (year - last)
