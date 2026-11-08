"""docs/formulas.md 18.9 targets 2, 3 and 5 (M8), printed by tools/m8_targets.py and checked
nightly (tests/balance/test_m8_balance.py).

- Target 2 (seats matter): from each seed's steady game at stage 3, 36 more months with six
  seat holders of score >= 14, and again with every seat vacant. The six are added in both
  arms (operations managers, so they count as support either way) and appointed in one.
- Target 3 (support matters): from the same games, 36 months holding support coverage at
  1.0 and at 0.5 (operations managers added each month as the company grows), seats vacant.
- Target 5 (the ceiling lifts): blitzscale with its second product in Fintech against the
  standard blitzscale, turn-120 ARR.

People added by these scripts are generated on stream `misc` (tests and tools only); the
numbers here describe the scripts, not the game, as in strategies.py.
"""

from __future__ import annotations

import math
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.report import SCENARIO, _loaded
from tst.balance.strategies import blitzscale, steady
from tst.sim.actions import AppointExecutive
from tst.sim.hiring.models import PersonState
from tst.sim.org.divisions import support_pools
from tst.sim.org.models import SEATS
from tst.sim.org.rules import org_view
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rivals.setup import market_salary_cents
from tst.sim.rng import RngFactory
from tst.sim.state import with_employment, with_person, with_person_state, with_reveal

SEEDS: Final = tuple(range(1, 11))
STAGE_3_BY: Final = 240  # turns of steady allowed to reach stage 3
MONTHS: Final = 36
SUPPORT_ROLE: Final = "operations_manager"
SEAT_SKILL: Final = 15.0  # every skill a seat weighs: s = 15, e = 0.625
FINTECH_SECOND: Final = ("Ledger", "fintech", ("smb", "mid_market"))
BLITZ_TURNS: Final = 120


@dataclass(frozen=True, slots=True)
class ArmResult:
    seed: int
    stage_3_turn: int | None
    arr_a: int  # seats filled / full coverage / fintech second
    arr_b: int  # seats vacant / half coverage / standard


def add_staff(
    game: Game, role: str, level: str, count: int, skill: float | None = None
) -> list[int]:
    """`count` employees in the company root at the role's market rate (script only)."""
    loaded = game.loaded
    data, balance = loaded.game_data, loaded.balance
    ids = []
    for _ in range(count):
        state = game.state
        pid, next_ids = state.next_ids.take("person")
        emp_id, next_ids = next_ids.take("employment")
        gen = RngFactory(state.save_meta.master_seed).stream(state.turn, "misc", pid)
        person = generate_person(
            gen, data, balance, state.turn, data.role(role), level, "north_america", person_id=pid
        )
        if skill is not None:
            person = replace(
                person, skills=person.skills.updated(dict.fromkeys(person.skills.keys(), skill))
            )
        state = replace(with_person(state, person), next_ids=next_ids)
        state = with_employment(
            state,
            Employment(
                id=emp_id,
                person_id=pid,
                company_id=PLAYER,
                role=role,
                level=level,
                salary_cents=market_salary_cents(role, level, balance, data),
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=balance.morale.new_hire))
        state = with_reveal(
            state,
            new_reveal_state(
                observer_company_id=PLAYER,
                person=person,
                turn=state.turn,
                rng=RngFactory(state.save_meta.master_seed),
                data=data,
                balance=balance,
            ),
        )
        game.state = state
        ids.append(pid)
    return ids


def fork(game: Game) -> Game:
    return Game(
        game.loaded,
        game.state,
        dict(game.balances),
        seq=game.seq,
        snapshots=list(game.snapshots),
        notes=dict(game.notes),
    )


def steady_at_stage_3(seed: int) -> Game | None:
    game = start_game(_loaded("data"), seed, SCENARIO)
    for _ in range(STAGE_3_BY):
        if game.state.ended:
            return None
        if game.state.player.stage >= game.loaded.balance.exec_seats.stage:
            return game
        steady(game)
        game.turn()
    return None


def _play(game: Game, months: int, coverage: float | None = None) -> int:
    for _ in range(months):
        if game.state.ended:
            break
        if coverage is not None:
            hold_coverage(game, coverage)
        steady(game, appoint=False)  # the arm decides the seats, not the script
        game.turn()
    return game.snapshots[-1].arr_cents if game.snapshots and not game.state.ended else 0


def hold_coverage(game: Game, coverage: float) -> None:
    """Add operations managers until the central pool's coverage reaches `coverage`."""
    b = game.loaded.balance
    pool = support_pools(game.state, org_view(game.state, PLAYER), b, game.loaded.game_data)[None]
    wanted = math.ceil(coverage * pool.headcount / b.org.support_ratio)
    missing = wanted - pool.support
    if missing > 0:
        add_staff(game, SUPPORT_ROLE, "senior", missing)


def seats_arm(seed: int) -> ArmResult:
    base = steady_at_stage_3(seed)
    if base is None:
        return ArmResult(seed, None, 0, 0)
    turn = base.state.turn
    add_staff(base, SUPPORT_ROLE, "senior", len(SEATS), skill=SEAT_SKILL)
    holders = sorted(e.person_id for e in base.state.staff(PLAYER))[-len(SEATS) :]
    filled = fork(base)
    for seat, pid in zip(SEATS, holders, strict=True):
        ps = filled.state.person_state(filled.founder_id)
        filled.state = with_person_state(filled.state, replace(ps, energy=100))
        filled.act(AppointExecutive(filled.founder_id, seat, pid))
    return ArmResult(seed, turn, _play(filled, MONTHS), _play(fork(base), MONTHS))


def support_arm(seed: int) -> ArmResult:
    base = steady_at_stage_3(seed)
    if base is None:
        return ArmResult(seed, None, 0, 0)
    turn = base.state.turn
    full = _play(fork(base), MONTHS, coverage=1.0)
    half = _play(fork(base), MONTHS, coverage=0.5)
    return ArmResult(seed, turn, full, half)


def blitz_arm(seed: int) -> ArmResult:
    fintech = start_game(_loaded("data"), seed, SCENARIO)
    plain = start_game(_loaded("data"), seed, SCENARIO)
    for game, second in ((fintech, FINTECH_SECOND), (plain, None)):
        for _ in range(BLITZ_TURNS):
            if game.state.ended:
                break
            if second is None:
                blitzscale(game)
            else:
                blitzscale(game, second)
            game.turn()
    arr = [g.snapshots[-1].arr_cents if not g.state.ended else 0 for g in (fintech, plain)]
    return ArmResult(seed, None, arr[0], arr[1])


ARMS = {"seats": seats_arm, "support": support_arm, "blitz": blitz_arm}


def run(arm: str, seeds: tuple[int, ...] = SEEDS, jobs: int = 1) -> list[ArmResult]:
    fn = ARMS[arm]
    if jobs <= 1:
        return [fn(s) for s in seeds]
    with ProcessPoolExecutor(jobs) as pool:
        return list(pool.map(fn, seeds))


def ratio(results: list[ArmResult]) -> float:
    """Median of arm A over the median of arm B, over seeds where both arms reached the fork
    and kept going (a bankrupt or removed founder has no ARR to compare)."""
    used = [r for r in results if r.arr_b > 0 and r.arr_a > 0]  # both arms still playing
    if not used:
        return 0.0
    b = median(r.arr_b for r in used)
    return median(r.arr_a for r in used) / b if b else float("inf")
