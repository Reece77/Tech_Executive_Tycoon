"""Realistic practice saves (M23c sub-task 9; fixtures only, never the game or a balance run).

Playtest 5 found the practice saves thin and broken: stage-3 companies with only a founder and
two geologists, and hand-built staff without the player's knowledge record of them, which the
People and Org screens need ("no person 2"). `finish` gives a fixture save:

- a knowledge record (as hiring creates one) for every employee of the player's company that
  has none, from the engine's own `new_reveal_state`;
- with `team=True` (stage 3 and up), a believable team in its own units: engineers, product,
  sales and finance, the specialists the scenario needs, and a CTO appointed through the
  engine's own action.

The tools in tools/e2e_*_save.py call it as their last step. Hires are seeded from the save's
master seed and a fixed stream sub-key, so a fixture is the same every time it is built."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Final

from tst.balance.game import Game
from tst.db.repository import ledger_balances, load_state, open_session
from tst.db.state_io import sync_state
from tst.loader import LoadedData
from tst.sim.actions.scaleup import AppointExecutive
from tst.sim.hiring.models import PersonState
from tst.sim.org.models import OrgUnit
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    reach_stage,
    with_company,
    with_employment,
    with_person,
    with_person_state,
    with_reveal,
    with_unit,
)

PLAYER: Final = 1
STREAM: Final = 9_000  # the misc stream's sub-keys for fixture hires (clear of the tools' own)
ENERGY: Final = 100  # the founder's energy while the CTO is appointed; restored after
MORALE: Final = 65.0
REGION: Final = "north_america"
# (role, level, count, unit, annual salary in cents): a stage-3 company's core
CORE: Final = (
    ("software_engineer", "senior", 4, "Engineering", 16_000_000),
    ("devops_engineer", "mid", 1, "Engineering", 13_000_000),
    ("product_manager", "senior", 2, "Product", 15_000_000),
    ("designer", "mid", 1, "Product", 11_000_000),
    ("sales_representative", "mid", 3, "Sales", 9_000_000),
    ("account_executive", "senior", 1, "Sales", 14_000_000),
    ("marketer", "mid", 1, "Sales", 10_000_000),
    ("finance_manager", "senior", 1, "Finance", 14_000_000),
    ("recruiter", "mid", 1, "Finance", 9_000_000),
)
SPECIALIST_SALARY: Final = 15_000_000


def add_reveals(state: GameState, data: LoadedData) -> GameState:
    """The player's knowledge record of every employee of the player's company without one."""
    rng = RngFactory(state.save_meta.master_seed)
    for e in state.employments:
        if e.company_id != PLAYER or e.status != "active":
            continue
        if state.reveal(PLAYER, e.person_id) is not None:
            continue
        state = with_reveal(
            state,
            new_reveal_state(
                observer_company_id=PLAYER,
                person=state.person(e.person_id),
                turn=state.turn,
                rng=rng,
                data=data.game_data,
                balance=data.balance,
            ),
        )
    return state


def _unit(state: GameState, name: str) -> tuple[GameState, int]:
    for u in state.units:
        if u.company_id == PLAYER and u.name == name and u.status == "active":
            return state, u.id
    uid, ids = state.next_ids.take("unit")
    state = replace(state, next_ids=ids)
    unit = OrgUnit(
        id=uid,
        company_id=PLAYER,
        kind="team",
        name=name,
        parent_id=None,
        leader_id=None,
        policy=None,
        created_turn=state.turn,
    )
    return with_unit(state, unit), uid


def hire(
    state: GameState,
    data: LoadedData,
    role_key: str,
    level: str,
    n: int,
    unit: str,
    salary_cents: int,
    sub: int,
) -> tuple[GameState, list[int]]:
    """`n` people in `role_key` at `level` in the unit called `unit` (made if missing)."""
    role = data.game_data.role(role_key)
    rng = RngFactory(state.save_meta.master_seed)
    state, uid = _unit(state, unit)
    hired = []
    for i in range(n):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(0, "misc", STREAM + sub * 100 + i),
            data.game_data,
            data.balance,
            state.turn,
            role,
            level,
            REGION,
            person_id=pid,
        )
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=eid,
                person_id=pid,
                company_id=PLAYER,
                role=role_key,
                level=level,
                salary_cents=salary_cents,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
                unit_id=uid,
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=MORALE))
        hired.append(pid)
    return state, hired


def add_team(game: Game, specialists: tuple[tuple[str, int, str], ...] = ()) -> None:
    """A stage-3 company's core team and the scenario's specialists ((role, count, unit)), and
    a CTO from the senior engineers, appointed through the engine's action."""
    state, data = game.state, game.loaded
    engineers: list[int] = []
    for sub, (role, level, n, unit, salary) in enumerate(CORE):
        state, hired = hire(state, data, role, level, n, unit, salary, sub)
        if role == "software_engineer":
            engineers += hired
    for sub, (role, n, unit) in enumerate(specialists, start=len(CORE)):
        state, _ = hire(state, data, role, "senior", n, unit, SPECIALIST_SALARY, sub)
    game.state = add_reveals(state, data)
    if engineers and not any(
        s.company_id == PLAYER and s.seat == "cto" and s.person_id is not None
        for s in game.state.exec_seats
    ):
        fid = game.founder_id
        ps = game.state.person_state(fid)
        energy = ps.energy
        game.state = with_person_state(game.state, replace(ps, energy=ENERGY))
        game.act(AppointExecutive(fid, "cto", engineers[0]))
        after = game.state.person_state(fid)
        game.state = with_person_state(game.state, replace(after, energy=energy))


def finish(
    path: Path,
    data: LoadedData,
    *,
    team: bool = False,
    specialists: tuple[tuple[str, int, str], ...] = (),
    stage: int | None = None,
) -> Path:
    """A fixture save's last step: knowledge records for every employee, and with `team` a
    believable stage-3 team (module docstring). Writes the state; posts no ledger entry (a
    hire is paid from the next month's payroll, as an offer accepted this month would be).
    `stage` raises the company to at least that stage first (as M18's and M19's fixtures do):
    a company running refineries or fabs is a scale-up, and executive seats open at stage 3."""
    with open_session(path) as session, session.begin():
        before = load_state(session)
        game = Game(data, before, dict(ledger_balances(session)))
        if stage is not None and game.state.player.stage < stage:
            game.state = with_company(
                game.state, reach_stage(game.state.player, stage, game.state.turn)
            )
        if team:
            add_team(game, specialists)
        else:
            game.state = add_reveals(game.state, data)
        sync_state(session, before, game.state)
    return path
