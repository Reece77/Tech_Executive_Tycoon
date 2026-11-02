"""docs/formulas.md 21.8 targets 2, 3 and 5 (M11), printed by tools/m11_targets.py and checked
nightly (tests/balance/test_m11_balance.py). Targets 1 and 4 are unit tests
(tests/unit/test_research_eras.py, tests/unit/test_formulas_m11_worked_examples.py).

- Target 2: each seed's steady game forks at its first month at stage 2's ARR gate ($1M,
  11.11; steady reaches stage 2 by its seed round at month 4-6, with no revenue, when a
  $1M-a-year research unit bankrupts it on every seed). The `research` arm
  adds a 6-person research unit (senior software engineers, generated on stream `misc` as in
  m8.py) researching software platform, B2B SaaS's top domain, fully funded; the `steady` arm
  plays on. Both run to turn 120. ARR is compared net of the research cost (12 x the month's
  budget and the researchers' monthly employment cost), with the first product's quality.
- Target 3a: from January 2014 a 10-person AI lab (every skill 14) researches AI, fully
  funded, with the money to do it; Transformers must come before January 2017.
- Target 3b: in do-nothing runs, how often a rival brings an era more than 6 months early.
- Target 5: in the research arm, the cost of gaining 15 points (half a 30-point gap) with the
  6-person unit (budget and the researchers' employment cost until the lead reaches 15)
  against licensing 15 points at the player's ARR then.

True values are read here (leads, costs): this is a tool, not the API.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.m8 import add_staff, fork
from tst.balance.report import SCENARIO, _loaded
from tst.balance.strategies import do_nothing, steady
from tst.sim.actions import CreateUnit, MovePerson
from tst.sim.actions.research import StartProject
from tst.sim.calendar import ym_to_turn
from tst.sim.hiring.phases import employment_monthly_cost_cents
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, apply_entries
from tst.sim.org.rules import org_view
from tst.sim.research.formulas import license_price_cents
from tst.sim.research.licensing import arr_cents
from tst.sim.research.projects import lab
from tst.sim.state import with_person_state

SEEDS: Final = tuple(range(1, 11))
TURNS: Final = 120
STAGE_2_BY: Final = 120
RESEARCHERS: Final = 6
LAB_SIZE: Final = 10
LAB_SKILL: Final = 14.0
LAB_FROM: Final = ym_to_turn(2014, 1)
LAB_BY: Final = ym_to_turn(2017, 1)
LAB_FUNDING: Final = 10_000_000_000  # $100M: target 3a is about research, not solvency
HALF_GAP: Final = 15.0
EARLY: Final = 6  # months
QUIET_TURNS: Final = 200  # do-nothing runs cover the eras to 2026
DOMAIN: Final = "software_platform"


@dataclass(frozen=True, slots=True)
class ArmRun:
    seed: int
    arm: str
    stage_2_turn: int | None
    arr: int
    quality: float
    research_cost: int  # a year, at the end (budget + researchers' employment cost)
    half_gap_cost: int | None  # spent until the lead first reached 15
    half_gap_licence: int | None  # licensing 15 points at the ARR then
    lead: float


def _energy(game: Game) -> None:
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def _start_lab(game: Game, domain: str, count: int, role: str, skill: float | None) -> list[int]:
    people = add_staff(game, role, "senior", count, skill=skill)
    _energy(game)
    before = {u.id for u in game.state.active_units(PLAYER)}
    game.act(CreateUnit(game.founder_id, "team", "Lab"))
    (unit,) = [u.id for u in game.state.active_units(PLAYER) if u.id not in before]
    for pid in people:
        _energy(game)
        game.act(MovePerson(game.founder_id, pid, unit))
    _energy(game)
    assert game.act(StartProject(game.founder_id, unit, domain))
    return people


def _refill_lab(game: Game, people: list[int], domain: str) -> list[int]:
    """Keep the research unit at RESEARCHERS: a researcher who left is replaced by a new
    senior hire into the same unit (the target is a 6-person unit throughout)."""
    projects = [p for p in game.state.active_projects(PLAYER) if p.domain == domain]
    if not projects or projects[0].unit_id is None:
        return people
    unit = projects[0].unit_id
    staying = [pid for pid in people if game.state.employment_of(pid) is not None]
    for pid in add_staff(game, "software_engineer", "senior", RESEARCHERS - len(staying)):
        _energy(game)
        game.act(MovePerson(game.founder_id, pid, unit))
        staying.append(pid)
    return staying


def _monthly_cost(game: Game, people: list[int]) -> int:
    """The project's budget this month plus its researchers' employment cost."""
    state, b, data = game.state, game.loaded.balance, game.loaded.game_data
    projects = state.active_projects(PLAYER)
    if not projects:
        return 0
    view = org_view(state, PLAYER)
    budget = sum(lab(state, view, p, b, data).budget_cents for p in projects)
    pay = 0
    for pid in people:
        e = state.employment_of(pid)
        if e is not None:
            pay += employment_monthly_cost_cents(e, b)
    return budget + pay


def _quality(game: Game) -> float:
    products = [p for p in game.state.company_products(PLAYER) if p.status != "retired"]
    return products[0].quality if products else 0.0


def _arm(base: Game, arm: str, seed: int) -> ArmRun:
    game = fork(base)
    people = (
        _start_lab(game, DOMAIN, RESEARCHERS, "software_engineer", None)
        if arm == "research"
        else []
    )
    spent = 0
    half_cost = half_licence = None
    while game.state.turn < TURNS and not game.state.ended:
        steady(game)
        if people:
            people = _refill_lab(game, people, DOMAIN)
        spent += _monthly_cost(game, people)
        game.turn()
        lead = game.state.research_lead(PLAYER, DOMAIN)
        if people and half_cost is None and lead >= HALF_GAP:
            half_cost = spent
            arr = arr_cents(game.state, PLAYER)
            half_licence = license_price_cents(HALF_GAP, arr, game.loaded.balance)
    ended = game.state.ended
    arr = game.snapshots[-1].arr_cents if game.snapshots and not ended else 0
    return ArmRun(
        seed=seed,
        arm=arm,
        stage_2_turn=base.state.turn,
        arr=arr,
        quality=_quality(game),
        research_cost=12 * _monthly_cost(game, people) if people and not ended else 0,
        half_gap_cost=half_cost,
        half_gap_licence=half_licence,
        lead=game.state.research_lead(PLAYER, DOMAIN),
    )


def steady_at_stage_2(seed: int) -> Game | None:
    """Steady at its first month with ARR at stage 2's gate (11.11)."""
    game = start_game(_loaded("data"), seed, SCENARIO)
    gate = game.loaded.balance.stages.arr_cents[2]  # tunable-exempt: 21.8 target 2's stage
    for _ in range(STAGE_2_BY):
        if game.state.ended:
            return None
        if game.snapshots and game.snapshots[-1].arr_cents >= gate:
            return game
        steady(game)
        game.turn()
    return None


