"""Playing the strategies and checking docs/balance-targets.md.

`play` runs one strategy on one seed and keeps only plain numbers (`RunResult`), so runs can
go to worker processes; `evaluate` turns a set of results into one row per target.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from statistics import mean, median
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.strategies import STRATEGIES
from tst.loader import LoadedData, load_all
from tst.sim.rivals.startups import is_entrant

SEEDS: Final = tuple(range(1, 11))
TURNS: Final = 120
SCENARIO: Final = "ex_big_tech_founders"
VALUE_WINDOW: Final = 12  # founder value is the mean of the last 12 month ends (109-120)
SUCCESS_MULT: Final = 3  # success: mean founder value >= 3x the turn-0 value
PLAYERS: Final = ("bootstrap-frugal", "steady", "blitzscale")  # T3
DIFFICULTY_RUNS: Final = (("steady", "easy"), ("steady", "hard"))  # T5's extra runs
E3_MONTHS: Final = 24
# S2 for v2 (M10d brief): what CI's nightly needs plus 25% headroom, re-set when a milestone
# adds work per turn. M7a set 20 for v1.
S2_BUDGET: Final = 43.0
STARTUP_YEARS_MONTHS: Final = 60  # T7: alive five years after founding
EARLY_LEAVE_MONTHS: Final = 12  # T6


@dataclass(frozen=True, slots=True)
class Tenure:
    start: int
    end: int | None  # None: still employed at the end of the run
    reason: str | None


@dataclass(frozen=True, slots=True)
class RunResult:
    strategy: str
    seed: int
    difficulty: str
    turns: int  # turns asked for
    seconds: float
    game_state: str
    ended_turn: int | None
    value_start: int  # founder value at turn 0, cents
    value_mean: float  # mean founder value over the last VALUE_WINDOW month ends
    traction_above_floor: bool  # V_traction > V_floor at the last month end
    arr_cents: int  # at the last month end
    rounds: dict[str, int]  # series -> month it closed
    launch_turn: int | None
    tenures: tuple[Tenure, ...]  # the player's employees (not the founder)
    incumbents: int
    incumbents_alive: int
    startups: tuple[tuple[int, int | None], ...]  # (founded_turn, failed_turn)
    events: tuple[tuple[int, str, str], ...]  # (turn, template id, trigger), the player's
    refused: dict[str, int] = field(default_factory=dict)

    @property
    def bankrupt(self) -> bool:
        return self.game_state == "bankrupt"

    @property
    def succeeded(self) -> bool:
        return (
            self.game_state == "active"
            and self.value_mean >= SUCCESS_MULT * self.value_start
            and self.traction_above_floor
        )


@cache
def _loaded(data_dir: str) -> LoadedData:
    return load_all(Path(data_dir))


def play(
    strategy: str,
    seed: int,
    turns: int = TURNS,
    difficulty: str = "standard",
    data_dir: str = "data",
) -> RunResult:
    """One strategy on one seed. Picklable arguments and result (worker processes)."""
    started = time.perf_counter()
    game = start_game(_loaded(data_dir), seed, SCENARIO, difficulty)
    script = STRATEGIES[strategy]
    launch: int | None = None
    for _ in range(turns):
        if game.state.ended:
            break
        script(game)
        if launch is None and any(p.status == "live" for p in game.state.company_products(PLAYER)):
            launch = game.state.turn
        game.turn()
    return _result(game, strategy, seed, difficulty, turns, time.perf_counter() - started, launch)


def _result(
    game: Game,
    strategy: str,
    seed: int,
    difficulty: str,
    turns: int,
    seconds: float,
    launch: int | None,
) -> RunResult:
    state = game.state
    last = turns
    window = [game.founder_value.get(t, 0) for t in range(last - VALUE_WINDOW + 1, last + 1)]
    founder = game.founder_id
    rivals = [c for c in state.companies if not c.is_player]
    incumbents = [c for c in rivals if not c.is_startup]
    return RunResult(
        strategy=strategy,
        seed=seed,
        difficulty=difficulty,
        turns=turns,
        seconds=seconds,
        game_state=state.save_meta.game_state,
        ended_turn=state.save_meta.ended_turn,
        value_start=game.founder_value[0],
        value_mean=mean(window),
        traction_above_floor=game.traction_above_floor.get(last, False),
        arr_cents=game.snapshots[-1].arr_cents if game.snapshots else 0,
        rounds={
            r.series: r.closed_turn
            for r in state.company_rounds(PLAYER)
            if r.status == "closed" and r.closed_turn is not None
        },
        launch_turn=launch,
        tenures=tuple(
            Tenure(e.start_turn, e.end_turn if e.status == "ended" else None, e.end_reason)
            for e in state.employments
            if e.company_id == PLAYER and e.person_id != founder
        ),
        incumbents=len(incumbents),
        incumbents_alive=sum(1 for c in incumbents if c.alive),
        # T7 measures the 15.4 startups; scheduled entrants are real companies (M8, 18.7).
        startups=tuple(
            (c.founded_turn, c.failed_turn)
            for c in rivals
            if c.is_startup and not is_entrant(c, game.loaded.game_data)
        ),
        events=tuple(
            (e.turn, e.template_id, e.trigger) for e in state.events if e.company_id == PLAYER
        ),
        refused=dict(game.refused),
    )


def run_all(
    seeds: Sequence[int] = SEEDS,
    turns: int = TURNS,
    strategies: Iterable[str] = tuple(STRATEGIES),
    difficulty_runs: bool = True,
    jobs: int = 1,
    data_dir: str = "data",
) -> list[RunResult]:
    """Every strategy on every seed at standard difficulty, plus T5's difficulty runs."""
    plan = [(s, seed, "standard") for s in strategies for seed in seeds]
    if difficulty_runs:
        plan += [(s, seed, d) for s, d in DIFFICULTY_RUNS for seed in seeds]
    if jobs <= 1:
        return [play(s, seed, turns, d, data_dir) for s, seed, d in plan]
    with ProcessPoolExecutor(jobs) as pool:
        futures = [pool.submit(play, s, seed, turns, d, data_dir) for s, seed, d in plan]
        return [f.result() for f in futures]


