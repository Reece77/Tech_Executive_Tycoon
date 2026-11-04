"""docs/formulas.md 27.5 targets (M13b), printed by tools/m13b_targets.py and checked nightly
(tests/balance/test_m13b_balance.py).

Targets 1-4: from each seed's steady game at its first month of stage 3 (M8's fork), six
senior seat holders are appointed (CPO, CTO, CRO, CMO, COO, CFO; every skill a seat weighs at
the arm's score) and every seat is given authority. Then 36 months as on Holiday: the founder
takes no actions except approving the executives' proposals (as M10c's delegated arm) and
answering critical events; pitches under the auto-approve limit (the default, 5% of cash) go
ahead, bigger ones wait and lapse. Arms:

- `pitches`: holders at score 15, the default limit.
- `off`: the same with the limit at 0, so every pitch waits for an answer that never comes:
  M10c's delegated baseline with the CPO seat.
- `pitches_8`: holders at score 8, the default limit.

Target 5: from January 2014 each seed runs an AI product and a 10-person AI lab (M11's target
3a lab, ML research 14, fully funded) in two arms, `early` (Transformers arrives when the
lab's level reaches its threshold) and `schedule` (the same with no early arrival: the era
arrives on its historical month); customers of the player's AI products are compared at the
end of the early arm's first-mover window. True values are read here; this is a tool.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.m8 import add_staff, fork, steady_at_stage_3
from tst.balance.report import SCENARIO, _loaded
from tst.balance.strategies import SEAT_ROLES, appoint_executives, do_nothing, launch_ready
from tst.loader import LoadedData
from tst.sim.actions import (
    AppointExecutive,
    AssignUnit,
    CreateProduct,
    CreateUnit,
    MovePerson,
    SetMarketing,
    SetPrice,
)
from tst.sim.actions.authority import AnswerProposal, SetAuthority
from tst.sim.actions.research import StartProject
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, apply_entries
from tst.sim.org.models import PitchPolicy
from tst.sim.products.models import SELLING
from tst.sim.state import with_person_state, with_pitch_policy

SEEDS: Final = tuple(range(1, 11))
MONTHS: Final = 36
SEATS_GIVEN: Final = ("cto", "cro", "cmo", "coo", "cfo", "cpo")
GOOD: Final = 15.0
WEAK: Final = 8.0
ARMS: Final = ("pitches", "off", "pitches_8")
ERA: Final = "transformers"
LAB_FROM: Final = ym_to_turn(2014, 1)
LAB_SIZE: Final = 10
LAB_SKILL: Final = 14.0
LAB_FUNDING: Final = 10_000_000_000  # $100M: target 5 is about the era, not solvency
AI_TEAM: Final = 6  # builders on the AI product
AI_MARKETING: Final = 5_000_000  # $50,000 a month on it
AI_SEGMENT: Final = "smb"
LATEST: Final = ym_to_turn(2020, 1)  # stop if the era never arrives early


@dataclass(frozen=True, slots=True)
class Run:
    seed: int
    arm: str
    stage_3_turn: int | None
    arr: int  # cents at the end; 0 when the game ended
    new_products: int  # launched after the fork
    new_regions: int  # product launches in a region after the fork
    pitches: int  # pitches made
    hits: int
    scored: int  # pitches scored hit or miss (too early counts as a miss for the rate)


def _energy(game: Game) -> None:
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def _seat(game: Game, score: float, limit: int | None) -> None:
    for seat in SEATS_GIVEN:
        (pid,) = add_staff(game, SEAT_ROLES[seat], "senior", 1, skill=score)
        _energy(game)
        game.act(AppointExecutive(game.founder_id, seat, pid))
        game.act(SetAuthority(game.founder_id, seat, True))
    _energy(game)
    game.state = with_pitch_policy(game.state, PitchPolicy(PLAYER, auto_approve_cents=limit))


def _refill(game: Game) -> None:
    appoint_executives(game, SEATS_GIVEN)
    for seat in SEATS_GIVEN:
        a = game.state.authority(PLAYER, seat)
        if game.state.seat_holder(PLAYER, seat) is not None and (a is None or not a.enabled):
            game.act(SetAuthority(game.founder_id, seat, True))


def _arm(base: Game, arm: str) -> Run:
    game = fork(base)
    _seat(game, WEAK if arm == "pitches_8" else GOOD, 0 if arm == "off" else None)
    products = {p.id for p in game.state.company_products(PLAYER) if p.status in SELLING}
    regions = {(r.product_id, r.region) for r in game.state.product_regions}
    for _ in range(MONTHS):
        if game.state.ended:
            break
        for p in game.state.pending_proposals(PLAYER):
            game.act(AnswerProposal(game.founder_id, p.id, True))
        _refill(game)
        game.turn()
    state = game.state
    launched = [
        p
        for p in state.company_products(PLAYER)
        if p.id not in products and p.launched_turn is not None
    ]
    entered = {
        (r.product_id, r.region)
        for r in state.product_regions
        if r.product_id in {p.id for p in state.company_products(PLAYER)}
    } - regions
    mine = [p for p in state.pitches if p.company_id == PLAYER]
    scored = [p for p in mine if p.outcome is not None]
    arr = game.snapshots[-1].arr_cents if game.snapshots and not state.ended else 0
    return Run(
        seed=0,
        arm=arm,
        stage_3_turn=base.state.turn,
        arr=arr,
        new_products=len(launched),
        new_regions=len(entered),
        pitches=len(mine),
        hits=sum(1 for p in scored if p.outcome == "hit"),
        scored=len(scored),
    )


def play(seed: int) -> list[Run]:
    base = steady_at_stage_3(seed)
    if base is None:
        return [Run(seed, arm, None, 0, 0, 0, 0, 0, 0) for arm in ARMS]
    return [replace(_arm(base, arm), seed=seed) for arm in ARMS]


# --- Target 5 ------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EraRun:
    seed: int
    arrived: int | None  # the early arm's arrival; None if it never came early
    early: float  # the player's AI customers at the window's end, early arm
    schedule: float  # the same month, the era on schedule


def _no_early(loaded: LoadedData) -> LoadedData:
    b = loaded.balance
    rnd = b.rnd.model_copy(update={"era_lead": 10.0**6})  # tunable-exempt: never early
    return replace(loaded, balance=b.model_copy(update={"rnd": rnd}))


def _ai_company(game: Game) -> None:
    """From January 2014: funding, an AI product with a team and a 10-person AI lab."""
    entry = LedgerEntry.transfer(
        turn=game.state.turn,
        company_id=PLAYER,
        memo="Target 5 funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=LAB_FUNDING,
    )
    game.balances = apply_entries(game.balances, (entry,))
    _energy(game)
    product = game.state.next_ids.product
    game.act(CreateProduct(game.founder_id, "Oracle", "ai_models", (AI_SEGMENT,)))
    cat = game.loaded.game_data.category("ai_models")
    game.act(
        SetPrice(game.founder_id, product, AI_SEGMENT, cat.market(AI_SEGMENT).reference_price_cents)
    )
    for name, role, size, project in (
        ("Oracle team", "software_engineer", AI_TEAM, False),
        ("Lab", "data_scientist", LAB_SIZE, True),
    ):
        people = add_staff(game, role, "senior", size, skill=LAB_SKILL if project else None)
        _energy(game)
        before = {u.id for u in game.state.active_units(PLAYER)}
        game.act(CreateUnit(game.founder_id, "team", name))
        (unit,) = [u.id for u in game.state.active_units(PLAYER) if u.id not in before]
        for pid in people:
            _energy(game)
            game.act(MovePerson(game.founder_id, pid, unit))
        _energy(game)
        if project:
            assert game.act(StartProject(game.founder_id, unit, "ai"))
        else:
            game.act(AssignUnit(game.founder_id, product, unit))
    game.act(SetMarketing(game.founder_id, product, AI_MARKETING))


def _ai_customers(game: Game) -> float:
    state = game.state
    ids = [p.id for p in state.company_products(PLAYER) if p.category == "ai_models"]
    home = sum(s.customers for pid in ids for s in state.segments_of(pid))
    return home + sum(s.customers for pid in ids for s in state.regional_segments_of(pid))


def _until(game: Game, turn: int) -> None:
    while game.state.turn < turn and not game.state.ended:
        launch_ready(game)
        _energy(game)
        game.turn()


def play_era(seed: int) -> EraRun:
    early = start_game(_loaded("data"), seed, SCENARIO)
    while early.state.turn < LAB_FROM and not early.state.ended:
        do_nothing(early)
        early.turn()
    _ai_company(early)
    calm = fork(early)
    calm.loaded = _no_early(calm.loaded)
    arrived = None
    while early.state.turn < LATEST and not early.state.ended:
        launch_ready(early)
        _energy(early)
        early.turn()
        a = early.state.era_arrival(ERA)
        if a is not None:
            arrived = a.turn if a.company_id == PLAYER else None
            break
    if arrived is None:
        return EraRun(seed, None, 0.0, 0.0)
    end = arrived + early.loaded.balance.rnd.first_mover_months
    _until(early, end)
    _until(calm, end)
    return EraRun(seed, arrived, _ai_customers(early), _ai_customers(calm))


# --- Run and report -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    runs: list[Run]
    eras: list[EraRun]


def run(seeds: tuple[int, ...] = SEEDS, jobs: int = 1) -> Results:
    if jobs <= 1:
        return Results([r for s in seeds for r in play(s)], [play_era(s) for s in seeds])
    with ProcessPoolExecutor(jobs) as pool:
        f1 = pool.map(play, seeds)
        f5 = pool.map(play_era, seeds)
        return Results([r for runs in f1 for r in runs], list(f5))


def arm(results: Results, name: str) -> list[Run]:
    return [r for r in results.runs if r.arm == name and r.stage_3_turn is not None]


def target_1(results: Results) -> int:
    """Seeds with at least one new product launched and one new region entered."""
    return sum(1 for r in arm(results, "pitches") if r.new_products >= 1 and r.new_regions >= 1)


def target_2(results: Results) -> float:
    on, off = arm(results, "pitches"), arm(results, "off")
    under = median(r.arr for r in off) if off else 0
    return median(r.arr for r in on) / under if on and under else 0.0


def hit_rate(runs: list[Run]) -> float:
    scored = sum(r.scored for r in runs)
    return sum(r.hits for r in runs) / scored if scored else 0.0


def target_3(results: Results) -> tuple[float, float]:
    return hit_rate(arm(results, "pitches")), hit_rate(arm(results, "pitches_8"))


def target_4(results: Results) -> float:
    """Median pitches a year per company (the pitches arm)."""
    runs = arm(results, "pitches")
    return median(r.pitches / (MONTHS / 12) for r in runs) if runs else 0.0  # tunable-exempt


def target_5(results: Results) -> tuple[int, list[float]]:
    """(seeds with 15-35% more customers, every seed's lift)."""
    lifts = [e.early / e.schedule - 1 for e in results.eras if e.arrived and e.schedule > 0]
    lo, hi = 0.15, 0.35  # tunable-exempt: 27.5 target 5's band
    return sum(1 for x in lifts if lo <= x <= hi), lifts


def report(results: Results) -> str:
    lines = []
    for r in sorted(results.runs, key=lambda r: (r.seed, ARMS.index(r.arm))):
        if r.stage_3_turn is None:
            lines.append(f"seed {r.seed:2d} {r.arm:<10} never reached stage 3")
            continue
        lines.append(
            f"seed {r.seed:2d} {r.arm:<10} stage 3 at {r.stage_3_turn}: ARR ${r.arr // 100:,}; "
            f"new products {r.new_products}, regions {r.new_regions}; pitches {r.pitches}, "
            f"hits {r.hits} of {r.scored} scored"
        )
    for e in results.eras:
        lift = f"{e.early / e.schedule - 1:+.1%}" if e.arrived and e.schedule else "-"
        lines.append(
            f"seed {e.seed:2d} era: arrived {e.arrived}; AI customers {e.early:,.0f} early, "
            f"{e.schedule:,.0f} on schedule ({lift})"
        )
    on = arm(results, "pitches")
    one = target_1(results)
    lines.append(f"27.5 target 1: new product and region on {one}/{len(on)} seeds (>= 7)")
    lines.append(f"27.5 target 2: pitches / off median ARR {target_2(results):.2f} (>= 1.10)")
    good, weak = target_3(results)
    lines.append(
        f"27.5 target 3: hit rate score 15 {good:.0%}, score 8 {weak:.0%}: "
        f"{(good - weak) * 100:+.0f} points (>= +15)"
    )
    lines.append(f"27.5 target 4: {target_4(results):.1f} pitches a year on median (<= 8)")
    n, lifts = target_5(results)
    shown = ", ".join(f"{x:+.0%}" for x in lifts)
    lines.append(f"27.5 target 5: 15-35% more customers on {n} seeds (>= 7): {shown}")
    return "\n".join(lines)