def play_target_2(seed: int) -> list[ArmRun]:
    base = steady_at_stage_2(seed)
    if base is None:
        return [ArmRun(seed, a, None, 0, 0.0, 0, None, None, 0.0) for a in ("steady", "research")]
    return [_arm(base, a, seed) for a in ("steady", "research")]


def play_lab(seed: int) -> tuple[int, int | None, int | None]:
    """(seed, the month Transformers arrived, who caused it) for target 3a."""
    game = start_game(_loaded("data"), seed, SCENARIO)
    while game.state.turn < LAB_FROM and not game.state.ended:
        do_nothing(game)
        game.turn()
    entry = LedgerEntry.transfer(
        turn=game.state.turn,
        company_id=PLAYER,
        memo="Target 3a funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=LAB_FUNDING,
    )
    game.balances = apply_entries(game.balances, (entry,))
    _start_lab(game, "ai", LAB_SIZE, "data_scientist", LAB_SKILL)
    while game.state.turn < LAB_BY and not game.state.ended:
        game.turn()
        arrival = game.state.era_arrival("transformers")
        if arrival is not None:
            return seed, arrival.turn, arrival.company_id
    return seed, None, None


def play_quiet(seed: int) -> tuple[int, list[tuple[str, int, int | None]]]:
    """(seed, [(era, months early, causer)]) in a do-nothing run of QUIET_TURNS."""
    game = start_game(_loaded("data"), seed, SCENARIO)
    while game.state.turn < QUIET_TURNS and not game.state.ended:
        do_nothing(game)
        game.turn()
    return seed, [(a.key, a.months_early, a.company_id) for a in game.state.era_arrivals]


