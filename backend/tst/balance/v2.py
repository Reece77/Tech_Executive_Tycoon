"""docs/formulas.md 30.7 v2 balance targets (M15a), printed by tools/v2_targets.py, checked
nightly (V1-V4, tests/balance/test_v2_balance.py) and weekly (V1's 30 seeds, V5, V6:
.github/workflows/weekly.yml). True values are read here; this is a tool.

- V1-V4 read the runner's ten-year results (tst.balance.report.run_all over the nine
  strategies): wins by founder value at year 10 (T2's measure), median ARR and operating
  margin over the last 12 months.
- V5 plays steady_regions and research_heavy from January 2010 to December 2039 (360 months)
  and records each month what the target needs: era arrivals, total demand, which rivals are
  alive, rival launches by category and the player's stage.
- V6 is a timing test (tests/integration/test_v6_perf.py) on a save built by
  tools/v6_save.py from a 30-year research_heavy run.
- V7 is M10.T3 re-measured (tst.balance.m10) and T5's bootstrap band (report.evaluate).
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.report import SCENARIO, Row, RunResult, _loaded, _runs, winners
from tst.balance.strategies_v2 import STRATEGIES
from tst.sim.calendar import ym_to_turn
from tst.sim.state import GameState

SEEDS: Final = tuple(range(1, 11))
SEEDS_30: Final = tuple(range(1, 31))  # V1's second clause
LONG_SEEDS: Final = tuple(range(1, 11))
LONG_TURNS: Final = ym_to_turn(2039, 12) + 1  # 360: January 2010 to December 2039
LONG_STRATEGIES: Final = ("steady_regions", "research_heavy")
ERA_FROM: Final = ym_to_turn(2026, 1)
RIVALS_FROM: Final = ym_to_turn(2026, 1)
DEMAND_FROM: Final = ym_to_turn(2030, 1)
DECADES: Final = (
    (ym_to_turn(2010, 1), "2010s"),
    (ym_to_turn(2020, 1), "2020s"),
    (ym_to_turn(2030, 1), "2030s"),
)
BASE: Final = "steady_regions"

# 30.7's bands
V1_MAX_WINS: Final = 5  # of 10 seeds
V1_WINNERS: Final = 4  # strategies with a win over 30 seeds
V2_BAND: Final = (1.0, 1.4)
V2_MAX_WINS: Final = 4
V3_POINTS: Final = (0.03, 0.10)
V3_ARR: Final = (0.85, 1.25)
V4_BAND: Final = (0.85, 1.2)
V5_ERAS: Final = 5
V5_GROWTH: Final = 0.04
V5_RIVALS: Final = 0.30
V5_STAGE_4: Final = 5  # of 10 seeds


# --- V1-V4: ten years -----------------------------------------------------------------------


def _median_arr(results: Sequence[RunResult], strategy: str) -> float | None:
    runs = _runs(results, strategy)
    return median(r.arr_cents for r in runs) if runs else None


def _ratio(results: Sequence[RunResult], strategy: str) -> float | None:
    top, base = _median_arr(results, strategy), _median_arr(results, BASE)
    return top / base if top is not None and base else None


def _median_margin(results: Sequence[RunResult], strategy: str) -> float | None:
    margins = [m for r in _runs(results, strategy) if (m := r.margin) is not None]
    return median(margins) if margins else None


def _in(value: float | None, band: tuple[float, float]) -> bool:
    return value is not None and band[0] <= value <= band[1]


def _x(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}x"


def ten_year_rows(results: Sequence[RunResult]) -> list[Row]:
    """V1 (10 seeds), V2, V3 and V4 over the runner's results."""
    rows: list[Row] = []
    seeds = len({r.seed for r in results if r.difficulty == "standard"})
    wins = winners(results)
    most = max(wins.values(), default=0)
    detail = ", ".join(f"{s} {wins[s]}" for s in STRATEGIES if wins.get(s))
    cap = V1_MAX_WINS * seeds / 10
    rows.append(
        Row(
            "V1",
            "most wins of one strategy",
            detail or "-",
            f"each <= {cap:g}/{seeds}",
            most <= cap,
        )
    )
    ratio = _ratio(results, "research_heavy")
    rh_wins = wins.get("research_heavy", 0)
    rows.append(
        Row(
            "V2",
            "research_heavy / steady_regions median ARR",
            _x(ratio),
            f"{V2_BAND[0]}-{V2_BAND[1]}x",
            _in(ratio, V2_BAND),
        )
    )
    cap2 = V2_MAX_WINS * seeds / 10
    rows.append(
        Row("V2", "research_heavy wins", f"{rh_wins}/{seeds}", f"<= {cap2:g}", rh_wins <= cap2)
    )
    mi, mb = _median_margin(results, "integrator"), _median_margin(results, BASE)
    gap = mi - mb if mi is not None and mb is not None else None
    rows.append(
        Row(
            "V3",
            "integrator - steady_regions operating margin",
            "-" if gap is None else f"{gap * 100:+.1f} pts ({mi:.1%} vs {mb:.1%})",
            f"+{V3_POINTS[0] * 100:g} to +{V3_POINTS[1] * 100:g} pts",
            _in(gap, V3_POINTS),
        )
    )
    ratio3 = _ratio(results, "integrator")
    rows.append(
        Row(
            "V3",
            "integrator / steady_regions median ARR",
            _x(ratio3),
            f"{V3_ARR[0]}-{V3_ARR[1]}x",
            _in(ratio3, V3_ARR),
        )
    )
    ratio4 = _ratio(results, "ceo")
    rows.append(
        Row(
            "V4",
            "ceo / steady_regions median ARR",
            _x(ratio4),
            f"{V4_BAND[0]}-{V4_BAND[1]}x",
            _in(ratio4, V4_BAND),
        )
    )
    for s in ("acquirer", BASE):  # printed: M14's 28.9 target 5 reads this pair
        arr = _median_arr(results, s)
        rows.append(
            Row(
                "V",
                f"{s}: median ARR at year 10",
                "-" if arr is None else f"${arr / 100:,.0f}",
                "printed",
                None,
            )
        )
    return rows


