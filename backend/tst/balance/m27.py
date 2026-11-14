"""docs/formulas.md 40.10 targets (M27a), printed by tools/m27_targets.py and checked nightly
(tests/balance/test_m27_balance.py).

From each seed's steady game at its first month of stage 3 (M8's fork, 24.5 target 1's), the
six seats (CTO, CPO, CRO, CMO, COO, CFO) and five area leads (a recruiter, a research scientist,
a site reliability engineer, a communications manager and a sales manager) are hired senior,
every skill at the arm's score. Then 60 months in which the founder does nothing but approve
proposals and pitches whose central case is positive (40.10 target 1) and refill seats and
areas that fall empty. Arms:

- `spread`: score 15, Automate everything (40.8): areas spread over the team.
- `spread_8`: the same at score 8.
- `one`: score 15, every area given to one person: an appointed CEO (the one owner who may run
  every area, 40.1). A Ceo record is written directly with no scopes of its own (a tool, not the
  game), so only the areas run.
- `steady_regions`: 27.5 target 7's founder script (M10c's steady script with the holders at
  score 15 and no authority, plus a region launch at most every 24 months), for 60 months.

True values are read here (mistakes logged, energy left); this is a tool. People added are
generated on stream `misc` (tests and tools only), as in m8.py.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, Game
from tst.balance.m8 import add_staff, fork, steady_at_stage_3
from tst.balance.m13b import REGION_GAP, _launch_region
from tst.balance.strategies import SEAT_ROLES, appoint_executives, steady
from tst.sim.actions import AppointExecutive
from tst.sim.actions.authority import AnswerPitch, AnswerProposal
from tst.sim.automation.actions import SetAreaOwner
from tst.sim.automation.plan import automate_everything
from tst.sim.markets_public.models import Ceo
from tst.sim.state import with_person_state

SEEDS: Final = tuple(range(1, 11))
MONTHS: Final = 60
SEATS: Final = ("cto", "cpo", "cro", "cmo", "coo", "cfo")
LEADS: Final = (
    "recruiter",
    "research_scientist",
    "site_reliability_engineer",
    "communications_manager",
    "sales_manager",
)
GOOD: Final = 15.0
WEAK: Final = 8.0
ARMS: Final = ("spread", "spread_8", "one", "steady_regions")
DIGEST: Final = "digest"
PROPOSAL_TEMPLATES: Final = frozenset({"exec_proposal", "exec_pitch"})

# 40.10's bands
T1_LOW: Final = 0.85
T1_HIGH: Final = 1.2
T2_BELOW: Final = 0.8  # score 8: median ARR at least 20% below
T2_MISTAKES: Final = 2.0  # and at least twice the logged mistakes
T3_BELOW: Final = 0.9  # one owner: at least 10% below
T4_PROPOSALS: Final = 2.0  # a month (median)
T4_OTHER: Final = 10.0  # a month (median), not counting the digest
T5_UNSPENT: Final = 0.8


@dataclass(frozen=True, slots=True)
class Run:
    seed: int
    arm: str
    stage_3_turn: int | None
    arr: int  # cents at the end; 0 when the game ended
    mistakes: int  # logged mistakes over the run
    owners: int  # distinct owners at the start
    proposals: tuple[int, ...]  # proposals and pitches waiting for the founder, a month
    other: tuple[int, ...]  # other inbox items a month (the digest and digest items left out)
    unspent: float  # mean share of the founder's monthly energy left at month end
    no_time: int  # area-months skipped for lack of energy


def _energy(game: Game) -> None:
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def _hire(game: Game, score: float) -> None:
    for seat in SEATS:
        (pid,) = add_staff(game, SEAT_ROLES[seat], "senior", 1, skill=score)
        _energy(game)
        game.act(AppointExecutive(game.founder_id, seat, pid))
    for role in LEADS:
        add_staff(game, role, "senior", 1, skill=score)
    _energy(game)


def _automate(game: Game, *, setup: bool = False) -> None:
    """Automate everything for the areas nobody runs (the plan the player would confirm). In
    the run itself it spends the founder's own energy, as everything the founder does."""
    loaded = game.loaded
    for a in automate_everything(game.state, game.cash, loaded.balance, loaded.game_data):
        if setup:
            _energy(game)
        game.act(SetAreaOwner(game.founder_id, a.area, a.person_id, a.limit_cents))
    if setup:
        _energy(game)


