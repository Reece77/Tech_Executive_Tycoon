"""M57's v6 strategy targets (docs/tasks/M57-v6-balance-and-polish.md, sub-task 4), printed by
tools/v6_targets.py and checked weekly (tests/balance/test_v6_balance.py, .github/workflows/
weekly.yml). True values are read here only to report what each script's business did; the
scripts themselves read what a player sees.

Each v6 strategy (tst.balance.strategies_v6) and every founder-played strategy of v5's field
(tst.balance.v5.FIELD) is played for 30 years (January 2010 to December 2039) on seeds 1-20, and
each run's company score (30.1, tst.sim.score) read from its December snapshots: year 1 is
December 2010's, year 30 December 2039's. A run that fails before December 2039 scores 0 there.

- **V6.T1, viable:** each v6 strategy's median score growth, year 30's score less year 1's (in
  points: a difference, since a year-1 score can be small), is positive.
- **V6.T2, not dominant:** no v6 strategy's median year-30 score is more than V2's dominance cap
  (`V2_BAND[1]`, 1.4x) the field's median: the median of the field strategies' medians (v5's
  field and the v6 strategies, each strategy counted once whatever its seeds).
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
from tst.balance.strategies_v6 import V6
from tst.balance.v2 import V2_BAND
from tst.balance.v3 import LONG_TURNS, loaded
from tst.balance.v5 import ALL as V5_ALL
from tst.balance.v5 import FIELD as V5_FIELD
from tst.sim.calendar import ym_to_turn

SEEDS: Final = tuple(range(1, 21))
ALL: Final = {**V5_ALL, **V6}
FIELD: Final = (*V5_FIELD, *V6)  # T2's field
PLAYED: Final = tuple(dict.fromkeys(FIELD))
YEAR_1: Final = ym_to_turn(2010, 12)  # the first December snapshot
YEAR_30: Final = ym_to_turn(2039, 12)
DOMINANCE_CAP: Final = V2_BAND[1]  # 1.4x the field's median (T2)
CAMPAIGN_END: Final = "campaign_end"  # the game state a full 30-year run ends in


@dataclass(frozen=True, slots=True)
class V6Run:
    strategy: str
    seed: int
    score_1: int  # company score, December 2010
    score_30: int  # December 2039 (0 for a failed run)
    revenue_year: int  # the group's last 12 months, cents
    rungs: dict[str, int]
    ops: dict[str, int] = field(default_factory=dict)  # what the v6 business did (ops())
    seconds: float = 0.0
    ended_turn: int | None = None

    @property
    def growth(self) -> int:
        return self.score_30 - self.score_1


def score_at(game: Game, turn: int) -> int:
    """The player's company score snapshot of `turn`; 0 when none, and at year 30 for a game
    that failed (bankrupt, the founder removed) rather than reaching the campaign's end."""
    if turn == YEAR_30 and game.state.ended and game.state.save_meta.game_state != CAMPAIGN_END:
        return 0
    s = next((x for x in game.state.scores if x.company_id == PLAYER and x.turn == turn), None)
    return 0 if s is None else s.score


def ops(game: Game) -> dict[str, int]:
    """What each v6 business did: licences won and sites built, the bank's charter, titles
    released, and the mobile, fixed and banking lines' customers at the end."""
    state = game.state
    b = game.loaded.balance
    sites = sum(
        f.capacity
        for f in state.facilities
        if f.company_id == PLAYER and f.kind == b.telecom.tower_kind and f.status != "closed"
    )
    fibre = sum(
        f.capacity
        for f in state.facilities
        if f.company_id == PLAYER and f.kind == b.telecom.fibre_kind and f.status != "closed"
    )
    customers: dict[str, int] = {}
    for p in state.company_products(PLAYER):
        if p.category in (b.telecom.mobile, b.telecom.fixed, b.finserv.banking_category):
            n = sum(s.customers for s in state.segments_of(p.id))
            n += sum(s.customers for s in state.regional_segments_of(p.id))
            customers[p.category] = customers.get(p.category, 0) + round(n)
    chartered = any(x.company_id == PLAYER and x.status == "chartered" for x in state.finserv.banks)
    partner = any(x.company_id == PLAYER and x.status == "partner" for x in state.finserv.banks)
    mine = [t for t in state.media.titles if t.company_id == PLAYER]
    return {
        "licences": sum(1 for x in state.telecom.licences if x.company_id == PLAYER),
        "sites": sites,
        "fibre_k_homes": fibre,
        "mobile_customers": customers.get(b.telecom.mobile, 0),
        "fixed_customers": customers.get(b.telecom.fixed, 0),
        "bank_partner": int(partner),
        "bank_chartered": int(chartered),
        "bank_accounts": customers.get(b.finserv.banking_category, 0),
        "titles": len(mine),
        "titles_released": sum(1 for t in mine if t.stage == "released"),
    }