# --- Targets ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Row:
    target: str
    measure: str
    value: str
    band: str
    ok: bool | None  # None: printed only
    gate: bool = False  # a pass/fail target (T1-T3): the runner exits 1 if it fails


def _runs(
    results: Sequence[RunResult], strategy: str, difficulty: str = "standard"
) -> list[RunResult]:
    return [r for r in results if r.strategy == strategy and r.difficulty == difficulty]


def _median_months(runs: Sequence[RunResult], series: str) -> float | None:
    """Median month a series closed, unreached counted as never (None if most never)."""
    if not runs:
        return None
    months = sorted(r.rounds.get(series, 10**6) for r in runs)
    value = median(months)
    return None if value >= 10**6 else value


def _in(value: float | None, low: float, high: float) -> bool:
    return value is not None and low <= value <= high


def _fmt(value: float | None, suffix: str = "") -> str:
    return "-" if value is None else f"{value:g}{suffix}"


def winners(results: Sequence[RunResult]) -> Counter[str]:
    """Wins per strategy over the standard runs: the highest mean founder value on a seed;
    a tie means nobody wins that seed."""
    wins: Counter[str] = Counter()
    by_seed: dict[int, list[RunResult]] = {}
    for r in results:
        if r.difficulty == "standard":
            by_seed.setdefault(r.seed, []).append(r)
    for runs in by_seed.values():
        best = max(r.value_mean for r in runs)
        top = [r for r in runs if r.value_mean == best]
        if len(top) == 1:
            wins[top[0].strategy] += 1
    return wins


