"""M37's balance runs (docs/formulas.md 52.5; docs/tasks/M37-dynasty-mode.md).

**Target 1, nothing moves before 2040.** `pre_2040_hashes` plays M30's nine state-cache runs
(tst.balance.m30) to December 2039 with dynasty mode off or on (on: switched at turn 0, as the
new-game setting does) and digests every month with the fields M37 added left out
(`GameState.dynasty`, `GameMode.length`) and a dynasty campaign's mode read as the standard
campaign's (None). Each month's digest must equal the one recorded before M37 (`m30_state_hashes
.json` as `main` had it): anything M37 changed before 2040 would show as the first month that
differs. After M37 merges the fixture is re-recorded with the new fields (CHANGELOG), and
`legacy` keeps this comparison: `tests/fixtures/m37_pre_2040_hashes.json`.

**Targets 2-5** play dynasty games to December 2069 (`dynasty_run`) and print their readings.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Final

from tst.balance import m30
from tst.balance.game import Game, start_game
from tst.balance.report import SCENARIO
from tst.sim.dynasty.mode import continue_dynasty
from tst.sim.modes.models import GameMode
from tst.sim.state import GameState

TURNS: Final = 360  # January 2010 to December 2039
LEGACY_FILE: Final = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "m37_pre_2040_hashes.json"
)
# the fields M37 added: left out, so a digest is what it was before M37
SKIP: Final[Mapping[type, frozenset[str]]] = {
    GameState: frozenset({"dynasty"}),
    GameMode: frozenset({"length"}),
}

type Hashes = dict[str, list[str]]


def legacy_view(state: GameState) -> GameState:
    """A dynasty campaign's state as a standard one's: its mode, made only of the setting,
    read as None (a standard campaign has no mode)."""
    mode = state.mode
    if mode is not None and mode == GameMode(kind="campaign", length="dynasty"):
        return replace(state, mode=None)
    return state


def _digest(digester: m30.Digester, game: Game) -> str:
    import hashlib

    state = digester.digest(legacy_view(game.state))
    balances = digester.digest(game.balances)
    digester.next_month()
    return hashlib.sha256(state + balances).hexdigest()[: m30.HEX]


def pre_2040_hashes(job: tuple[str, int, bool], turns: int = TURNS) -> list[str]:
    """One M30 run to December 2039, dynasty mode off or on, M37's fields left out."""
    name, seed, dynasty = job
    loaded = m30.loaded()
    game = start_game(loaded, seed, SCENARIO)
    if dynasty:
        game.state = continue_dynasty(game.state, loaded.balance)
    script = m30.strategy(name)
    digester = m30.Digester(SKIP)
    out: list[str] = []
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        out.append(_digest(digester, game))
    return out


def jobs(dynasty: Sequence[bool] = (False, True)) -> list[tuple[str, int, bool]]:
    return [(name, seed, d) for d in dynasty for name, seed in m30.jobs()]


def all_pre_2040(workers: int, dynasty: Sequence[bool] = (False, True)) -> dict[str, list[str]]:
    todo = jobs(dynasty)
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        runs = list(pool.map(pre_2040_hashes, todo))
    return {
        f"{m30.key(n, s)}/{'dynasty' if d else 'standard'}": r
        for (n, s, d), r in zip(todo, runs, strict=True)
    }


def legacy() -> Hashes:
    """The digests recorded before M37 (main's m30_state_hashes.json, kept by M37)."""
    out: Hashes = json.loads(LEGACY_FILE.read_text(encoding="utf-8"))
    return out


def compare(runs: Mapping[str, list[str]], want: Hashes) -> dict[str, str | None]:
    """run -> None if identical to the pre-M37 digests, else the first difference."""
    return {k: m30.first_difference(v, want[k.rsplit("/", 1)[0]]) for k, v in runs.items()}
