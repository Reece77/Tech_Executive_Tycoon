"""M45's long state-cache check (docs/tasks/M45-performance-at-scale-part-two.md sub-task 1).

M45 may change any engine, database or API code to make it faster, but never a result. M30's
state cache (tst.balance.m30) covers January 2010 to December 2039; this one covers the dynasty
years M37 added. It plays M37's 2040-2069 runs (`tst.balance.m37.dynasty_run`'s game: the
full_integrator script, dynasty mode on, M36's family with two children) on seeds 1-3 for 720
months (January 2010 to December 2069) in memory, and digests the full state and the ledger
balances after every month with M30's canonical digest. `tests/fixtures/m45_dynasty_hashes.json`
holds the digests recorded before any M45 change (`tools/m45_state_hashes.py --write`); the
weekly test compares a run with them month by month and names the first month that differs.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Final

from tst.balance import m30, m37
from tst.sim.dynasty.mode import continue_dynasty
from tst.sim.modes.models import GameMode

SEEDS: Final = (1, 2, 3)
TURNS: Final = m37.END  # 720: January 2010 to December 2069
HASH_FILE: Final = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "m45_dynasty_hashes.json"
)

type Hashes = dict[str, list[str]]  # "full_integrator/seed/dynasty" -> one digest per month


# M51: GameMode gained `challenges` (empty in this game) after the fixture was recorded; the
# digest leaves it out, as M37's does for fields added after its fixture (m30.Digester)
# M52: and `scenario_sha256` (None) and `growth_delta` (empty), likewise
SKIP: Final[Mapping[type, frozenset[str]]] = {
    GameMode: frozenset({"challenges", "scenario_sha256", "growth_delta"})
}


def key(seed: int) -> str:
    return f"{m37.STRATEGY}/{seed}/dynasty"


def run_hashes(seed: int, turns: int = TURNS) -> list[str]:
    """M37's dynasty game on one seed: a digest after every month played."""
    game = m37._family_game(seed)
    game.state = continue_dynasty(game.state, m30.loaded().balance)
    script = m30.strategy(m37.STRATEGY)
    digester = m30.Digester(SKIP)
    out: list[str] = []
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        out.append(m30.month_digest(digester, game))
    return out


def all_hashes(workers: int = 1, turns: int = TURNS, seeds: tuple[int, ...] = SEEDS) -> Hashes:
    if workers <= 1:
        return {key(s): run_hashes(s, turns) for s in seeds}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        runs = pool.map(run_hashes, seeds, [turns] * len(seeds))
        return {key(s): r for s, r in zip(seeds, runs, strict=True)}


def recorded() -> Hashes:
    out: Hashes = json.loads(HASH_FILE.read_text(encoding="utf-8"))
    return out


def write(hashes: Hashes) -> None:
    HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(hashes, indent=0, sort_keys=True) + "\n"
    HASH_FILE.write_text(text, encoding="utf-8", newline="\n")