def evaluate(results: Sequence[RunResult]) -> list[Row]:
    rows: list[Row] = []
    seeds = len({r.seed for r in results if r.difficulty == "standard"})

    nothing = _runs(results, "do-nothing")
    if nothing:
        failed = sum(not r.succeeded for r in nothing)
        rows.append(
            Row(
                "T1",
                "do-nothing fails",
                f"{failed}/{len(nothing)}",
                "all",
                failed == len(nothing),
                True,
            )
        )
    wins = winners(results)
    most = max(wins.values(), default=0)
    detail = ", ".join(f"{s} {wins.get(s, 0)}" for s in STRATEGIES)
    cap = 6 * seeds / 10
    rows.append(
        Row("T2", "wins per strategy", detail, f"each <= {cap:g}/{seeds}", most <= cap, True)
    )
    for s in PLAYERS:
        runs = _runs(results, s)
        if runs:
            ok = sum(r.succeeded for r in runs)
            need = 3 * len(runs) / 10
            rows.append(
                Row("T3", f"{s} succeeds", f"{ok}/{len(runs)}", f">= {need:g}", ok >= need, True)
            )

    for s, low, high in (("steady", 1, 24), ("blitzscale", 1, 12)):  # Reece: C1 and B2
        m = _median_months(_runs(results, s), "seed")
        rows.append(
            Row("T4a", f"{s}: median months to seed", _fmt(m), f"{low}-{high}", _in(m, low, high))
        )
    for s, low, high in (("steady", 24, 60), ("blitzscale", 12, 36)):
        m = _median_months(_runs(results, s), "a")
        rows.append(
            Row(
                "T4b",
                f"{s}: median months to Series A",
                _fmt(m),
                f"{low}-{high}",
                _in(m, low, high),
            )
        )
    blitz = _runs(results, "blitzscale")
    reached = [r.rounds["b"] for r in blitz if "b" in r.rounds]
    m_b = median(reached) if reached else None
    need_b = 4 * len(blitz) / 10
    rows.append(
        Row(
            "T4c",
            "blitzscale: median months to Series B (where reached)",
            f"{_fmt(m_b)} on {len(reached)}/{len(blitz)}",
            f"30-72 on >= {need_b:g}",
            _in(m_b, 30, 72) and len(reached) >= need_b,
        )
    )
    rows.append(Row("T4d", "median months to IPO", "-", "not in v1", None))

    bands: tuple[tuple[str, str, float, float], ...] = (
        ("steady", "easy", 0.0, 0.10),
        ("steady", "standard", 0.0, 0.25),  # Reece, C2
        ("steady", "hard", 0.0, 0.70),  # Reece, C2
        ("blitzscale", "standard", 0.0, 0.40),  # Reece, B3; re-banded in M10d (2026-11-02)
        ("bootstrap-frugal", "standard", 0.20, 0.50),  # Reece, C3 (a)
    )
    for s, d, lo, hi in bands:
        runs = _runs(results, s, d)
        if runs:
            rate = sum(r.bankrupt for r in runs) / len(runs)
            rows.append(
                Row(
                    "T5",
                    f"{s} ({d}): bankrupt by the end",
                    f"{rate:.0%}",
                    f"{lo:.0%}-{hi:.0%}",
                    lo <= rate <= hi,
                )
            )

    rows += _tenure_rows([r for r in results if r.difficulty == "standard"])
    rows += _rival_rows(nothing)

    for s in PLAYERS:
        runs = _runs(results, s)
        if runs:
            arr = median(r.arr_cents for r in runs) / 100
            rows.append(Row("T8", f"{s}: median ARR at the end", f"${arr:,.0f}", "printed", None))

    rows += _solo_rows(results)
    worker = sum(r.seconds for r in results) / 60
    rows.append(
        Row(
            "S2",
            "balance run, worker-minutes (this machine)",
            f"{worker:.1f}",
            f"< {S2_BUDGET:g} on CI",
            worker < S2_BUDGET,
        )
    )
    return rows


def _tenure_rows(results: Sequence[RunResult]) -> list[Row]:
    """T6 over the player's employees of every strategy: leavers exclude a company closing."""
    tenures = [(t, r.ended_turn or r.turns) for r in results for t in r.tenures]
    if not tenures:
        return []
    leavers = [t for t, _ in tenures if t.end is not None and t.reason != "company_failed"]
    lengths = [t.end - t.start for t in leavers if t.end is not None]
    staff_years = sum(((t.end if t.end is not None else end) - t.start) for t, end in tenures) / 12
    rate = len(leavers) / staff_years if staff_years else 0.0
    eligible = [t for t, end in tenures if t.start <= end - EARLY_LEAVE_MONTHS]
    early = [
        t
        for t in eligible
        if t.end is not None
        and t.reason != "company_failed"
        and t.end - t.start < EARLY_LEAVE_MONTHS
    ]
    med = median(lengths) if lengths else None
    share = len(early) / len(eligible) if eligible else 0.0
    return [
        Row("T6", "median tenure of leavers (months)", _fmt(med), "18-48", _in(med, 18, 48)),
        Row("T6", "staff leaving each year", f"{rate:.0%}", "10%-25%", 0.10 <= rate <= 0.25),
        Row(
            "T6", "hires leaving in their first 12 months", f"{share:.0%}", "<= 25%", share <= 0.25
        ),
    ]


