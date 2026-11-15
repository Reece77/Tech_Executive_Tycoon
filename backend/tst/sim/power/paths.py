"""Regions' power paths after 2025 (docs/formulas.md 46.3, 46.4): each year's carbon price, grid
carbon intensity and median queue wait, drawn in the year's first month from the last year's
(the data's for 2026), on stream power (0, region_index). Only the current year is kept (46.9:
nothing ahead is stored).

- **Carbon:** a region with a price moves by exp(drift + sd x z), and with chance `step_rate` a
  policy step raises it by a draw in `step`; a region without one starts a scheme with chance
  `start_rate` at a draw in `start_price`.
- **Intensity:** falls by `decarbonise` (+ sd x z) a year, never below zero.
- **Queue wait:** the median grows by `growth` x the region's load growth a year, x exp(sd x z),
  inside `floor_months`..`cap_months`.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.power import grid
from tst.sim.power.config import interp
from tst.sim.power.models import RegionPath
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

REGION_FAMILY: Final = 0  # tunable-exempt: stream power family (0, region_index)
HISTORY_YEAR: Final = 2025  # tunable-exempt: the data's last year
PATH_TAG: Final = 1  # tunable-exempt: the third key part for a region's yearly path draw


def _previous(state: GameState, region: str, year: int, data: GameData) -> RegionPath:
    """Last year's path: the state's, else the data's 2025 values."""
    p = next((x for x in state.region_paths if x.region == region and x.year == year - 1), None)
    if p is not None:
        return p
    assert data.power is not None
    r = data.power.region(region)
    return RegionPath(
        region=region,
        year=HISTORY_YEAR,
        carbon=r.carbon_at(HISTORY_YEAR),
        intensity=interp(r.grid_intensity, HISTORY_YEAR),
        queue_months=interp(r.queue_months, HISTORY_YEAR),
    )


def step_region(
    prev: RegionPath,
    year: int,
    draws: tuple[float, float, float, float, float],
    growth: float,
    region: str,
    balance: Balance,
) -> RegionPath:
    """One region's year from last year's (module docstring). `draws`: two standard normals
    (carbon, intensity), a uniform for the step or start, a uniform for its size, and a normal
    for the queue."""
    cb, qb = balance.power.carbon, balance.power.queue
    z_c, z_i, u, v, z_q = draws
    if prev.carbon > 0:
        carbon = prev.carbon * math.exp(cb.drift[region] + cb.sd * z_c)
        if u < cb.step_rate:
            carbon *= 1 + cb.step.lo + (cb.step.hi - cb.step.lo) * v
    elif u < cb.start_rate[region]:
        carbon = cb.start_price.lo + (cb.start_price.hi - cb.start_price.lo) * v
    else:
        carbon = 0.0
    intensity = max(0.0, prev.intensity * (1 - cb.decarbonise[region] + cb.decarbonise_sd * z_i))
    queue = prev.queue_months * (1 + qb.growth * growth) * math.exp(qb.sd * z_q)
    queue = min(qb.cap_months, max(qb.floor_months, queue))
    return RegionPath(
        region=region, year=year, carbon=carbon, intensity=intensity, queue_months=queue
    )


def paths_month(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """In a year's first month from power.start (or a save's first month after it), every
    region's path for the year; earlier years are dropped."""
    if data.power is None or state.turn < month_to_turn(balance.power.start):
        return state
    year, _ = turn_to_ym(state.turn)
    if any(p.year == year for p in state.region_paths):
        return state
    out = []
    for i, r in enumerate(data.power.regions):
        gen = rng.stream(state.turn, "power", REGION_FAMILY, i, PATH_TAG)
        z_c, z_i, z_q = (float(x) for x in gen.standard_normal(3))
        u, v = (float(x) for x in gen.random(2))
        prev = _previous(state, r.key, year, data)
        out.append(step_region(prev, year, (z_c, z_i, u, v, z_q), r.demand_growth, r.key, balance))
    return replace(state, region_paths=tuple(out))


__all__ = ["grid", "paths_month", "step_region"]
