"""Regional cycles (docs/formulas.md 41.6): after 2025 each region's demand multiplier is an
AR(1) around 1 plus a recession or boom when one runs, independent across regions except a
global shock that hits all.

Draws (stream world), every month in this order whether used or not: key `(2,)` one uniform for
a global shock's start, then a uniform for its depth and one for its months; then each region
in regions.yaml order, key `(1, region_index)`: a standard normal for the AR(1), then uniforms
for a phase's start, kind, depth and months. A phase starts only in a region with none
running; a global shock replaces any running phase in every region. A phase's effect is a sine
arch to its depth (`formulas.phase_effect`). Markets in a region grow by the ratio of this
month's multiplier to last month's (tst.sim.products.phases.brand_and_demand).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.rng import RngFactory
from tst.sim.state import GameState
from tst.sim.world import draws
from tst.sim.world import formulas as wf
from tst.sim.world.models import RegionCycle
from tst.sim.world.news import Item

MONTHS: Final = 12  # tunable-exempt: calendar
GLOBAL_DRAWS, REGION_DRAWS = 3, 4  # tunable-exempt: uniforms a month (module docstring)


def _label(data: GameData, region: str) -> str:
    return data.region(region).label


def cycles_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[Item]]:
    cb = balance.world.cycle
    turn = state.turn
    g = draws.gen(rng, turn, draws.GLOBAL)
    g_start, g_depth, g_months = (float(x) for x in g.random(GLOBAL_DRAWS))
    shock = g_start < balance.world.global_shock_rate / MONTHS
    news: list[Item] = []
    if shock:
        depth = -wf.lerp(cb.global_depth.lo, cb.global_depth.hi, g_depth)
        months = wf.whole_months(cb.months.lo, cb.months.hi, g_months)
        news.append(Item("cycle", f"A global shock: demand falls {-depth:.0%} in every region"))
    out: list[RegionCycle] = []
    by_region = {c.region: c for c in state.region_cycles}
    for i, region in enumerate(data.regions):
        c = by_region.get(region.key, RegionCycle(region=region.key, turn=turn - 1))
        gen = draws.gen(rng, turn, draws.CYCLE, i)
        z = float(gen.standard_normal())
        start, kind, depth_u, months_u = (float(x) for x in gen.random(REGION_DRAWS))
        level = wf.ar1_level(c.level, cb.phi, cb.sd, z)
        running = c.phase != "none" and turn < c.phase_start + c.phase_months
        if shock:
            c = replace(c, phase="global", phase_start=turn, phase_months=months, depth=depth)
        elif not running:
            c = replace(c, phase="none", phase_months=0, depth=0.0)
            rate = (cb.recession_rate + cb.boom_rate) / MONTHS
            if start < rate:
                recession = kind * (cb.recession_rate + cb.boom_rate) < cb.recession_rate
                span = cb.recession_depth if recession else cb.boom_depth
                d = wf.lerp(span.lo, span.hi, depth_u) * (-1 if recession else 1)
                n = wf.whole_months(cb.months.lo, cb.months.hi, months_u)
                c = replace(
                    c,
                    phase="recession" if recession else "boom",
                    phase_start=turn,
                    phase_months=n,
                    depth=d,
                )
                news.append(
                    Item(
                        "cycle",
                        f"{'Recession' if recession else 'A boom'} in {_label(data, region.key)}",
                        region=region.key,
                    )
                )
        effect = wf.phase_effect(c.depth, c.phase_months, turn - c.phase_start)
        out.append(
            replace(
                c, turn=turn, level=level, multiplier=level * (1 + effect), previous=c.multiplier
            )
        )
    return replace(state, region_cycles=tuple(out)), news


def growth_ratio(state: GameState, region: str, turn: int) -> float:
    """How a region's demand moves this month for its cycle (1 before 2026): this month's
    multiplier over last month's, once phase 7 has set this month's."""
    c = next((c for c in state.region_cycles if c.region == region), None)
    if c is None or c.turn != turn or c.previous <= 0:
        return 1.0
    return c.multiplier / c.previous
