"""Each region's rate index and policy rate (docs/formulas.md 64.4, ADR-0025 points 2 and 6).

**Index.** To December 2025 the index is fx_history.yaml's (built exactly at load, x INDEX_SCALE;
an index of 1,000,000 is January 2010's value). From `fx.applies_from` each region's index walks,
one month at a time as months come (stream `fx` (region index, month)):

    ln I_t = ln I_{t-1} + reversion x (ln A_t - ln I_{t-1}) + sigma_region x z  (+/- ln(1 +
    jump_size)
             with chance jump_chance)
    A_t    = I_{Dec 2025} x (1 + drift_region) ** (months since December 2025 / 12)

with `dmath`'s exp and log (identical on every platform), rounded to an integer index. The home
region's (north_america's) index is 1 always.

**Policy rate** (% a year): the data's to December 2025 (the home region's is FEDFUNDS, as
macro_history.yaml's base rate); after, the home region's is the macro layer's base rate and every
other region's its December 2025 rate + `fx.rate_comove` x the home rate's move since.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.finance import macro
from tst.sim.fx.config import INDEX_SCALE, MONTHS, FxFile
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def file(data: GameData) -> FxFile | None:
    return data.fx


def enabled(data: GameData) -> bool:
    return data.fx is not None


def index_at(state: GameState, region: str, turn: int, balance: Balance, data: GameData) -> int:
    """The region's index (x INDEX_SCALE) in month `turn` (at most this month's: the walk's future
    months do not exist)."""
    f = data.fx
    xb = balance.fx
    if f is None or region == xb.home:
        return INDEX_SCALE
    start = xb.start_turn
    if turn < start:
        return f.history_index(region, turn)
    walk = state.fx.walk_of(region)
    if not walk:
        return f.history_index(region, start - 1)
    return walk[min(turn - start, len(walk) - 1)]


def policy_rate(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """The region's policy rate this month, % a year (module docstring)."""
    f = data.fx
    xb = balance.fx
    start = xb.start_turn
    if f is None or region == xb.home:
        return macro.base_rate(state, data)
    if state.turn < start:
        return f.history_rate(region, state.turn)
    move = macro.base_rate(state, data) - f.history_rate(xb.home, start - 1)
    return f.history_rate(region, start - 1) + xb.rate_comove * move


def walk_month(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """This month's step of every region's walk, once, from `fx.applies_from` (module docstring)."""
    f = data.fx
    xb = balance.fx
    start = xb.start_turn
    if f is None or state.turn < start:
        return state
    k = state.turn - start
    rows = dict(state.fx.walk)
    changed = False
    for ri, region in enumerate(data.region_keys):
        if region == xb.home:
            continue
        walk = rows.get(region, ())
        if len(walk) > k:
            continue
        last = f.history_index(region, start - 1)
        while len(walk) <= k:
            turn = start + len(walk)
            prev = walk[-1] if walk else last
            months = turn - (start - 1)
            ln_prev = dmath.log(prev / INDEX_SCALE)
            ln_anchor = dmath.log(last / INDEX_SCALE) + dmath.log(1.0 + xb.drift[region]) * (
                months / MONTHS
            )
            g = rng.stream(turn, "fx", ri, turn)
            z = float(g.standard_normal())
            u = float(g.random())
            up = float(g.random()) < 0.5  # tunable-exempt: a jump is up or down with equal odds
            step = xb.reversion * (ln_anchor - ln_prev) + xb.sigma[region] * z
            if u < xb.jump_chance:
                jump = dmath.log(1.0 + xb.jump_size)
                step += jump if up else -jump
            walk = (*walk, max(1, round(dmath.exp(ln_prev + step) * INDEX_SCALE)))
        rows[region] = walk
        changed = True
    if not changed:
        return state
    walk_rows = tuple((r, rows[r]) for r in data.region_keys if r in rows)
    return replace(state, fx=replace(state.fx, walk=walk_rows))