def _one_owner(game: Game) -> None:
    """Every area to one CEO (score 15), written directly with no scopes of its own."""
    (pid,) = add_staff(game, "operations_manager", "exec", 1, skill=GOOD)
    ceo = Ceo(1, PLAYER, pid, game.state.turn, ())
    game.state = replace(game.state, ceos=(*game.state.ceos, ceo))
    for area in game.loaded.balance.automation.areas:
        _energy(game)
        game.act(SetAreaOwner(game.founder_id, area, pid))
    _energy(game)


def _answer(game: Game) -> None:
    """Approve every proposal, and pitches whose central case is positive (target 1)."""
    for p in game.state.pending_proposals(PLAYER):
        game.act(AnswerProposal(game.founder_id, p.id, True))
    for pitch in game.state.pending_pitches(PLAYER):
        answer = "approve" if pitch.central > 0 else "decline"
        game.act(AnswerPitch(game.founder_id, pitch.id, answer))  # type: ignore[arg-type]


def _waiting(game: Game) -> int:
    return len(game.state.pending_proposals(PLAYER)) + len(game.state.pending_pitches(PLAYER))


def _other(game: Game) -> int:
    return sum(
        1
        for i in game.last_logs
        if i.company_id == PLAYER
        and i.template is not None
        and i.template != DIGEST
        and i.template not in PROPOSAL_TEMPLATES
        and not i.in_digest
    )


def _arm(base: Game, arm: str) -> Run:
    game = fork(base)
    if arm == "steady_regions":
        return _steady(game, base)
    _hire(game, WEAK if arm == "spread_8" else GOOD)
    if arm == "one":
        _one_owner(game)
    else:
        _automate(game, setup=True)
    owners = len({o.person_id for o in game.state.owners_of(PLAYER)})
    seen: set[tuple[int, int]] = set()
    mistakes = no_time = 0
    proposals: list[int] = []
    other: list[int] = []
    unspent: list[float] = []
    for _ in range(MONTHS):
        if game.state.ended:
            break
        month_start = game.energy()
        _answer(game)
        if arm != "one":
            appoint_executives(game, SEATS)
            _automate(game)
        left = game.energy()
        game.turn()
        proposals.append(_waiting(game))
        other.append(_other(game))
        unspent.append(left / month_start if month_start else 1.0)
        for d in game.state.area_decisions:
            key = (d.turn, d.seq)
            if d.company_id != PLAYER or key in seen:
                continue
            seen.add(key)
            mistakes += d.kind == "mistake"
            no_time += d.kind == "no_time"
    arr = game.snapshots[-1].arr_cents if game.snapshots and not game.state.ended else 0
    return Run(
        seed=0,
        arm=arm,
        stage_3_turn=base.state.turn,
        arr=arr,
        mistakes=mistakes,
        owners=owners,
        proposals=tuple(proposals),
        other=tuple(other),
        unspent=sum(unspent) / len(unspent) if unspent else 1.0,
        no_time=no_time,
    )


def _steady(game: Game, base: Game) -> Run:
    """27.5 target 7's script for 60 months: M10c's steady arm plus region launches."""
    for seat in SEATS:
        (pid,) = add_staff(game, SEAT_ROLES[seat], "senior", 1, skill=GOOD)
        _energy(game)
        game.act(AppointExecutive(game.founder_id, seat, pid))
    _energy(game)
    last: int | None = None
    for _ in range(MONTHS):
        if game.state.ended:
            break
        steady(game)
        if (last is None or game.state.turn - last >= REGION_GAP) and _launch_region(game):
            last = game.state.turn
        game.turn()
    arr = game.snapshots[-1].arr_cents if game.snapshots and not game.state.ended else 0
    return Run(0, "steady_regions", base.state.turn, arr, 0, 0, (), (), 0.0, 0)