def winners_row_30(results: Sequence[RunResult]) -> Row:
    """V1's second clause: at least four strategies win at least once over 30 seeds."""
    wins = winners(results)
    n = sum(1 for v in wins.values() if v > 0)
    seeds = len({r.seed for r in results if r.difficulty == "standard"})
    detail = ", ".join(f"{s} {wins[s]}" for s in STRATEGIES if wins.get(s))
    return Row(
        "V1",
        f"strategies with a win over {seeds} seeds",
        f"{n} ({detail})",
        f">= {V1_WINNERS}",
        n >= V1_WINNERS,
    )


# --- V5: thirty years ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LongRun:
    strategy: str
    seed: int
    ended_turn: int | None
    eras: int  # era arrivals from January 2026 to December 2039
    demand_from: float  # total demand value in January 2030 (addressable x reference price)
    demand_to: float  # in December 2039
    rivals_2026: int  # rivals alive in January 2026
    rivals_alive: int  # of those, still alive at the end
    launches: dict[tuple[str, str], int]  # (category, decade) -> rival launches
    stage_4_turn: int | None
    seconds: float


def demand_value(state: GameState, game: Game) -> float:
    """Every segment's addressable customers x its category's reference price, home and other
    regions (a value-weighted measure of total demand: M15a decision)."""
    data = game.loaded.game_data
    price = {
        (c.key, m.segment): m.reference_price_cents for c in data.categories for m in c.markets
    }
    home = sum(m.addressable * price.get((m.category, m.segment), 0) for m in state.markets)
    away = sum(
        m.addressable * price.get((m.category, m.segment), 0) for m in state.regional_markets
    )
    return home + away


def _decade(turn: int) -> str:
    return next(label for start, label in reversed(DECADES) if turn >= start)


def play_long(job: tuple[str, int]) -> LongRun:
    import time

    strategy, seed = job
    started = time.perf_counter()
    game = start_game(_loaded("data"), seed, SCENARIO)
    script = STRATEGIES[strategy]
    seen: dict[int, tuple[str, int]] = {}  # rival product id -> (category, launched turn)
    demand_from = 0.0
    alive_2026: set[int] = set()
    stage_4: int | None = None
    while game.state.turn < LONG_TURNS and not game.state.ended:
        state = game.state
        if state.turn == DEMAND_FROM:
            demand_from = demand_value(state, game)
        if state.turn == RIVALS_FROM:
            alive_2026 = {c.id for c in state.rivals() if c.alive}
        script(game)
        game.turn()
        state = game.state
        for p in state.products:
            if p.company_id != PLAYER and p.launched_turn is not None and p.id not in seen:
                seen[p.id] = (p.category, p.launched_turn)
        if stage_4 is None and state.player.stage >= 4:
            stage_4 = state.turn
    state = game.state
    launches: dict[tuple[str, str], int] = {}
    for category, turn in seen.values():
        key = (category, _decade(turn))
        launches[key] = launches.get(key, 0) + 1
    eras = sum(1 for a in state.era_arrivals if ERA_FROM <= a.turn < LONG_TURNS)
    alive = {c.id for c in state.companies if c.alive}
    return LongRun(
        strategy=strategy,
        seed=seed,
        ended_turn=state.save_meta.ended_turn,
        eras=eras,
        demand_from=demand_from,
        demand_to=demand_value(state, game),
        rivals_2026=len(alive_2026),
        rivals_alive=len(alive_2026 & alive),
        launches=launches,
        stage_4_turn=stage_4,
        seconds=time.perf_counter() - started,
    )


