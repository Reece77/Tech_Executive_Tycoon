"""Licences, debris rules and the rivals' world after 2025 (docs/formulas.md 56.2-56.3).

- **Licences.** An application (`apply_licence`) is reviewed for at least the region's
  `licence.review_months`; then each month a decision comes with `decision_chance` (stream space
  (2, region_index, company_id)), granting with the region's `approval` chance, else refusing (the
  company may apply again). Neither the decision's month nor its draw is shown ahead.
- **Debris.** At `space.start` a month is drawn `debris.window` years ahead (stream space (0, 0)):
  from it, each satellite in orbit pays `debris.fee_cents` a month and disposal costs x
  `debris.deorbit_mult`. Before it comes it is never shown; when it comes the player is told.
- **Rivals' world.** From `space.start` each year's growth of rivals' launches and constellations
  is drawn in `rival_growth` (stream space (0, year)), a year ahead; their public figures (launches
  a year, satellites in orbit) follow space.yaml to 2025 and grow by these after it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.space import draws
from tst.sim.space.data import LAST_YEAR, MONTHS, file, year_at
from tst.sim.space.models import Licence
from tst.sim.state import GameState

APPLIED: Final = "applied"
GRANTED: Final = "granted"
REFUSED: Final = "refused"


def licences_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    lb = balance.space.licence
    turn = state.turn
    out: list[Licence] = []
    logs: list[LogItem] = []
    changed = False
    for lic in state.space.licences:
        if lic.status == APPLIED and lic.decision_turn is not None and turn >= lic.decision_turn:
            gen = draws.gen(rng, turn, draws.LICENCE, data.region_index(lic.region), lic.company_id)
            if float(gen.random()) < lb.decision_chance:
                region = data.region(lic.region).label
                if float(gen.random()) < lb.approval.get(lic.region, 0.0):
                    lic = replace(lic, status=GRANTED, granted_turn=turn, decision_turn=None)
                    logs.append(
                        inbox_item(turn, lic.company_id, "space_licence_granted", region=region)
                    )
                else:
                    lic = replace(lic, status=REFUSED, decision_turn=None)
                    logs.append(
                        inbox_item(turn, lic.company_id, "space_licence_refused", region=region)
                    )
                changed = True
        out.append(lic)
    if not changed:
        return state, logs
    return replace(state, space=replace(state.space, licences=tuple(out))), logs


def world_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Phase 9 from December 2025: the debris month (once) and rivals' growth a year ahead."""
    sb = balance.space
    start = sb.start_turn
    logs: list[LogItem] = []
    if state.turn < start - 1:
        return state, logs
    world = state.space.world
    if world.debris_turn is None:
        u = float(draws.gen(rng, start, draws.WORLD, 0, 0).random())
        years = sb.debris.window.lo + (sb.debris.window.hi - sb.debris.window.lo) * u
        world = replace(world, debris_turn=start + round(years * MONTHS))
    year = turn_to_ym(state.turn)[0]
    have = {y for y, _ in world.growth}
    growth = list(world.growth)
    for y in range(turn_to_ym(start)[0], year + 2):
        if y in have:
            continue
        u = float(draws.gen(rng, start, draws.WORLD, y).random())
        growth.append((y, sb.rival_growth.lo + (sb.rival_growth.hi - sb.rival_growth.lo) * u))
    world = replace(world, growth=tuple(sorted(growth)))
    if world.debris_turn == state.turn:
        for c in state.companies:
            if c.is_player:
                logs.append(inbox_item(state.turn, c.id, "space_debris_rule"))
    if world != state.space.world:
        state = replace(state, space=replace(state.space, world=world))
    return state, logs


def rival_factor(state: GameState, year: float) -> float:
    """Rivals' public figures over 2025's at `year` (1 to 2025, then the drawn growth)."""
    if year <= LAST_YEAR + 1:
        return 1.0
    f = 1.0
    y = LAST_YEAR + 1
    while y < int(year):
        g = state.space.world.growth_of(y)
        f *= 1 + (g if g is not None else 0.0)
        y += 1
    g = state.space.world.growth_of(int(year))
    return f * (1 + (g if g is not None else 0.0) * (year - int(year)))


def rival_launches(state: GameState, data: GameData, company: str) -> float:
    """A provider's launches a year (public: the data to 2025, then grown)."""
    p = file(data).launch.provider(company)
    if p is None:
        return 0.0
    year = year_at(state.turn)
    if year <= LAST_YEAR + 1:
        return p.launches_at(year)
    return p.launches_at(LAST_YEAR) * rival_factor(state, year)


def rival_satellites(state: GameState, data: GameData, key: str) -> float:
    c = file(data).constellation(key)
    if c is None:
        return 0.0
    year = year_at(state.turn)
    if year <= LAST_YEAR + 1:
        return c.satellites_at(year)
    return c.satellites_at(LAST_YEAR) * rival_factor(state, year)