def _rival_rows(nothing: Sequence[RunResult]) -> list[Row]:
    """T7 over the do-nothing runs."""
    if not nothing:
        return []
    alive = mean(r.incumbents_alive for r in nothing)
    total = nothing[0].incumbents
    turns = nothing[0].turns
    old = [
        (founded, failed)
        for r in nothing
        for founded, failed in r.startups
        if founded + STARTUP_YEARS_MONTHS <= turns
    ]
    survived = [f for f in old if f[1] is None or f[1] > f[0] + STARTUP_YEARS_MONTHS]
    share = len(survived) / len(old) if old else None
    need = total * 10 / 12
    return [
        Row(
            "T7",
            "incumbents in business at the end",
            f"{alive:.1f}/{total}",
            f">= {need:g}",
            alive >= need,
        ),
        Row(
            "T7",
            "rival startups alive 5 years after founding",
            f"{_fmt(None if share is None else round(100 * share))}% of {len(old)}",
            "20%-65%",  # re-banded in M10d (product manager, 2026-11-02)
            share is not None and 0.2 <= share <= 0.65,
        ),
    ]


def _solo_rows(results: Sequence[RunResult]) -> list[Row]:
    """E3: a solo founder with no product (do-nothing), and bootstrap-frugal before launch,
    over the first 24 months."""
    rows = []
    for s, label in (
        ("do-nothing", "solo founder"),
        ("bootstrap-frugal", "bootstrap before launch"),
    ):
        runs = _runs(results, s)
        if not runs:
            continue
        per_run = []
        for r in runs:
            end = min(E3_MONTHS, r.launch_turn if r.launch_turn is not None else E3_MONTHS)
            per_run.append([e for e in r.events if e[0] < end])
        distinct = mean(len({e[1] for e in events}) for events in per_run)
        pooled = [e for events in per_run for e in events]
        finance = set(_finance_templates())
        dull = sum(1 for e in pooled if e[2] == "quiet_month" or e[1] in finance)
        share = dull / len(pooled) if pooled else 0.0
        repeat = max(
            (max(Counter(e[1] for e in ev).values(), default=0) for ev in per_run), default=0
        )
        if s == "do-nothing":
            rows.append(
                Row(
                    "E3",
                    f"{label}: distinct templates a run (24 months)",
                    f"{distinct:.1f}",
                    ">= 10",
                    distinct >= 10,
                )
            )
        else:
            rows.append(
                Row("E3", f"{label}: distinct templates a run", f"{distinct:.1f}", "printed", None)
            )
        rows.append(
            Row(
                "E3",
                f"{label}: finance and quiet-month share",
                f"{share:.0%}",
                "<= 50%",
                share <= 0.5,
            )
        )
        rows.append(
            Row("E3", f"{label}: most repeats of one template", str(repeat), "<= 3", repeat <= 3)
        )
    return rows


@cache
def _finance_templates() -> frozenset[str]:
    data = _loaded("data").game_data
    return frozenset(t.id for t in data.event_templates if t.category == "finance")


def table(rows: Sequence[Row]) -> str:
    width = max(len(r.measure) for r in rows)
    lines = []
    for r in rows:
        mark = "    " if r.ok is None else (" ok " if r.ok else "FAIL")
        lines.append(f"{mark} {r.target:4s} {r.measure:{width}s}  {r.value:>28s}  ({r.band})")
    return "\n".join(lines)


def runs_table(results: Sequence[RunResult]) -> str:
    """One line per run: what happened."""
    lines = []
    for r in sorted(results, key=lambda r: (r.strategy, r.difficulty, r.seed)):
        rounds = " ".join(f"{k}@{v}" for k, v in sorted(r.rounds.items(), key=lambda x: x[1]))
        lines.append(
            f"{r.strategy:16s} {r.difficulty:8s} seed {r.seed:2d} | {r.game_state:15s}"
            f"{'' if r.ended_turn is None else f' @{r.ended_turn}':5s} | value x"
            f"{r.value_mean / r.value_start if r.value_start else 0:5.2f}"
            f" traction>floor {'y' if r.traction_above_floor else 'n'}"
            f" | ARR ${r.arr_cents / 100:>12,.0f}"
            f" | staff {sum(t.end is None for t in r.tenures):3d}"
            f" | {rounds} | {r.seconds:5.1f}s"
        )
    return "\n".join(lines)
