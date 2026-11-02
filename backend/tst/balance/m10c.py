"""docs/formulas.md 24.5 targets (M10c), printed by tools/m10c_targets.py and checked nightly
(tests/balance/test_m10c_balance.py).

From each seed's steady game at its first month of stage 3 (M8's fork), five senior seat
holders are added and appointed (CTO, CRO, CMO, COO, CFO; every skill a seat weighs at the
arm's score, so s = that score). Then 36 months in three arms:

- `steady`: holders at score 15, no authority; the steady script plays on (M8 target 2's
  filled arm with authority-capable seats).
- `delegated`: holders at score 15, every seat given authority at its default guardrails;
  the founder takes no actions except approving the executives' proposals (24.1: approving is
  how a proposal becomes an action) and answering critical events as every script does.
- `delegated_8`: the same with holders at score 8.

Target 1 compares `delegated` with `steady` (median ARR); target 2 compares `delegated_8` with
`delegated`; targets 3 and 4 are measured in `delegated`. True values are read here (team
output, coverage): this is a tool, not the API. People added are generated on stream `misc`
(tests and tools only), as in m8.py.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, Game
from tst.balance.m8 import add_staff, fork, steady_at_stage_3
from tst.balance.strategies import SEAT_ROLES, appoint_executives, steady
from tst.sim.actions import AppointExecutive
from tst.sim.actions.authority import AnswerProposal, SetAuthority
from tst.sim.org.divisions import support_pools
from tst.sim.org.rules import org_view
from tst.sim.products.models import SELLING
from tst.sim.products.phases import team_of
from tst.sim.state import with_person_state

SEEDS: Final = tuple(range(1, 11))
MONTHS: Final = 36
SEATS_GIVEN: Final = ("cto", "cro", "cmo", "coo", "cfo")
GOOD: Final = 15.0
WEAK: Final = 8.0
ARMS: Final = ("steady", "delegated", "delegated_8")


@dataclass(frozen=True, slots=True)
class Run:
    seed: int
    arm: str
    stage_3_turn: int | None
    arr: int  # cents at the end; 0 when the game ended
    longest_below: int  # most consecutive months a live product sat below its maintenance line
    builders_max: int  # below exec level (seat holders and exec hires are outside the caps)
    sellers_max: int
    builder_cap: int  # max(the CTO's cap, builders at the fork)
    seller_cap: int
    coverage: tuple[float, ...]  # central coverage at each month end that began with a COO acting
    energy_unspent: float  # mean share of the founder's monthly energy left at month end
    approved: int  # proposals the founder approved


def _function_count(game: Game, function: str) -> int:
    state, data = game.state, game.loaded.game_data
    return sum(
        1
        for e in state.staff(PLAYER)
        if not state.person(e.person_id).is_founder
        and e.level != "exec"  # seat holders and the refill's exec hires are not the caps'
        and data.role(e.role).product_function == function
    )


def _below_line(game: Game) -> set[int]:
    """Live products whose true builder output is below their maintenance line."""
    state, b, data = game.state, game.loaded.balance, game.loaded.game_data
    view = org_view(state, PLAYER)
    out = set()
    for p in state.company_products(PLAYER):
        if p.status not in SELLING:
            continue
        output = team_of(state, view, p, b, data).base_output(b)
        if output < b.products.rot_threshold * data.category(p.category).scope:
            out.add(p.id)
    return out


def _seat(game: Game, score: float, authority: bool) -> None:
    for seat in SEATS_GIVEN:
        (pid,) = add_staff(game, SEAT_ROLES[seat], "senior", 1, skill=score)
        ps = game.state.person_state(game.founder_id)
        game.state = with_person_state(game.state, replace(ps, energy=100))
        game.act(AppointExecutive(game.founder_id, seat, pid))
        if authority:
            game.act(SetAuthority(game.founder_id, seat, True))
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def _refill(game: Game) -> None:
    """Keep the five seats filled as the steady script does (executives resign and are poached
    at the game's usual rates), and give a new holder authority at the defaults."""
    appoint_executives(game, SEATS_GIVEN)
    for seat in SEATS_GIVEN:
        a = game.state.authority(PLAYER, seat)
        if game.state.seat_holder(PLAYER, seat) is not None and (a is None or not a.enabled):
            game.act(SetAuthority(game.founder_id, seat, True))


def _arm(base: Game, arm: str) -> Run:
    game = fork(base)
    delegated = arm != "steady"
    _seat(game, WEAK if arm == "delegated_8" else GOOD, delegated)
    b = game.loaded.balance
    caps = b.exec_authority.defaults
    builder_cap = max(int(caps["cto"]["headcount_cap"]), _function_count(game, "builder"))
    seller_cap = max(int(caps["cro"]["headcount_cap"]), _function_count(game, "seller"))
    streak: dict[int, int] = {}
    longest = builders = sellers = approved = 0
    coverage: list[float] = []
    unspent: list[float] = []
    for _ in range(MONTHS):
        if game.state.ended:
            break
        start = game.energy()
        coo = game.state.authority(PLAYER, "coo")
        coo_acting = bool(coo and coo.enabled and game.state.seat_holder(PLAYER, "coo"))
        if delegated:
            for p in game.state.pending_proposals(PLAYER):
                approved += game.act(AnswerProposal(game.founder_id, p.id, True))
            _refill(game)
        else:
            steady(game)
        unspent.append(game.energy() / start if start else 1.0)
        game.turn()
        if game.state.ended:
            break
        below = _below_line(game)
        streak = {pid: streak.get(pid, 0) + 1 for pid in below}
        longest = max(longest, *streak.values(), 0)
        builders = max(builders, _function_count(game, "builder"))
        sellers = max(sellers, _function_count(game, "seller"))
        view = org_view(game.state, PLAYER)
        if coo_acting or not delegated:  # 24.5 target 3: while a COO has authority
            pool = support_pools(game.state, view, b, game.loaded.game_data)[None]
            coverage.append(pool.coverage)
    arr = game.snapshots[-1].arr_cents if game.snapshots and not game.state.ended else 0
    return Run(
        seed=0,
        arm=arm,
        stage_3_turn=base.state.turn,
        arr=arr,
        longest_below=longest,
        builders_max=builders,
        sellers_max=sellers,
        builder_cap=builder_cap,
        seller_cap=seller_cap,
        coverage=tuple(coverage),
        energy_unspent=sum(unspent) / len(unspent) if unspent else 1.0,
        approved=approved,
    )


def play(seed: int) -> list[Run]:
    base = steady_at_stage_3(seed)
    if base is None:
        return [
            Run(seed, arm, None, 0, 0, 0, 0, 0, 0, (), 1.0, 0)  # never reached stage 3
            for arm in ARMS
        ]
    return [replace(_arm(base, arm), seed=seed) for arm in ARMS]


def run(seeds: tuple[int, ...] = SEEDS, jobs: int = 1) -> list[Run]:
    if jobs <= 1:
        return [r for s in seeds for r in play(s)]
    with ProcessPoolExecutor(jobs) as pool:
        return [r for runs in pool.map(play, seeds) for r in runs]


def arm(runs: list[Run], name: str) -> list[Run]:
    return [r for r in runs if r.arm == name and r.stage_3_turn is not None]


def median_ratio(runs: list[Run], a: str, b: str) -> float:
    """Median ARR of arm `a` over arm `b`, over seeds that reached stage 3."""
    top, bottom = arm(runs, a), arm(runs, b)
    if not top or not bottom:
        return 0.0
    under = median(r.arr for r in bottom)
    return median(r.arr for r in top) / under if under else float("inf")


def coverage_gap(r: Run, target: float) -> float:
    """The largest shortfall of support coverage below the target over the run."""
    return max((target - c for c in r.coverage), default=0.0)


def report(runs: list[Run]) -> str:
    """Every seed's arms, then the four targets with their values."""
    target = 1.0  # the COO's default coverage target
    lines = []
    for r in sorted(runs, key=lambda r: (r.seed, ARMS.index(r.arm))):
        if r.stage_3_turn is None:
            lines.append(f"seed {r.seed:2d} {r.arm:<12} never reached stage 3")
            continue
        lines.append(
            f"seed {r.seed:2d} {r.arm:<12} stage 3 at {r.stage_3_turn}: ARR ${r.arr // 100:,}; "
            f"longest below line {r.longest_below}; builders {r.builders_max}/{r.builder_cap}, "
            f"sellers {r.sellers_max}/{r.seller_cap}; coverage gap {coverage_gap(r, target):.2f}"
            f"; founder energy unspent {r.energy_unspent:.0%}; approved {r.approved}"
        )
    delegated = arm(runs, "delegated")
    one = median_ratio(runs, "delegated", "steady")
    two = median_ratio(runs, "delegated", "delegated_8")
    lines.append(
        f"24.5 target 1: delegated / steady median ARR {one:.2f} (within 0.85-1.15); longest "
        f"below the maintenance line {max((r.longest_below for r in delegated), default=0)} "
        "months (<= 2)"
    )
    lines.append(f"24.5 target 2: score 15 / score 8 median ARR {two:.2f} (>= 1.15)")
    over = sum(r.builders_max > r.builder_cap or r.sellers_max > r.seller_cap for r in delegated)
    gap = max((coverage_gap(r, target) for r in delegated), default=0.0)
    lines.append(
        f"24.5 target 3: {over} runs over a headcount cap (0); largest coverage shortfall "
        f"{gap:.2f} (<= 0.1)"
    )
    energy = sum(r.energy_unspent for r in delegated) / len(delegated) if delegated else 0.0
    lines.append(f"24.5 target 4: founder energy unspent {energy:.0%} on average (>= 60%)")
    return "\n".join(lines)
