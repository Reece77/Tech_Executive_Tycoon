"""Process nodes past the last seeded one (docs/formulas.md 52.2; M37).

**Windows (public, at load).** The first successor's window is centred `dynasty.nodes.gap_years`
after the last future node's window midpoint (A3's); each later gap is the one before x
(1 + gap_growth): Moore's law slows. A window is `window_months` wide and never starts before
January of dynasty.start_year, so no game to December 2039 is offered one.

**Economics (seeded, engine only).** Successor j's month in its window, wafer price, capital per
wafer-per-year and transistor density gain come from stream `dynasty`, key (SERIES, NODES, j) at
turn 0: a pure function of the seed, as 38.1's future nodes are. The wafer price and capital
are the previous node's x a draw in `wafer_mult` and `capital_mult`; the density gain of step k
is 1 + (the first step's draw - 1) x density_decay^k, so cost per transistor falls less each
step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tst.sim import dmath
from tst.sim.calendar import ym_to_turn
from tst.sim.dynasty.config import DynastyBalance
from tst.sim.dynasty.draws import NODES, SERIES, gen
from tst.sim.fabs.config import FutureNodeDef, NodesFile
from tst.sim.facilities.config import month_to_turn
from tst.sim.rng import RngFactory

MONTHS = 12  # tunable-exempt: calendar
JANUARY = 1  # tunable-exempt: calendar month


def _month(turn: int) -> str:
    year, month = divmod(turn, MONTHS)
    return f"{2010 + year:04d}-{month + 1:02d}"  # tunable-exempt: turn 0 is January 2010


def with_successors(nodes: NodesFile, rule: DynastyBalance) -> NodesFile:
    """nodes.yaml with `dynasty_future` filled from its `successors` and dynasty.nodes."""
    if not nodes.successors:
        return nodes
    last = nodes.future[-1] if nodes.future else None
    if last is not None:
        mid = last.start_turn + last.months // 2
    else:
        mid = month_to_turn(nodes.nodes[-1].first[next(iter(nodes.nodes[-1].first))])
    first_allowed = ym_to_turn(rule.start_year, JANUARY)
    nr = rule.nodes
    gap = nr.gap_years * MONTHS
    out: list[FutureNodeDef] = []
    # M52 (66.3): `beyond.nodes` more, their windows after 2069 (the gaps keep growing)
    for s in nodes.successors[: nr.count + rule.beyond.nodes]:
        mid += round(gap)
        gap *= 1 + nr.gap_growth
        start = max(first_allowed, mid - nr.window_months // 2)
        end = max(start, start + nr.window_months - 1)
        out.append(FutureNodeDef(key=s.key, label=s.label, window=(_month(start), _month(end))))
    return nodes.model_copy(update={"dynasty_future": tuple(out), "dynasty_rule": nr})


@dataclass(frozen=True, slots=True)
class Successor:
    key: str
    arrival: int  # the scheduled month (hidden until it arrives)
    wafer_mult: float
    capital_mult: float
    density_gain: float  # x transistor density over the previous node


def successors(seed: int, nodes: NodesFile) -> tuple[Successor, ...]:
    """Every successor's seeded draws (engine only)."""
    nr = nodes.dynasty_rule
    if nr is None:
        return ()
    rng = RngFactory(seed)
    first_gain: float | None = None
    out = []
    for j, fut in enumerate(nodes.dynasty_future):
        drawn = gen(rng, 0, SERIES, NODES, j).random(4)  # tunable-exempt: four draws
        u, w, c, d = (float(x) for x in drawn)
        if first_gain is None:
            first_gain = nr.density.at(d)
        gain = 1 + (first_gain - 1) * dmath.pow(nr.density_decay, j)
        out.append(
            Successor(
                key=fut.key,
                arrival=fut.start_turn + min(fut.months - 1, math.floor(u * fut.months)),
                wafer_mult=nr.wafer_mult.at(w),
                capital_mult=nr.capital_mult.at(c),
                density_gain=gain,
            )
        )
    return tuple(out)


def density(seed: int, nodes: NodesFile, key: str) -> float:
    """A node's transistor density relative to the last future node (A3 = 1), for 52.5
    target 3. An earlier future node is A3 / the first step's gain for each step back."""
    steps = successors(seed, nodes)
    gains = {s.key: s.density_gain for s in steps}
    if key in gains:
        value = 1.0
        for s in steps:
            value *= s.density_gain
            if s.key == key:
                return value
    keys = [n.key for n in nodes.future]
    first = steps[0].density_gain if steps else 1.0
    if key in keys:
        return float(dmath.pow(first, keys.index(key) - (len(keys) - 1)))
    return float(dmath.pow(first, -(len(keys) + 1)))