def run_long(
    seeds: Sequence[int] = LONG_SEEDS,
    strategies: Sequence[str] = LONG_STRATEGIES,
    jobs: int = 1,
) -> list[LongRun]:
    plan = [(s, seed) for s in strategies for seed in seeds]
    if jobs <= 1:
        return [play_long(j) for j in plan]
    with ProcessPoolExecutor(jobs) as pool:
        return list(pool.map(play_long, plan))


def long_rows(runs: Sequence[LongRun], categories: Sequence[str]) -> list[Row]:
    rows: list[Row] = []
    years = (LONG_TURNS - DEMAND_FROM) / 12
    for s in sorted({r.strategy for r in runs}, key=LONG_STRATEGIES.index):
        mine = [r for r in runs if r.strategy == s and r.ended_turn is None]
        ended = sum(1 for r in runs if r.strategy == s and r.ended_turn is not None)
        if not mine:
            rows.append(Row("V5", f"{s}: runs alive to 2039", f"0 ({ended} ended)", "-", False))
            continue
        eras = median(r.eras for r in mine)
        rows.append(
            Row(
                "V5",
                f"{s}: era arrivals 2026-2039 (median)",
                f"{eras:g}",
                f">= {V5_ERAS}",
                eras >= V5_ERAS,
            )
        )
        growth = median(
            (r.demand_to / r.demand_from) ** (1 / years) - 1 for r in mine if r.demand_from > 0
        )
        rows.append(
            Row(
                "V5",
                f"{s}: total demand growth in the 2030s",
                f"{growth:.1%} a year",
                f">= {V5_GROWTH:.0%}",
                growth >= V5_GROWTH,
            )
        )
        share = median(r.rivals_alive / r.rivals_2026 for r in mine if r.rivals_2026)
        rows.append(
            Row(
                "V5",
                f"{s}: 2026 rivals alive in 2039 (median)",
                f"{share:.0%}",
                f">= {V5_RIVALS:.0%}",
                share >= V5_RIVALS,
            )
        )
        missing = sorted(
            {
                f"{c} {d}"
                for r in mine
                for c in categories
                for _, d in DECADES
                if r.launches.get((c, d), 0) == 0
            }
        )
        rows.append(
            Row(
                "V5",
                f"{s}: categories with no rival launch in a decade",
                ", ".join(missing) or "none",
                "none",
                not missing,
            )
        )
        if ended:
            rows.append(Row("V5", f"{s}: runs that ended before 2039", str(ended), "printed", None))
        if s == BASE:
            listed = sum(1 for r in runs if r.strategy == s and r.stage_4_turn is not None)
            need = V5_STAGE_4 * len(LONG_SEEDS) / 10
            rows.append(
                Row(
                    "V5",
                    f"{s}: reaches stage 4 by 2039",
                    f"{listed}/{len([r for r in runs if r.strategy == s])}",
                    f">= {need:g}",
                    listed >= need,
                )
            )
    return rows


def long_table(runs: Sequence[LongRun]) -> str:
    lines = []
    for r in sorted(runs, key=lambda r: (r.strategy, r.seed)):
        lines.append(
            f"{r.strategy:15s} seed {r.seed:2d} | ended {r.ended_turn} | eras {r.eras} | demand "
            f"x{r.demand_to / r.demand_from if r.demand_from else 0:.2f} since 2030 | rivals "
            f"{r.rivals_alive}/{r.rivals_2026} | stage 4 at {r.stage_4_turn} | {r.seconds:.0f}s"
        )
    return "\n".join(lines)
