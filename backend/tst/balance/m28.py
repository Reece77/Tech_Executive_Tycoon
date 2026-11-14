"""M28's balance targets (docs/formulas.md 41.8), printed by tools/m28_targets.py.

Target 1, history holds, is a fingerprint: a do-nothing game played to December 2025 hashes,
year by year, every commodity, power and component month, the foundry market's prices and
capacities, the rival miners' capacities, every log item (the dated events and the news) and
every ledger entry of every company. `tests/fixtures/m28_history.json` holds main's
fingerprint from before M28 (`tools/m28_targets.py --write-history` on a checkout of main);
the guard compares the branch's against it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from functools import cache
from pathlib import Path
from typing import Final

from tst.balance.game import Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.fabs import market
from tst.sim.fabs import nodes as nd
from tst.sim.mining.risk import rival_capacity
from tst.sim.rng import RngFactory
from tst.sim.turn import TurnResult

SEEDS: Final = tuple(range(1, 11))
DATA: Final = Path(__file__).resolve().parents[2] / "data"
HISTORY_FILE: Final = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "m28_history.json"
)
FIRST_YEAR: Final = 2010
LAST_HISTORY_TURN: Final = 191  # December 2025
SERIES: Final = ("prices", "wafer", "capacity", "events", "books")

type Fingerprint = dict[str, dict[str, str]]  # series -> year -> sha256


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


def _f(x: float) -> str:
    """A float to 10 significant figures: libm's last bits differ between platforms (the
    fixture is recorded on Windows; CI runs Linux), the history's numbers do not."""
    return f"{x:.10g}"


def _params(params: tuple[tuple[str, object], ...]) -> str:
    return "|".join(f"{k}={_f(v) if isinstance(v, float) else v}" for k, v in params)


def _month_lines(game: Game, result: TurnResult, turn: int) -> dict[str, list[str]]:
    state = game.state  # after the month: the month just played is `turn`
    b, d = game.loaded.balance, game.loaded.game_data
    out: dict[str, list[str]] = {s: [] for s in SERIES}
    out["prices"] = [
        f"{g.good}|{g.turn}|{_f(g.index)}|{_f(g.allocation)}|{g.shock_turn}|{g.shock_kind}"
        for g in state.supply
    ]
    if d.nodes is not None:
        tl = market.timeline(state, b, d)
        slots = market.player_slots(state)
        out["wafer"] = [
            _f(nd.price_factor(tl, d.nodes, turn, b.fab, slots)),
            _f(nd.allocation_factor(tl, d.nodes, turn, b.fab, slots)),
            *(f"{n}|{tl.behind(n, turn)}" for n in tl.keys if tl.arrival[n] <= turn),
            *(f"{f.key}|{tl.reached(f.key, turn)}" for f in d.nodes.foundries),
        ]
        out["capacity"] = [
            f"{f.key}|{_f(nd.capacity(tl, f, turn, b.fab))}" for f in d.nodes.foundries
        ]
    if turn % MONTHS_PER_YEAR == MONTHS_PER_YEAR - 1:  # December: the rival miners
        rng = RngFactory(state.save_meta.master_seed)
        out["capacity"] += [
            f"{r.supplier}|{r.commodity}|{_f(r.capacity_share)}|{_f(r.output_share)}"
            for r in rival_capacity(rng, turn, state, b, d)
        ]
    out["events"] = [
        f"{i.turn}|{i.company_id}|{i.kind}|{i.template}|{i.message}|{_params(i.params)}"
        for i in result.log_items
    ] + [f"{r.template_id}|{r.company_id}" for r in result.event_requests]
    out["books"] = [
        f"{e.company_id}|{e.memo}|" + ",".join(f"{x.account}:{x.amount}" for x in e.lines)
        for e in result.ledger_entries
    ]
    return out


def history_fingerprint(seed: int, last_turn: int = LAST_HISTORY_TURN) -> Fingerprint:
    """41.8 target 1: a do-nothing game's series to `last_turn`, hashed by year."""
    game = start_game(loaded(), seed)
    hashes: dict[str, dict[int, hashlib._Hash]] = {s: {} for s in SERIES}
    while game.state.turn <= last_turn:
        turn = game.state.turn
        game.turn()
        assert game.last_result is not None
        year = FIRST_YEAR + turn // MONTHS_PER_YEAR
        for series, lines in _month_lines(game, game.last_result, turn).items():
            h = hashes[series].setdefault(year, hashlib.sha256())
            for line in lines:
                h.update(line.encode())
                h.update(b"\n")
    return {s: {str(y): h.hexdigest() for y, h in sorted(ys.items())} for s, ys in hashes.items()}


def history_all(seeds: Sequence[int], workers: int = 1) -> dict[str, Fingerprint]:
    if workers <= 1:
        return {str(s): history_fingerprint(s) for s in seeds}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return {str(s): f for s, f in zip(seeds, pool.map(history_fingerprint, seeds), strict=True)}


def recorded_history() -> dict[str, Fingerprint]:
    out: dict[str, Fingerprint] = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return out


def write_history(fingerprints: dict[str, Fingerprint]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(fingerprints, indent=1, sort_keys=True) + "\n"
    HISTORY_FILE.write_text(text, encoding="utf-8", newline="\n")


def history_diffs(got: dict[str, Fingerprint], want: dict[str, Fingerprint]) -> list[str]:
    """Every (seed, series, year) whose hash differs from main's: empty when history holds."""
    out = []
    for seed, series in got.items():
        for name, years in series.items():
            for year, h in years.items():
                if want.get(seed, {}).get(name, {}).get(year) != h:
                    out.append(f"seed {seed} {name} {year}")
    return out


def run(seeds: Sequence[int] = SEEDS, workers: int = 1) -> object:
    """Targets 2-6 (tst.balance.m28_world)."""
    from tst.balance import m28_world

    return m28_world.run(seeds, workers)


def report(results: object) -> str:
    from tst.balance import m28_world

    assert isinstance(results, m28_world.Results)
    return m28_world.report(results)
