"""M27b's tools (docs/formulas.md 40.7): staff for any group company, and (sub-task 11) the
chain targets (a)-(d). True values are read here; this is a tool, not the game. People added
are generated on stream `misc` (tests and tools only), as in m8.py."""

from __future__ import annotations

import copy
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.report import SCENARIO
from tst.loader import LoadedData
from tst.sim.hiring.models import PersonState
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rivals.setup import market_salary_cents
from tst.sim.rng import RngFactory
from tst.sim.state import with_employment, with_person, with_person_state, with_reveal


def add_staff_at(
    game: Game,
    company_id: int,
    role: str,
    level: str,
    count: int,
    skill: float | None = None,
    unit_id: int | None = None,
) -> list[int]:
    """`count` employees of `role` in `company_id` (any group company) at the market rate,
    seen by the player's company (script only)."""
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
                company_id=company_id,
                role=role,
                level=level,
                salary_cents=market_salary_cents(role, level, balance, data),
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
                unit_id=unit_id,
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


# --- The chain targets (M27b sub-task 11; printed by tools/m27b_targets.py) -------------------
#
# From each seed's full_integrator game (M23b) at January 2025 (turn 180: the ladder aims at
# the whole chain by year 15), three arms to December 2039 (year 30):
#
# - `scripted`: full_integrator plays on, its six seat holders at score 15 (as 40.10's base).
# - `auto_15`: the founder stops playing; the seats at score 15, eleven area leads hired senior
#   at 15 (M27a's five and the chain's six), a CEO and a plant manager in each subsidiary, and
#   Automate everything in the player's company and every subsidiary. Each month the founder
#   only approves proposals whose central case is positive (or that have none) and pitches whose
#   central case is positive, and refills seats and areas (40.10 target 1's founder). The
#   exploration area gets a yearly budget of EXPLORATION_BUDGET; lobbying and screening keep the
#   default 0 (full_integrator neither lobbies nor acquires).
# - `auto_8`: the same at score 8.


SEEDS: Final = tuple(range(1, 11))
FORK_TURN: Final = 180  # January 2025
END_TURN: Final = 360  # to December 2039
ARMS: Final = ("scripted", "auto_15", "auto_8")
GOOD: Final = 15.0
WEAK: Final = 8.0
SEATS: Final = ("cto", "cpo", "cro", "cmo", "coo", "cfo")
LEADS: Final = (
    "recruiter",
    "research_scientist",
    "site_reliability_engineer",
    "communications_manager",
    "sales_manager",
    "manufacturing_engineer",
    "procurement_manager",
    "geologist",
    "plant_manager",
    "fab_manager",
    "public_policy_manager",
    "corporate_development_manager",
)
EXPLORATION_BUDGET: Final = 2_000_000_000  # $20M a year
A_BAND: Final = (0.85, 1.2)  # (a): auto_15 / scripted median year-30 ARR
B_BELOW: Final = 0.8  # (b): auto_8 at least 20% below auto_15
D_PROPOSALS: Final = 3.0  # (d): proposals a month (median) in auto_15
MIN_OWNERS: Final = 8  # (a): areas spread over at least this many people


@dataclass(frozen=True, slots=True)
class ChainRun:
    seed: int
    arm: str
    arr: int  # cents: 12 x the group's last month's revenue (M23b), 0 when the game ended
    owners: int  # distinct owners at the fork
    proposals: tuple[int, ...]  # waiting for the founder after each month
    mistakes: int
    never: int  # delegate actions of a kind no delegate may take (target (c): must be 0)
    seconds: float


def _fork(game: Game) -> Game:
    out = copy.copy(game)
    for name in (
        "balances",
        "snapshots",
        "founder_value",
        "traction_above_floor",
        "notes",
        "pnl",
        "group_pnl",
        "month_lines",
        "group_lines",
    ):
        setattr(out, name, copy.copy(getattr(game, name)))
    out.refused = copy.copy(game.refused)
    return out


def base_game(seed: int, fork: int = FORK_TURN) -> Game:
    from tst.balance.strategies_v3 import full_integrator

    game = start_game(_data(), seed, SCENARIO)
    while game.state.turn < fork and not game.state.ended:
        full_integrator(game)
        game.turn()
    return game


def _data() -> LoadedData:
    from tst.balance.v3 import loaded

    return loaded()


def _set_skills(game: Game, person_id: int, score: float) -> None:
    person = game.state.person(person_id)
    game.state = with_person(
        game.state,
        replace(person, skills=person.skills.updated(dict.fromkeys(person.skills.keys(), score))),
    )


def _founder_energy(game: Game) -> None:
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def _seats(game: Game, score: float) -> None:
    """The six seats at `score`: a holder's skills set to it, an empty seat filled by a hire."""
    from tst.balance.strategies import SEAT_ROLES
    from tst.sim.actions import AppointExecutive

    for seat in SEATS:
        holder = game.state.seat_holder(PLAYER, seat)
        if holder is not None:
            _set_skills(game, holder, score)
            continue
        (pid,) = add_staff_at(game, PLAYER, SEAT_ROLES[seat], "senior", 1, skill=score)
        _founder_energy(game)
        game.act(AppointExecutive(game.founder_id, seat, pid))


def _subsidiaries(game: Game) -> list[int]:
    from tst.sim.automation import scope

    return scope.companies(game.state)[1:]


