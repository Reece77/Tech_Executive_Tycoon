"""M43's v5 balance targets (docs/tasks/M43-v5-balance-and-conglomerate-view.md), printed by
tools/v5_targets.py and checked weekly (tests/balance/test_v5_balance.py, .github/workflows/
weekly.yml). True values are read here; this is a tool.

Every strategy since v1 is played for 30 years (January 2010 to December 2039) on the same
seeds as M23b's and M35b's, and the v5 strategies with a family to December 2069 in dynasty mode:

- **T1, viable, not dominant:** each v5 strategy's median year-30 ARR (12 x the group's last
  month, as M23b and M35b) is 0.9-1.4x its natural comparison's (`PAIRS`, named before
  measuring: the brief's Decisions made). The trailing year's revenue ratio prints beside it.
- **T2, no strategy always wins:** no strategy has the highest founder value at December 2039 on
  more than 4 of 10 seeds among all the founder-played strategies (M35b's field and v5's).
- **The dynasty runs** print each v5 strategy's 2069 ARR and family value beside its 2039
  reading (52's targets are M37's own).

T3 (each system's targets on the combined code), T4 (the known misses), T5 (compliance) and T6
(the economy) are the earlier tools' runs, read from their own jobs.
"""

from __future__ import annotations

import json
import statistics as st
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from tst.balance.game import Game, start_game
from tst.balance.report import SCENARIO, Row
from tst.balance.strategies_v5 import V5, V5_ARMS
from tst.balance.v3 import LONG_TURNS, loaded
from tst.balance.v4 import ALL as V4_ALL
from tst.balance.v4 import FIELD as V4_FIELD

SEEDS: Final = tuple(range(1, 11))
ALL: Final = {**V4_ALL, **V5, **V5_ARMS}
# T1's natural comparisons, named before measuring (the brief's Decisions made): the strategy
# each v5 one grows out of, played for the same 30 years
PAIRS: Final = (
    ("ev_integrator", "full_integrator"),
    ("life_sciences", "devices_regions"),
    ("robotics_first", "devices_regions"),
    ("cloud_first", "cloud_first_grid"),
    ("space_and_defence", "devices_regions"),
)
FIELD: Final = (*V4_FIELD, *V5)  # T2's field
PLAYED: Final = tuple(dict.fromkeys((*FIELD, *(b for _, b in PAIRS))))
ARR_RATIO: Final = (0.9, 1.4)  # T1
MAX_WINS: Final = 4  # T2
DYNASTY_END: Final = 720  # the turn after December 2069


@dataclass(frozen=True, slots=True)
class V5Run:
    strategy: str
    seed: int
    value: int  # founder value at the end (the family's in a dynasty run), cents
    revenue_month: int  # the group's last month, cents
    revenue_year: int  # the group's last 12 months, cents
    rungs: dict[str, int]
    seconds: float = 0.0
    ended_turn: int | None = None
    dynasty: bool = False

    @property
    def arr(self) -> int:
        return 12 * self.revenue_month


def family_value(game: Game) -> int:
    """A dynasty run's value at the end: the family's stake (45.6: its people and the trust) at
    the top of the group x V_base. The founder's own stake is gone after a succession, so
    `Game.founder_value` reads 0 there."""
    from tst.balance.game import PLAYER
    from tst.sim.family.rules import family_bp
    from tst.sim.finance.fundraising import base_value
    from tst.sim.state import ultimate_owner

    state = game.state
    if state.ended:
        return 0
    value = base_value(state, PLAYER, game.loaded.balance, game.loaded.game_data)
    return value * family_bp(state, ultimate_owner(state, PLAYER)) // 10_000


def _result(strategy: str, seed: int, game: Game, started: float, dynasty: bool) -> V5Run:
    last = max(game.group_pnl) if game.group_pnl else 0
    year = [game.group_pnl[t] for t in range(last - 11, last + 1) if t in game.group_pnl]
    if dynasty:
        value = family_value(game)
    else:
        value = game.founder_value.get(max(game.founder_value), 0) if game.founder_value else 0
    return V5Run(
        strategy=strategy,
        seed=seed,
        value=value,
        revenue_month=game.group_pnl.get(last, (0, 0))[0],
        revenue_year=sum(r for r, _ in year),
        rungs={k.removeprefix("rung:"): v for k, v in game.notes.items() if k.startswith("rung:")},
        seconds=time.perf_counter() - started,
        ended_turn=game.state.save_meta.ended_turn,
        dynasty=dynasty,
    )


def _play(game: Game, script: Callable[[Game], None], turns: int) -> None:
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()


def play(job: tuple[str, int]) -> V5Run:
    """One strategy for 30 years on one seed."""
    strategy, seed = job
    started = time.perf_counter()
    game = start_game(loaded(), seed, SCENARIO)
    _play(game, ALL[strategy], LONG_TURNS)
    return _result(strategy, seed, game, started, dynasty=False)


def play_dynasty(job: tuple[str, int]) -> V5Run:
    """One v5 strategy with M37's family in dynasty mode to December 2069."""
    from tst.balance import m37
    from tst.sim.dynasty.mode import continue_dynasty

    strategy, seed = job
    started = time.perf_counter()
    game = m37._family_game(seed)
    game.state = continue_dynasty(game.state, game.loaded.balance)
    _play(game, ALL[strategy], DYNASTY_END)
    return _result(strategy, seed, game, started, dynasty=True)


