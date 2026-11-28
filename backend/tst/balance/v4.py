"""M35b's v4 balance targets (docs/tasks/M35b-v4-balance.md), printed by tools/v4_targets.py and
checked weekly (tests/balance/test_v4_balance.py, .github/workflows/weekly.yml). True values
are read here; this is a tool.

The four v4 scripts (tst.balance.strategies_v4) and their comparisons are played for 30 years
(January 2010 to December 2039) on the same seeds as M23b's v3 strategies:

- **T1, viable, not dominant:** each v4 strategy's median year-30 ARR (12 x the group's last
  month, as M23b) is 0.9-1.4x its natural comparison's: platform_owner against
  devices_regions, power_hyperscaler against cloud_steady (a steady cloud company without
  plants), litho_bet against full_integrator. compliant_platform's ratio to devices_regions
  prints for information. The trailing year's revenue ratio prints beside it (cloud revenue
  swings month to month).
- **T2, no strategy always wins:** no v4 strategy has the highest founder value at December 2039
  on more than 4 of 10 seeds, among M23b's seven compared strategies and the four v4 ones.
- **T3, regulation bites platforms:** platform_owner has a duty or a fine (6970) by December
  2034 on at least 7 of 10 seeds; compliant_platform's median fines to December 2039 are at
  least 30% below platform_owner's.
- **T4, power binds:** the capacity each cloud company ordered by December 2032 (every data
  centre it ordered to then: all serve its home market, North America, the data's most
  congested region) is all live at least 12 months earlier for power_hyperscaler than for
  cloud_steady (the median of the seeds' paired gaps; a company's capacity not all live by
  December 2039 counts as 2040). Its data centres in congested regions (a queue median above
  CONGESTED_MONTHS when ordered) print beside it.

T5 (each system's own targets on the combined code) is M31-M34's tools and the v3 weekly;
T6 (the known misses) is reported from their runs.
"""

from __future__ import annotations

import json
import statistics as st
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.report import SCENARIO, Row
from tst.balance.strategies_v4 import V4, V4_ARMS
from tst.balance.v3 import ALL as V3_ALL
from tst.balance.v3 import COMPARED, DEVICES, INTEGRATOR, LONG_TURNS, loaded
from tst.sim.calendar import turn_to_ym, ym_to_turn
from tst.sim.ledger import FINES
from tst.sim.power import queues

SEEDS: Final = tuple(range(1, 11))
ALL: Final = {**V3_ALL, **V4, **V4_ARMS}
CLOUD: Final = "cloud_steady"
PAIRS: Final = (
    ("platform_owner", DEVICES),
    ("power_hyperscaler", CLOUD),
    ("litho_bet", INTEGRATOR),
)
INFO_PAIRS: Final = (("compliant_platform", DEVICES),)
FIELD: Final = (*COMPARED, *V4)  # T2's field
PLAYED: Final = tuple(dict.fromkeys((*FIELD, DEVICES, CLOUD)))
V4_ONLY: Final = (*V4, DEVICES, CLOUD, INTEGRATOR)  # the runs T1, T3 and T4 read
ARR_RATIO: Final = (0.9, 1.4)  # T1
MAX_WINS: Final = 4  # T2
DUTY_BY: Final = ym_to_turn(2034, 12)  # T3
DUTY_SEEDS: Final = 7  # T3: of 10
FINE_CUT: Final = 0.30  # T3: compliant_platform's fines at least this much lower
CAPACITY_BY: Final = ym_to_turn(2032, 12)  # T4
EARLIER: Final = 12  # T4: months
NEVER: Final = ym_to_turn(2040, 1)
CONGESTED_MONTHS: Final = 24.0  # a region is congested when its queue median passes this


@dataclass(frozen=True, slots=True)
class DataCentre:
    region: str
    ordered: int
    capacity: int
    live: int | None  # the first month it ran any capacity
    congested: bool  # its region's queue median above CONGESTED_MONTHS when ordered


@dataclass(frozen=True, slots=True)
class V4Run:
    strategy: str
    seed: int
    value: int  # founder value at December 2039, cents
    revenue_month: int  # the group's last month, cents
    revenue_year: int  # the group's last 12 months, cents
    rungs: dict[str, int]
    duties_2034: int  # the player's duties in force by December 2034
    fines_2034: int  # 6970 fines by December 2034, cents
    fines: int  # 6970 fines by December 2039, cents
    cases: tuple[str, ...]  # regulator/outcome of each of the player's cases
    centres: tuple[DataCentre, ...] = ()
    plants: int = 0
    seconds: float = 0.0
    ended_turn: int | None = None
    programmes: tuple[str, ...] = field(default=())  # stage/status/started

    @property
    def arr(self) -> int:
        return 12 * self.revenue_month


def _fines(game: Game) -> int:
    return game.balances.get((PLAYER, FINES), 0)


def _duties(game: Game) -> int:
    s = game.state
    return sum(1 for d in s.duties if d.company_id == PLAYER and d.from_turn <= s.turn)