def play(job: tuple[str, int]) -> V6Run:
    """One strategy for 30 years on one seed."""
    strategy, seed = job
    started = time.perf_counter()
    game = start_game(loaded(), seed, SCENARIO)
    script = ALL[strategy]
    while game.state.turn < LONG_TURNS and not game.state.ended:
        script(game)
        game.turn()
    last = max(game.group_pnl) if game.group_pnl else 0
    year = [game.group_pnl[t] for t in range(last - 11, last + 1) if t in game.group_pnl]
    return V6Run(
        strategy=strategy,
        seed=seed,
        score_1=score_at(game, YEAR_1),
        score_30=score_at(game, YEAR_30),
        revenue_year=sum(r for r, _ in year),
        rungs={k.removeprefix("rung:"): v for k, v in game.notes.items() if k.startswith("rung:")},
        ops=ops(game),
        seconds=time.perf_counter() - started,
        ended_turn=game.state.save_meta.ended_turn,
    )


def run_all(strategies: Sequence[str], seeds: Sequence[int], jobs: int = 1) -> list[V6Run]:
    plan = [(s, seed) for s in strategies for seed in seeds]
    if jobs <= 1:
        return [play(j) for j in plan]
    with ProcessPoolExecutor(jobs) as pool:
        return list(pool.map(play, plan))


# --- Saving runs (shards) -----------------------------------------------------------------------


def save(runs: Sequence[V6Run], path: Path) -> None:
    path.write_text(json.dumps([asdict(r) for r in runs], indent=0) + "\n", encoding="utf-8")


def load(path: Path) -> list[V6Run]:
    return [V6Run(**raw) for raw in json.loads(path.read_text(encoding="utf-8"))]


# --- Rows ---------------------------------------------------------------------------------------


def _of(runs: Sequence[V6Run], strategy: str) -> list[V6Run]:
    return [r for r in runs if r.strategy == strategy]


def _median(xs: Sequence[float]) -> float | None:
    return st.median(xs) if xs else None


def field_median(runs: Sequence[V6Run]) -> float | None:
    """T2's field median: the median of each field strategy's median year-30 score."""
    medians = [m for s in FIELD if (m := _median([r.score_30 for r in _of(runs, s)])) is not None]
    return _median(medians)


def t1_rows(runs: Sequence[V6Run]) -> list[Row]:
    rows = []
    for name in V6:
        mine = _of(runs, name)
        g = _median([float(r.growth) for r in mine])
        y1 = _median([float(r.score_1) for r in mine])
        y30 = _median([float(r.score_30) for r in mine])
        rows.append(
            Row(
                f"V6.T1.{name}",
                f"{name} company score growth, December 2010 to 2039 (median; year 1, year 30)",
                "-" if g is None else f"{g:+.0f} ({y1:.0f}, {y30:.0f})",
                "> 0",
                None if g is None else g > 0,
                score=None if g is None else -g,
            )
        )
    return rows


def t2_rows(runs: Sequence[V6Run]) -> list[Row]:
    fm = field_median(runs)
    complete = all(_of(runs, s) for s in FIELD)
    rows = []
    for name in V6:
        m = _median([float(r.score_30) for r in _of(runs, name)])
        ratio = m / fm if m is not None and fm else None
        rows.append(
            Row(
                f"V6.T2.{name}",
                f"{name} year-30 company score / the field's median (median; field)",
                "-" if ratio is None else f"{ratio:.2f}x ({m:.0f} / {fm:.0f})",
                f"<= {DOMINANCE_CAP:.2f}x",
                None if ratio is None or not complete else ratio <= DOMINANCE_CAP,
                score=ratio,
            )
        )
    return rows


def rows(runs: Sequence[V6Run]) -> list[Row]:
    return [*t1_rows(runs), *t2_rows(runs)]


def strategy_table(runs: Sequence[V6Run]) -> str:
    """Each played strategy's medians, the v6 ones alongside v5's field."""
    lines = ["strategy            runs  year 1  year 30  growth  failed  year $M"]
    for name in PLAYED:
        mine = _of(runs, name)
        if not mine:
            continue
        y1 = _median([float(r.score_1) for r in mine]) or 0.0
        y30 = _median([float(r.score_30) for r in mine]) or 0.0
        g = _median([float(r.growth) for r in mine]) or 0.0
        rev = _median([float(r.revenue_year) for r in mine]) or 0.0
        failed = sum(1 for r in mine if r.ended_turn is not None and r.ended_turn < YEAR_30)
        mark = "*" if name in V6 else " "
        lines.append(
            f"{name:18}{mark} {len(mine):4} {y1:7.0f} {y30:8.0f} {g:+7.0f} {failed:7} "
            f"{rev / 1e8:8,.0f}"
        )
    return "\n".join(lines)


def run_table(runs: Sequence[V6Run]) -> str:
    keys = sorted({k for r in runs for k in r.ops})
    head = "strategy            seed  y1  y30  year $M      s  " + "  ".join(keys)
    lines = [head]
    for r in sorted(runs, key=lambda r: (r.strategy, r.seed)):
        cells = "  ".join(f"{r.ops.get(k, 0):>{len(k)}}" for k in keys)
        lines.append(
            f"{r.strategy:19} {r.seed:4} {r.score_1:3} {r.score_30:4} "
            f"{r.revenue_year / 1e8:8,.0f} {r.seconds:6.0f}  {cells}"
        )
    return "\n".join(lines)