def run_all(
    strategies: Sequence[str], seeds: Sequence[int], jobs: int = 1, dynasty: bool = False
) -> list[V5Run]:
    plan = [(s, seed) for s in strategies for seed in seeds]
    fn = play_dynasty if dynasty else play
    if jobs <= 1:
        return [fn(j) for j in plan]
    with ProcessPoolExecutor(jobs) as pool:
        return list(pool.map(fn, plan))


# --- Saving runs (the weekly's shards) --------------------------------------------------------


def save(runs: Sequence[V5Run], path: Path) -> None:
    path.write_text(json.dumps([asdict(r) for r in runs], indent=0) + "\n", encoding="utf-8")


def load(path: Path) -> list[V5Run]:
    return [V5Run(**raw) for raw in json.loads(path.read_text(encoding="utf-8"))]


# --- Rows -------------------------------------------------------------------------------------


def _of(runs: Sequence[V5Run], strategy: str, dynasty: bool = False) -> list[V5Run]:
    return [r for r in runs if r.strategy == strategy and r.dynasty == dynasty]


def _median(xs: Sequence[float]) -> float | None:
    return st.median(xs) if xs else None


def ratio(runs: Sequence[V5Run], top: str, base: str, year: bool = False) -> float | None:
    def m(name: str) -> float | None:
        return _median([float(r.revenue_year if year else r.arr) for r in _of(runs, name)])

    a, b = m(top), m(base)
    return a / b if a is not None and b else None


def t1_rows(runs: Sequence[V5Run]) -> list[Row]:
    rows = []
    for top, base in PAIRS:
        r = ratio(runs, top, base)
        y = ratio(runs, top, base, year=True)
        present = bool(_of(runs, top) and _of(runs, base))
        rows.append(
            Row(
                f"V5.T1.{top}",
                f"{top} ARR / {base}, December 2039 (median; trailing year)",
                "-" if r is None else f"{r:.2f}x ({'-' if y is None else f'{y:.2f}x'})",
                "0.90-1.40x",
                None if not present else (r is not None and ARR_RATIO[0] <= r <= ARR_RATIO[1]),
                score=None if r is None else abs(r - 1.15),
            )
        )
    return rows


def wins(runs: Sequence[V5Run]) -> dict[str, int]:
    out: dict[str, int] = {}
    for seed in sorted({r.seed for r in runs}):
        field_ = [r for r in runs if r.seed == seed and r.strategy in FIELD and not r.dynasty]
        if field_:
            best = max(field_, key=lambda r: (r.value, r.strategy))
            out[best.strategy] = out.get(best.strategy, 0) + 1
    return out


def t2_row(runs: Sequence[V5Run]) -> Row:
    w = wins(runs)
    top = max(w.values(), default=0)
    n = len({r.seed for r in runs if not r.dynasty})
    complete = all(_of(runs, s) for s in FIELD)
    return Row(
        "V5.T2",
        f"most wins by any strategy of {n} (December 2039 founder value)",
        f"{top} ({', '.join(f'{k} {v}' for k, v in sorted(w.items()))})",
        f"<= {MAX_WINS}",
        top <= MAX_WINS if complete else None,
        score=float(top),
    )


def dynasty_rows(runs: Sequence[V5Run]) -> list[Row]:
    rows = []
    for name in V5:
        long = _of(runs, name, dynasty=True)
        if not long:
            continue
        short = _of(runs, name)
        arr69 = _median([float(r.arr) for r in long])
        arr39 = _median([float(r.arr) for r in short])
        value = _median([float(r.value) for r in long])
        rows.append(
            Row(
                f"V5.dynasty.{name}",
                f"{name} with a family to December 2069: median ARR (2039's), family value",
                f"${(arr69 or 0) / 1e8:,.0f}M (${(arr39 or 0) / 1e8:,.0f}M), "
                f"${(value or 0) / 1e8:,.0f}M",
                "printed",
                None,
            )
        )
    return rows


def rows(runs: Sequence[V5Run]) -> list[Row]:
    return [*t1_rows(runs), t2_row(runs), *dynasty_rows(runs)]


def run_table(runs: Sequence[V5Run]) -> str:
    lines = ["strategy            seed dyn  value $M    ARR $M   year $M      s"]
    for r in sorted(runs, key=lambda r: (r.dynasty, r.strategy, r.seed)):
        lines.append(
            f"{r.strategy:19} {r.seed:4} {'y' if r.dynasty else '-':>3} {r.value / 1e8:9,.0f} "
            f"{r.arr / 1e8:9,.0f} {r.revenue_year / 1e8:9,.0f} {r.seconds:6.0f}"
        )
    return "\n".join(lines)


def rung_table(runs: Sequence[V5Run]) -> str:
    keys = sorted({k for r in runs for k in r.rungs})
    lines = ["strategy            seed  " + "  ".join(f"{k[:12]:>12}" for k in keys)]
    for r in sorted(runs, key=lambda r: (r.dynasty, r.strategy, r.seed)):
        cells = []
        for k in keys:
            t = r.rungs.get(k)
            cells.append(f"{'-' if t is None else f'{2010 + t // 12}-{t % 12 + 1:02d}':>12}")
        lines.append(f"{r.strategy:19} {r.seed:4}  " + "  ".join(cells))
    return "\n".join(lines)