def _automate(game: Game, *, setup: bool = False) -> None:
    from tst.sim.automation.actions import SetAreaOwner, SetAreaSettings
    from tst.sim.automation.plan import automate_everything
    from tst.sim.state import company_cash

    b, d = game.loaded.balance, game.loaded.game_data
    for company in [PLAYER, *_subsidiaries(game)]:
        cash = company_cash(game.balances, company)
        cid = None if company == PLAYER else company
        for a in automate_everything(game.state, cash, b, d, cid):
            if setup:
                _founder_energy(game)
            game.act(SetAreaOwner(game.founder_id, a.area, a.person_id, a.limit_cents, None, cid))
            if a.area == "exploration":
                game.act(
                    SetAreaSettings(
                        game.founder_id, a.area, company_id=cid, budget_cents=EXPLORATION_BUDGET
                    )
                )
    if setup:
        _founder_energy(game)


def _answer(game: Game) -> None:
    from tst.sim.actions.authority import AnswerPitch, AnswerProposal

    for p in game.state.pending_proposals(PLAYER):
        central = dict(p.params).get("central_cents")
        game.act(AnswerProposal(game.founder_id, p.id, central is None or int(central) > 0))
    for pitch in game.state.pending_pitches(PLAYER):
        game.act(
            AnswerPitch(game.founder_id, pitch.id, "approve" if pitch.central > 0 else "decline")
        )


def _arr(game: Game) -> int:
    if game.state.ended or not game.group_pnl:
        return 0
    return 12 * game.group_pnl[max(game.group_pnl)][0]


def _arm(base: Game, seed: int, arm: str, end: int = END_TURN) -> ChainRun:
    import time

    from tst.balance.strategies import appoint_executives
    from tst.balance.strategies_v3 import full_integrator
    from tst.sim.automation.config import NEVER_ACTIONS

    started = time.perf_counter()
    game = _fork(base)
    score = WEAK if arm == "auto_8" else GOOD
    _seats(game, score)
    if arm == "scripted":
        while game.state.turn < end and not game.state.ended:
            full_integrator(game)
            game.turn()
        return ChainRun(seed, arm, _arr(game), 0, (), 0, 0, time.perf_counter() - started)
    for role in LEADS:
        add_staff_at(game, PLAYER, role, "senior", 1, skill=score)
    for sub in _subsidiaries(game):
        add_staff_at(game, sub, "operations_manager", "exec", 1, skill=score)
        add_staff_at(game, sub, "plant_manager", "senior", 1, skill=score)
    _automate(game, setup=True)
    owners = len({o.person_id for o in game.state.area_owners})
    seen: set[tuple[int, int, int]] = set()
    proposals: list[int] = []
    mistakes = never = 0
    while game.state.turn < end and not game.state.ended:
        _answer(game)
        appoint_executives(game, SEATS)
        _automate(game)
        game.turn()
        proposals.append(
            len(game.state.pending_proposals(PLAYER)) + len(game.state.pending_pitches(PLAYER))
        )
        for dec in game.state.area_decisions:
            key = (dec.company_id, dec.turn, dec.seq)
            if key in seen:
                continue
            seen.add(key)
            mistakes += dec.kind == "mistake"
        if game.last_result is not None:
            never += sum(1 for _, a in game.last_result.delegate_actions if a.kind in NEVER_ACTIONS)
    return ChainRun(
        seed,
        arm,
        _arr(game),
        owners,
        tuple(proposals),
        mistakes,
        never,
        time.perf_counter() - started,
    )


def play_seed(job: tuple[int, int, int]) -> list[ChainRun]:
    """One seed's base game, then its three arms from the fork."""
    seed, fork, end = job
    base = base_game(seed, fork)
    return [_arm(base, seed, arm, end) for arm in ARMS]


def run(
    seeds: tuple[int, ...] = SEEDS, jobs: int = 1, fork: int = FORK_TURN, end: int = END_TURN
) -> list[ChainRun]:
    plan = [(s, fork, end) for s in seeds]
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            return [r for runs in pool.map(play_seed, plan) for r in runs]
    return [r for job in plan for r in play_seed(job)]


def _median_arr(results: list[ChainRun], arm: str) -> float:
    xs = [r.arr for r in results if r.arm == arm]
    return median(xs) if xs else 0.0


def target_a(results: list[ChainRun]) -> float:
    base = _median_arr(results, "scripted")
    return _median_arr(results, "auto_15") / base if base else 0.0


def target_b(results: list[ChainRun]) -> float:
    good = _median_arr(results, "auto_15")
    return _median_arr(results, "auto_8") / good if good else 0.0


def target_d(results: list[ChainRun]) -> float:
    xs = [x for r in results if r.arm == "auto_15" for x in r.proposals]
    return median(xs) if xs else 0.0


def report(results: list[ChainRun]) -> str:
    lines = [
        f"seed {r.seed:>2} {r.arm:<9} year-30 ARR ${r.arr / 100:,.0f}, owners {r.owners}, "
        f"mistakes {r.mistakes}, never {r.never}, {r.seconds:.0f}s"
        for r in sorted(results, key=lambda r: (r.seed, ARMS.index(r.arm)))
    ]
    owners = min((r.owners for r in results if r.arm == "auto_15"), default=0)
    never = sum(r.never for r in results)
    lines += [
        f"M27b target (a): auto_15 / scripted median year-30 ARR {target_a(results):.2f} "
        f"(band {A_BAND[0]}-{A_BAND[1]}); fewest owners {owners} (at least {MIN_OWNERS})",
        f"M27b target (b): auto_8 / auto_15 median year-30 ARR {target_b(results):.2f} "
        f"(at most {B_BELOW})",
        f"M27b target (c): delegate grey routes and terminations {never} (must be 0)",
        f"M27b target (d): proposals a month in auto_15 {target_d(results):.1f} "
        f"(median, at most {D_PROPOSALS})",
    ]
    return "\n".join(lines)
