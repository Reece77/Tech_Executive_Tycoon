"""M20's balance runs (docs/formulas.md 36.5): refineries' margins, power, wafers for chips and
by-products in a ban, and "nothing else moves". Printed by tools/m20_targets.py.

Each run is a real game (`tst.balance.game`), the plant ordered through `build_refinery`,
staffed by a unit of process engineers at a set skill, and (to save simulated years) made
ready at once from its order month: construction and the overrun are tested elsewhere.
"""

from __future__ import annotations

import statistics as st
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

from tst.balance.game import Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.actions.facilities import StaffFacility
from tst.sim.calendar import ym_to_turn
from tst.sim.hiring.models import PersonState
from tst.sim.org.models import OrgUnit
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.refining import goods as rg
from tst.sim.refining.actions import BuildRefinery
from tst.sim.refining.plants import refinery_of
from tst.sim.rng import RngFactory
from tst.sim.state import (
    with_employment,
    with_facility,
    with_person,
    with_person_state,
    with_unit,
)

DATA = Path(__file__).resolve().parents[2] / "data"
PLAYER = 1
RICH = 10**14  # cents: cash is never the constraint in these runs
SKILL = 12.0  # the staff's manufacturing skill
SALARY = 7_800_000  # a mid process engineer's salary, cents a year (roles.yaml)


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


def game_at(seed: int, turn: int, scenario: str = "funded_spinout") -> Game:
    g = start_game(loaded(), seed, scenario)
    g.balances[(PLAYER, "1000_cash")] = g.balances.get((PLAYER, "1000_cash"), 0) + RICH
    g.state = replace(g.state, turn=turn)
    return g


def hire_unit(game: Game, name: str, n: int, skill: float = SKILL, seed: int = 1) -> int:
    """A team of `n` process engineers at manufacturing skill `skill`; its unit id."""
    state = game.state
    lg = loaded()
    role = lg.game_data.role("process_engineer")
    uid, ids = state.next_ids.take("unit")
    state = replace(state, next_ids=ids)
    state = with_unit(
        state,
        OrgUnit(
            id=uid,
            company_id=PLAYER,
            kind="team",
            name=name,
            parent_id=None,
            leader_id=None,
            policy=None,
            created_turn=state.turn,
        ),
    )
    rng = RngFactory(seed)
    for i in range(n):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(0, "misc", 500 + uid * 1000 + i),
            lg.game_data,
            lg.balance,
            state.turn,
            role,
            "mid",
            "north_america",
            person_id=pid,
        )
        person = replace(person, skills=person.skills.updated({"manufacturing": skill}))
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=eid,
                person_id=pid,
                company_id=PLAYER,
                role="process_engineer",
                level="mid",
                salary_cents=SALARY,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
                unit_id=uid,
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    game.state = state
    return uid


def build(
    game: Game,
    recipe: str,
    region: str,
    capacity: int,
    *,
    ready_now: bool = True,
    skill: float = SKILL,
    host_id: int | None = None,
) -> int:
    """Order, staff (full coverage) and, by default, finish a plant now. Its facility id."""
    b = loaded().balance
    kind = b.facility.kinds[b.refining.recipes[recipe].kind]
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))
    fid = game.state.next_ids.facility
    ok = game.act(BuildRefinery(game.founder_id, recipe, region, capacity, host_id=host_id))
    if not ok:
        raise RuntimeError(f"build_refinery refused: {dict(game.refused)}")
    need = -(-capacity // int(kind.staff_per)) if kind.staff_per >= 1 else capacity
    uid = hire_unit(game, f"{recipe} {fid}", max(1, need), skill, seed=fid)
    game.state = with_person_state(game.state, replace(ps, energy=100))
    game.act(StaffFacility(game.founder_id, fid, uid))
    if ready_now:
        f = game.state.facility(fid)
        assert f is not None
        game.state = with_facility(
            game.state,
            replace(
                f,
                ready_turn=game.state.turn,
                late_turn=game.state.turn,
                on_time=f.capacity,
                status="building",
            ),
        )
    return fid


def months(game: Game, n: int) -> None:
    for _ in range(n):
        game.turn()


@dataclass(frozen=True)
class PlantRun:
    recipe: str
    region: str
    margins: tuple[float, ...]
    units: tuple[float, ...]  # unit cost each month
    markets: tuple[float, ...]

    @property
    def median_margin(self) -> float:
        return st.median(self.margins) if self.margins else float("nan")


def run_plant(
    recipe: str,
    region: str,
    start: tuple[int, int],
    end: tuple[int, int],
    seed: int = 1,
    capacity: int | None = None,
) -> PlantRun:
    """A plant live from `start` through `end` (inclusive), its input bought at spot."""
    b = loaded().balance
    kind = b.facility.kinds[b.refining.recipes[recipe].kind]
    size = capacity or (kind.sizes or b.facility.sizes)[1]
    game = game_at(seed, ym_to_turn(*start) - 1)
    fid = build(game, recipe, region, size)
    margins: list[float] = []
    units: list[float] = []
    markets: list[float] = []
    ramp = b.refining.recipes[recipe].ramp_months
    last = ym_to_turn(*end)
    while game.state.turn < last:
        game.turn()
        ref = refinery_of(game.state, fid)
        assert ref is not None and ref.month is not None
        pm = ref.month
        if game.state.turn - ym_to_turn(*start) + 1 < ramp:  # 36.5 measures running plants
            continue
        if pm.margin is not None:
            margins.append(pm.margin)
            units.append(pm.unit_cost_cents)
            markets.append(pm.market_cents)
    return PlantRun(recipe, region, tuple(margins), tuple(units), tuple(markets))


def price_now(game: Game, good: str) -> float:
    lg = loaded()
    return rg.price_cents(game.state, good, lg.balance, lg.game_data)


def seeds(n: int) -> Sequence[int]:
    return range(1, n + 1)