@dataclass(frozen=True, slots=True)
class Results:
    target_2: list[ArmRun]
    lab: list[tuple[int, int | None, int | None]]
    quiet: list[tuple[int, list[tuple[str, int, int | None]]]]


def run(seeds: tuple[int, ...] = SEEDS, jobs: int = 1) -> Results:
    if jobs <= 1:
        two = [r for s in seeds for r in play_target_2(s)]
        labs = [play_lab(s) for s in seeds]
        quiet = [play_quiet(s) for s in seeds]
    else:
        with ProcessPoolExecutor(jobs) as pool:
            f2 = pool.map(play_target_2, seeds)
            fl = pool.map(play_lab, seeds)
            fq = pool.map(play_quiet, seeds)
            two = [r for runs in f2 for r in runs]
            labs, quiet = list(fl), list(fq)
    return Results(two, labs, quiet)


def target_2(results: Results) -> tuple[float, float, float]:
    """(median net ARR ratio, median gross ratio, median quality gain) over seeds that
    reached stage 2."""
    pairs = []
    for seed in {r.seed for r in results.target_2}:
        s = next(r for r in results.target_2 if r.seed == seed and r.arm == "steady")
        q = next(r for r in results.target_2 if r.seed == seed and r.arm == "research")
        if s.stage_2_turn is not None:
            pairs.append((s, q))
    if not pairs:
        return 0.0, 0.0, 0.0
    net = median(q.arr - q.research_cost for _, q in pairs) / max(
        1, median(s.arr for s, _ in pairs)
    )
    gross = median(q.arr for _, q in pairs) / max(1, median(s.arr for s, _ in pairs))
    gain = median(q.quality - s.quality for s, q in pairs)
    return net, gross, gain


def target_3a(results: Results) -> int:
    return sum(
        1 for _, turn, who in results.lab if turn is not None and who == PLAYER and turn < LAB_BY
    )


def target_3b(results: Results) -> float:
    early = sum(
        1
        for _, arrivals in results.quiet
        if any(who is not None and who != PLAYER and months > EARLY for _, months, who in arrivals)
    )
    return early / len(results.quiet) if results.quiet else 0.0


def target_5(results: Results) -> float | None:
    rows = [r for r in results.target_2 if r.arm == "research" and r.half_gap_cost is not None]
    if not rows:
        return None
    return median(r.half_gap_licence or 0 for r in rows) / max(
        1, median(r.half_gap_cost or 0 for r in rows)
    )


def report(results: Results) -> str:
    lines = []
    for r in sorted(results.target_2, key=lambda r: (r.seed, r.arm)):
        if r.stage_2_turn is None:
            lines.append(f"seed {r.seed:2d} {r.arm:<8} never reached stage 2")
            continue
        half = (
            f"; 15 points cost ${(r.half_gap_cost or 0) // 100:,} vs licence "
            f"${(r.half_gap_licence or 0) // 100:,}"
            if r.half_gap_cost is not None
            else ""
        )
        lines.append(
            f"seed {r.seed:2d} {r.arm:<8} stage 2 at {r.stage_2_turn}: ARR ${r.arr // 100:,}; "
            f"quality {r.quality:.1f}; research ${r.research_cost // 100:,} a year; "
            f"lead {r.lead:.1f}{half}"
        )
    for seed, turn, who in results.lab:
        lines.append(f"seed {seed:2d} AI lab: Transformers at turn {turn} (causer {who})")
    for seed, arrivals in results.quiet:
        early = [f"{k} {m} early ({who})" for k, m, who in arrivals if who is not None]
        lines.append(f"seed {seed:2d} do-nothing: {', '.join(early) or 'every era on schedule'}")
    net, gross, gain = target_2(results)
    lines.append(
        f"21.8 target 2: research / steady median ARR net of research {net:.2f} (>= 1.10; "
        f"gross {gross:.2f}); median quality gain {gain:+.1f} (>= 5)"
    )
    lines.append(
        f"21.8 target 3: AI lab brings Transformers before Jan 2017 on {target_3a(results)}/"
        f"{len(results.lab)} seeds (>= 5); rivals pull an era > 6 months early in "
        f"{target_3b(results):.0%} of do-nothing runs (<= 15%)"
    )
    five = target_5(results)
    shown = f"{five:.2f}" if five is not None else "n/a (the lead never reached 15)"
    lines.append(f"21.8 target 5: licensing 15 points / researching them {shown} (<= 0.7)")
    return "\n".join(lines)