def play(seed: int) -> list[Run]:
    base = steady_at_stage_3(seed)
    if base is None:
        return [Run(seed, arm, None, 0, 0, 0, (), (), 0.0, 0) for arm in ARMS]
    return [replace(_arm(base, arm), seed=seed) for arm in ARMS]


type Results = list[Run]


def run(seeds: tuple[int, ...] = SEEDS, jobs: int = 1) -> Results:
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            return [r for runs in pool.map(play, seeds) for r in runs]
    return [r for seed in seeds for r in play(seed)]


def arm(results: Results, name: str) -> list[Run]:
    return [r for r in results if r.arm == name and r.stage_3_turn is not None]


def _median_arr(results: Results, name: str) -> float:
    runs = arm(results, name)
    return median(r.arr for r in runs) if runs else 0.0


def target_1(results: Results) -> float:
    """Spread median ARR / the steady + regions script's (0.85-1.2)."""
    base = _median_arr(results, "steady_regions")
    return _median_arr(results, "spread") / base if base else 0.0


def target_2(results: Results) -> tuple[float, float]:
    """Score 8 / score 15: median ARR ratio (<= 0.8) and mistakes ratio (>= 2)."""
    good = _median_arr(results, "spread")
    weak = _median_arr(results, "spread_8")
    m15 = sum(r.mistakes for r in arm(results, "spread"))
    m8 = sum(r.mistakes for r in arm(results, "spread_8"))
    return (weak / good if good else 0.0, m8 / max(m15, 1))


def target_3(results: Results) -> float:
    """One owner / spread median ARR (<= 0.9)."""
    good = _median_arr(results, "spread")
    return _median_arr(results, "one") / good if good else 0.0


def target_4(results: Results) -> tuple[float, float]:
    """Spread run: median proposals a month (<= 2) and other inbox items a month (<= 10)."""
    runs = arm(results, "spread")
    props = [x for r in runs for x in r.proposals]
    other = [x for r in runs for x in r.other]
    return (median(props) if props else 0.0, median(other) if other else 0.0)


def target_5(results: Results) -> float:
    """Spread run: mean share of the founder's energy left (>= 0.8)."""
    runs = arm(results, "spread")
    return sum(r.unspent for r in runs) / len(runs) if runs else 0.0


def report(results: Results) -> str:
    lines = []
    for r in sorted(results, key=lambda r: (r.seed, ARMS.index(r.arm))):
        lines.append(
            f"seed {r.seed:>2} {r.arm:<15} stage 3 at {r.stage_3_turn}: ARR ${r.arr / 100:,.0f}, "
            f"owners {r.owners}, mistakes {r.mistakes}, no time {r.no_time}, "
            f"unspent {r.unspent:.0%}"
        )
    t2 = target_2(results)
    t4 = target_4(results)
    lines += [
        f"40.10 target 1: spread / steady + regions median ARR {target_1(results):.2f} "
        f"(band {T1_LOW}-{T1_HIGH})",
        f"40.10 target 2: score 8 / score 15 median ARR {t2[0]:.2f} (at most {T2_BELOW}), "
        f"mistakes x{t2[1]:.1f} (at least {T2_MISTAKES})",
        f"40.10 target 3: one owner / spread median ARR {target_3(results):.2f} "
        f"(at most {T3_BELOW})",
        f"40.10 target 4: proposals a month {t4[0]:.1f} (at most {T4_PROPOSALS}), other inbox "
        f"items a month {t4[1]:.1f} (at most {T4_OTHER})",
        f"40.10 target 5: founder energy left {target_5(results):.0%} (at least {T5_UNSPENT:.0%})",
    ]
    return "\n".join(lines)