def _track(game: Game, seen: dict[int, DataCentre]) -> None:
    """Each data centre's order, and the first month it runs."""
    d = game.loaded.game_data
    turn = game.state.turn
    for f in game.state.facilities:
        if f.company_id != PLAYER or not f.kind.startswith("data_centre"):
            continue
        dc = seen.get(f.id)
        if dc is None:
            median = queues.median_months(game.state, f.region, d) if d.power else 0.0
            dc = DataCentre(f.region, f.ordered_turn, f.capacity, None, median > CONGESTED_MONTHS)
        if dc.live is None and f.live_capacity(turn) > 0:
            dc = DataCentre(dc.region, dc.ordered, dc.capacity, turn, dc.congested)
        seen[f.id] = dc


def play(job: tuple[str, int]) -> V4Run:
    strategy, seed = job
    started = time.perf_counter()
    game = start_game(loaded(), seed, SCENARIO)
    script = ALL[strategy]
    seen: dict[int, DataCentre] = {}
    duties_2034 = fines_2034 = 0
    while game.state.turn < LONG_TURNS and not game.state.ended:
        script(game)
        game.turn()
        _track(game, seen)
        if game.state.turn - 1 == DUTY_BY:
            duties_2034, fines_2034 = _duties(game), _fines(game)
    if game.state.turn - 1 < DUTY_BY:  # ended early
        duties_2034, fines_2034 = _duties(game), _fines(game)
    s = game.state
    last = max(game.group_pnl) if game.group_pnl else 0
    year = [game.group_pnl[t] for t in range(last - 11, last + 1) if t in game.group_pnl]
    value = game.founder_value.get(max(game.founder_value), 0) if game.founder_value else 0
    return V4Run(
        strategy=strategy,
        seed=seed,
        value=value,
        revenue_month=game.group_pnl.get(last, (0, 0))[0],
        revenue_year=sum(r for r, _ in year),
        rungs={k.removeprefix("rung:"): v for k, v in game.notes.items() if k.startswith("rung:")},
        duties_2034=duties_2034,
        fines_2034=fines_2034,
        fines=_fines(game),
        cases=tuple(f"{c.regulator}/{c.outcome}" for c in s.reg_cases if c.company_id == PLAYER),
        centres=tuple(seen[k] for k in sorted(seen)),
        plants=sum(1 for p in s.plants if p.company_id == PLAYER),
        seconds=time.perf_counter() - started,
        ended_turn=s.save_meta.ended_turn,
        programmes=tuple(
            f"{p.stage}/{p.status}/{p.started_turn}" for p in s.programmes if p.company_id == PLAYER
        ),
    )


def run_all(strategies: Sequence[str], seeds: Sequence[int], jobs: int = 1) -> list[V4Run]:
    plan = [(s, seed) for s in strategies for seed in seeds]
    if jobs <= 1:
        return [play(j) for j in plan]
    with ProcessPoolExecutor(jobs) as pool:
        return list(pool.map(play, plan))


# --- Saving runs (the weekly's shards) --------------------------------------------------------


def save(runs: Sequence[V4Run], path: Path) -> None:
    path.write_text(json.dumps([asdict(r) for r in runs], indent=0) + "\n", encoding="utf-8")


def load(path: Path) -> list[V4Run]:
    out = []
    for raw in json.loads(path.read_text(encoding="utf-8")):
        raw["centres"] = tuple(DataCentre(**c) for c in raw["centres"])
        raw["cases"] = tuple(raw["cases"])
        raw["programmes"] = tuple(raw["programmes"])
        out.append(V4Run(**raw))
    return out


# --- Rows -------------------------------------------------------------------------------------


def _of(runs: Sequence[V4Run], strategy: str) -> list[V4Run]:
    return [r for r in runs if r.strategy == strategy]


def _median(xs: Sequence[float]) -> float | None:
    return st.median(xs) if xs else None


def _in(x: float | None, band: tuple[float, float]) -> bool:
    return x is not None and band[0] <= x <= band[1]


def ratio(runs: Sequence[V4Run], top: str, base: str, year: bool = False) -> float | None:
    def m(name: str) -> float | None:
        return _median([float(r.revenue_year if year else r.arr) for r in _of(runs, name)])

    a, b = m(top), m(base)
    return a / b if a is not None and b else None


def t1_rows(runs: Sequence[V4Run]) -> list[Row]:
    rows = []
    for i, (top, base) in enumerate((*PAIRS, *INFO_PAIRS)):
        r = ratio(runs, top, base)
        y = ratio(runs, top, base, year=True)
        printed = (top, base) in INFO_PAIRS
        present = bool(_of(runs, top) and _of(runs, base))
        rows.append(
            Row(
                f"V4.T1.{i + 1}",
                f"{top} ARR / {base}, December 2039 (median; trailing year)",
                "-" if r is None else f"{r:.2f}x ({'-' if y is None else f'{y:.2f}x'})",
                "printed" if printed else "0.90-1.40x",
                None if printed or not present else _in(r, ARR_RATIO),
                score=None if r is None else abs(r - 1.15),
            )
        )
    return rows


