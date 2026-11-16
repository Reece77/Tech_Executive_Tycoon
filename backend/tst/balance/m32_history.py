"""docs/formulas.md 46.8 target 1 (M32): history holds. Two scripted strategies that build every
metered facility kind before 2026 (full_integrator: mines, a converter, a wafer plant and a fab;
integrator: its own data centres) are played to December 2025, and each year's power cost of
each kind is summed, with every ledger entry hashed by year. `tests/fixtures/m32_history.json`
holds main's from before M32 (`tools/m32_targets.py --write-history` on a checkout of main), and
the guard compares: each kind's yearly power cost within 1% (46.8: the median over 10 seeds), and
the books identical.

This module reads only records that main had before M32 (fab and refinery months' power cents, a
data centre's operating cost at its region's index), so the same code records the fixture on
main. Mines' power has no record on main; their cash costs are in the books hash.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from functools import cache
from pathlib import Path
from typing import Final

from tst.balance.game import Game, start_game
from tst.balance.strategies_v2 import STRATEGIES as V2
from tst.balance.strategies_v3 import V3
from tst.loader import LoadedData, load_all
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.commodities import power

SEEDS: Final = tuple(range(1, 11))
STRATEGIES: Final = ("full_integrator", "integrator")
DATA: Final = Path(__file__).resolve().parents[2] / "data"
HISTORY_FILE: Final = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "m32_history.json"
)
FIRST_YEAR: Final = 2010
LAST_HISTORY_TURN: Final = 191  # December 2025
TOLERANCE: Final = 0.01  # 46.8 target 1: within 1%
KINDS: Final = ("data_centre", "fab", "refinery")

type Run = dict[str, dict[str, object]]  # year -> {kind: cents, "books": sha256}


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


def _strategy(name: str) -> object:
    return {**V2, **V3}[name]


def _month_power(game: Game) -> dict[str, int]:
    """The month's power cost by kind, from records main had before M32."""
    state = game.state
    b = game.loaded.balance
    turn = state.turn - 1  # the month just played
    out = dict.fromkeys(KINDS, 0)
    for f in state.facilities:
        if f.kind in b.power.paid_by and f.live_capacity(turn) > 0:
            kind = b.facility.kinds[f.kind]
            base = f.live_capacity(turn) * kind.opex_per_unit_cents
            out["data_centre"] += round(power.opex_cents(base, _dc_mult(game, f.kind, f.region)))
    for fab in state.fabs:
        if fab.month is not None and fab.month.turn == turn:
            out["fab"] += fab.month.power_cents
    for ref in state.refineries:
        if ref.month is not None and ref.month.turn == turn:
            out["refinery"] += ref.month.power_cents
    return out


def _dc_mult(game: Game, kind: str, region: str) -> float:
    b, d = game.loaded.balance, game.loaded.game_data
    return power.kind_index(game.state, kind, region, b, d)


def history_run(key: tuple[str, int]) -> Run:
    """One strategy's yearly power costs and books hash to December 2025."""
    name, seed = key
    game = start_game(loaded(), seed)
    step = _strategy(name)
    years: dict[int, dict[str, int]] = {}
    books: dict[int, hashlib._Hash] = {}
    while game.state.turn <= LAST_HISTORY_TURN and not game.state.ended:
        turn = game.state.turn
        step(game)  # type: ignore[operator]
        game.turn()
        assert game.last_result is not None
        year = FIRST_YEAR + turn // MONTHS_PER_YEAR
        totals = years.setdefault(year, dict.fromkeys(KINDS, 0))
        for k, v in _month_power(game).items():
            totals[k] += v
        h = books.setdefault(year, hashlib.sha256())
        for e in game.last_result.ledger_entries:
            line = f"{e.company_id}|{e.memo}|" + ",".join(
                f"{x.account}:{x.amount}" for x in e.lines
            )
            h.update(line.encode())
            h.update(b"\n")
    return {str(y): {**years[y], "books": books[y].hexdigest()} for y in sorted(years)}


def history_all(
    strategies: Sequence[str] = STRATEGIES, seeds: Sequence[int] = SEEDS, workers: int = 1
) -> dict[str, Run]:
    keys = [(s, n) for s in strategies for n in seeds]
    if workers <= 1:
        runs = [history_run(k) for k in keys]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            runs = list(pool.map(history_run, keys))
    return {f"{s}/{n}": r for (s, n), r in zip(keys, runs, strict=True)}


def recorded_history() -> dict[str, Run]:
    out: dict[str, Run] = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return out


def write_history(runs: dict[str, Run]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(runs, indent=1, sort_keys=True) + "\n"
    HISTORY_FILE.write_text(text, encoding="utf-8", newline="\n")


def _ratio(got: object, want: object) -> float:
    g, w = float(got), float(want)  # type: ignore[arg-type]
    if w == 0:
        return 0.0 if g == 0 else 1.0
    return abs(g - w) / abs(w)


def cost_diffs(got: dict[str, Run], want: dict[str, Run]) -> list[str]:
    """Every (strategy, year, kind) whose median power cost over the seeds is more than 1% from
    main's: empty when target 1 holds."""
    out: list[str] = []
    for strategy in sorted({k.split("/")[0] for k in got}):
        runs = [(k, r) for k, r in got.items() if k.startswith(f"{strategy}/")]
        years = sorted({y for _, r in runs for y in r})
        for year in years:
            for kind in KINDS:
                g = [float(r[year][kind]) for _, r in runs if year in r]  # type: ignore[arg-type]
                w = [
                    float(want[k][year][kind])  # type: ignore[arg-type]
                    for k, _ in runs
                    if year in want.get(k, {})
                ]
                if g and w and _ratio(statistics.median(g), statistics.median(w)) > TOLERANCE:
                    out.append(f"{strategy} {year} {kind}")
    return out


def book_diffs(got: dict[str, Run], want: dict[str, Run]) -> list[str]:
    """Every (run, year) whose books differ from main's."""
    return [
        f"{k} {y}"
        for k, r in got.items()
        for y, row in r.items()
        if want.get(k, {}).get(y, {}).get("books") != row["books"]
    ]
