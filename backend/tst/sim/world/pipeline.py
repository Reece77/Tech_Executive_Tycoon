"""The world starts with its pipeline (docs/formulas.md 41.2, M28r).

Capacity was already being built when the world starts: the first December decisions (December
2026) cannot land before the good's `build_months` after them, so without a pipeline every
good's capacity would stand still for one to three years while demand grows. Each facility the
world opens with (its `ordered_turn == ready_turn`, the first month) therefore grows month by
month, from the first month to the month before the first decisions can land, along its good's
pre-M28 path:

- a named foundry: 38.3's seeded capacity growth for that foundry (`nodes.capacity`), the path
  the foundry market read before M28; the "other producers" of foundry wafers: the named
  foundries' summed path;
- a commodity (M17's goods, M20's refined goods among them): the data's `demand_growth`, the
  path on which supply keeps pace with demand at `base_utilisation`, so the balance factor stays
  at 1 and prices follow M17's seeded path, as they did before M28.

`world.pipeline_share` scales the growth (1: all of the path is already under construction).
The pipeline was paid for before the world starts: its capex is in the opening books (41.1).
Pure functions of the state, data and balance.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.fabs import nodes as nd
from tst.sim.state import GameState
from tst.sim.world import data as wd
from tst.sim.world.config import FOUNDRY_GOOD
from tst.sim.world.models import WorldFacility

MONTHS: Final = 12  # tunable-exempt: calendar
DECEMBER: Final = 11  # tunable-exempt: the month index of December


def first_december(start: int) -> int:
    """The first December decision month at or after the world's first month."""
    return start + (DECEMBER - start % MONTHS)


def end_turn(start: int, good: str, data: GameData) -> int:
    """The last month the pipeline adds capacity: the month before the first December's
    decisions on the good can land."""
    return first_december(start) + wd.build_months(data, good) - 1


def is_opening(f: WorldFacility) -> bool:
    """A facility the world opened with (December decisions' builds arrive after their order)."""
    return f.ordered_turn == f.ready_turn


def _raw(
    state: GameState, good: str, key: str, start: int, turn: int, balance: Balance, data: GameData
) -> float:
    """The pre-M28 path's capacity in `turn` over its capacity in the month before `start`."""
    base = start - 1
    if good == FOUNDRY_GOOD:
        assert data.nodes is not None
        tl = nd.timeline(state.save_meta.master_seed, data.nodes, balance.fab)
        named = [f for f in data.nodes.foundries if f.key == key] or list(data.nodes.foundries)
        then = sum(nd.capacity(tl, f, base, balance.fab) for f in named)
        now = sum(nd.capacity(tl, f, turn, balance.fab) for f in named)
        return now / then if then > 0 else 1.0
    growth = wd.demand_growth(data, good)
    return float((1 + growth) ** ((turn - base) / MONTHS))


def ratio(
    state: GameState, good: str, key: str, start: int, turn: int, balance: Balance, data: GameData
) -> float:
    """An opening facility's capacity in `turn` over its opening capacity: the path to the
    pipeline's last month, held after it, scaled by `pipeline_share`."""
    t = max(start - 1, min(turn, end_turn(start, good, data)))
    raw = _raw(state, good, key, start, t, balance, data)
    return 1 + balance.world.pipeline_share * (raw - 1)


def keys(state: GameState) -> dict[int, str]:
    """Chain company id -> its data key (a foundry's nodes.yaml key, other_<good>, ...)."""
    return {c.company_id: c.key for c in state.chain_companies}


def grow(
    state: GameState, facilities: list[WorldFacility], balance: Balance, data: GameData
) -> list[WorldFacility]:
    """This month's pipeline arrivals: each opening facility, unless closed, steps from last
    month's point on its path to this month's."""
    turn = state.turn
    names = keys(state)
    cache: dict[tuple[str, str, int], float] = {}
    out = []
    for f in facilities:
        if not is_opening(f) or f.status == "closed":
            out.append(f)
            continue
        if turn > end_turn(f.ordered_turn, f.good, data):
            out.append(f)
            continue
        k = (f.good, names.get(f.company_id, ""), f.ordered_turn)
        step = cache.get(k)
        if step is None:
            now = ratio(state, f.good, k[1], f.ordered_turn, turn, balance, data)
            then = ratio(state, f.good, k[1], f.ordered_turn, turn - 1, balance, data)
            step = cache[k] = now / then if then > 0 else 1.0
        out.append(replace(f, capacity=f.capacity * step))
    return out


def committed(
    state: GameState, f: WorldFacility, balance: Balance, data: GameData, names: dict[int, str]
) -> float:
    """A facility's capacity once its pipeline has arrived (announced builds are public: rivals
    plan on them, 41.2)."""
    if not is_opening(f) or f.status == "closed":
        return f.capacity
    key = names.get(f.company_id, "")
    end = end_turn(f.ordered_turn, f.good, data)
    if state.turn >= end:
        return f.capacity
    now = ratio(state, f.good, key, f.ordered_turn, state.turn, balance, data)
    final = ratio(state, f.good, key, f.ordered_turn, end, balance, data)
    return f.capacity * final / now if now > 0 else f.capacity