def wins(runs: Sequence[V4Run]) -> dict[str, int]:
    out: dict[str, int] = {}
    for seed in sorted({r.seed for r in runs}):
        field_ = [r for r in runs if r.seed == seed and r.strategy in FIELD]
        if field_:
            best = max(field_, key=lambda r: (r.value, r.strategy))
            out[best.strategy] = out.get(best.strategy, 0) + 1
    return out


def t2_row(runs: Sequence[V4Run]) -> Row:
    w = wins(runs)
    top = max((w.get(s, 0) for s in V4), default=0)
    n = len({r.seed for r in runs})
    complete = all(_of(runs, s) for s in FIELD)
    return Row(
        "V4.T2",
        f"most wins by a v4 strategy of {n} (December 2039 founder value)",
        f"{top} ({', '.join(f'{k} {v}' for k, v in sorted(w.items()))})",
        f"<= {MAX_WINS}",
        top <= MAX_WINS if complete else None,
        score=float(top),
    )


def t3_rows(runs: Sequence[V4Run]) -> list[Row]:
    owner = _of(runs, "platform_owner")
    hit = sum(1 for r in owner if r.duties_2034 > 0 or r.fines_2034 > 0)
    comp = _of(runs, "compliant_platform")
    f_owner = _median([float(r.fines) for r in owner])
    f_comp = _median([float(r.fines) for r in comp])
    cut = 1 - f_comp / f_owner if f_owner and f_comp is not None else None
    return [
        Row(
            "V4.T3.1",
            "platform_owner with a duty or fine by December 2034",
            f"{hit} of {len(owner)}",
            f">= {DUTY_SEEDS} of 10",
            hit >= DUTY_SEEDS if owner else None,
            score=float(len(owner) - hit),
        ),
        Row(
            "V4.T3.2",
            "compliant_platform's fines below platform_owner's, to 2039 (median)",
            "-"
            if cut is None
            else f"{cut:.0%} (${(f_comp or 0) / 1e8:,.0f}M vs ${(f_owner or 0) / 1e8:,.0f}M)",
            f">= {FINE_CUT:.0%}",
            None if not (owner and comp) else (cut is not None and cut >= FINE_CUT),
            score=None if cut is None else -cut,
        ),
    ]


def full_turn(r: V4Run) -> int:
    """The month the capacity `r` ordered by CAPACITY_BY is all live (NEVER if not by 2039)."""
    mine = [c for c in r.centres if c.ordered <= CAPACITY_BY]
    if not mine:
        return NEVER
    return max(c.live if c.live is not None else NEVER for c in mine)


def t4_row(runs: Sequence[V4Run]) -> Row:
    hyper = {r.seed: r for r in _of(runs, "power_hyperscaler")}
    steady = {r.seed: r for r in _of(runs, CLOUD)}
    gaps = [full_turn(steady[s]) - full_turn(hyper[s]) for s in sorted(hyper) if s in steady]
    gap = _median([float(g) for g in gaps])
    congested = sum(1 for r in hyper.values() for c in r.centres if c.congested)
    steady_congested = sum(1 for r in steady.values() for c in r.centres if c.congested)
    return Row(
        "V4.T4",
        "months earlier power_hyperscaler's 2032 capacity is all live (median paired gap)",
        "-"
        if gap is None
        else f"{gap:+.0f} ({', '.join(str(g) for g in gaps)}; congested DCs "
        f"{congested} vs {steady_congested})",
        f">= {EARLIER}",
        None if gap is None else gap >= EARLIER,
        score=None if gap is None else -gap,
    )


def rows(runs: Sequence[V4Run]) -> list[Row]:
    return [*t1_rows(runs), t2_row(runs), *t3_rows(runs), t4_row(runs)]


def run_table(runs: Sequence[V4Run]) -> str:
    lines = [
        "strategy           seed  value $M   ARR $M  year $M  duties34  fines $M  DCs plants  s"
    ]
    for r in sorted(runs, key=lambda r: (r.strategy, r.seed)):
        lines.append(
            f"{r.strategy:18} {r.seed:4} {r.value / 1e8:9,.0f} {r.arr / 1e8:8,.0f} "
            f"{r.revenue_year / 1e8:8,.0f} {r.duties_2034:9} {r.fines / 1e8:9,.0f} "
            f"{len(r.centres):4} {r.plants:6} {r.seconds:5.0f}"
        )
    return "\n".join(lines)


def rung_table(runs: Sequence[V4Run]) -> str:
    keys = sorted({k for r in runs for k in r.rungs})
    lines = ["strategy           seed  " + "  ".join(f"{k[:12]:>12}" for k in keys)]
    for r in sorted(runs, key=lambda r: (r.strategy, r.seed)):
        cells = []
        for k in keys:
            t = r.rungs.get(k)
            cells.append(f"{'-' if t is None else '{}-{:02d}'.format(*turn_to_ym(t)):>12}")
        lines.append(f"{r.strategy:18} {r.seed:4}  " + "  ".join(cells))
    return "\n".join(lines)
