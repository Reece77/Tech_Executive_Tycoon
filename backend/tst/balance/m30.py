"""M30's long state-cache check (docs/tasks/M30-performance-at-scale.md sub-task 1).

M30 may change any engine or API code to make it faster, but never a result. This check plays
three scripted strategies on seeds 1-3 for 360 months (January 2010 to December 2039) with the
engine in memory (tst.balance.game, as the balance runs do) and hashes the full state and the
ledger balances after every month. `tests/fixtures/m30_state_hashes.json` holds the hashes made
before any M30 change (`tools/m30_state_hashes.py --write`); the nightly test compares a run with
them month by month and names the first month that differs.

The digest is canonical: dataclasses by their compared fields in order, tuples and lists in
order (their order is the engine's iteration order, so it is part of the result), sets and
mappings sorted (their order is not). Floats are hashed exactly (`repr`), so the fixture is
recorded and checked on Linux (CI); libm's last bits can differ on another platform.

Immutable sub-objects are shared between one month's state and the next, so their digests are
memoised by identity for the month after (`Digester`): hashing a 2039 state then costs what
changed, not the whole state.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from functools import cache
from pathlib import Path
from typing import Final

from tst.balance.game import Game, start_game
from tst.balance.report import SCENARIO
from tst.loader import LoadedData, load_all

SEEDS: Final = (1, 2, 3)
# A chain builder (devices, chips, mines, fabs), the largest software company (its own data
# centres; 279 staff by 2039 on seed 1) and a research-led stage-4 company (V6's save): between
# them every system the turn runs. (acquirer, which buys companies, ends its game before 2039
# on seeds 1-3, so it cannot carry a 360-month check.)
STRATEGIES: Final = ("full_integrator", "integrator", "research_heavy")
TURNS: Final = 360  # January 2010 to December 2039
DATA: Final = Path(__file__).resolve().parents[2] / "data"
HASH_FILE: Final = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "m30_state_hashes.json"
)
HEX: Final = 16  # characters of each month's sha256 kept in the fixture

type Hashes = dict[str, list[str]]  # "strategy/seed" -> one hex digest per month played


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


_FIELDS: dict[type, tuple[str, ...]] = {}


def _fields(cls: type) -> tuple[str, ...]:
    names = _FIELDS.get(cls)
    if names is None:
        names = tuple(f.name for f in dataclasses.fields(cls) if f.compare)
        _FIELDS[cls] = names
    return names


class Digester:
    """Canonical digests of engine values. Dataclass instances and tuples are memoised by
    identity, holding the object so its id cannot be reused; `next_month` keeps only what
    the last digest saw, so the memo never outgrows one state."""

    def __init__(self) -> None:
        self._memo: dict[int, tuple[object, bytes]] = {}
        self._seen: dict[int, tuple[object, bytes]] = {}

    def next_month(self) -> None:
        self._memo, self._seen = self._seen, {}

    def digest(self, value: object) -> bytes:
        key = id(value)
        hit = self._seen.get(key)
        if hit is not None and hit[0] is value:
            return hit[1]
        hit = self._memo.get(key)
        if hit is not None and hit[0] is value:
            self._seen[key] = hit
            return hit[1]
        out = hashlib.sha256(self._encode(value)).digest()
        if isinstance(value, tuple) or dataclasses.is_dataclass(value):
            self._seen[key] = (value, out)
        return out

    def _encode(self, value: object) -> bytes:
        if value is None or isinstance(value, bool | int | str):
            return f"{type(value).__name__}:{value!r}".encode()
        if isinstance(value, float):
            return f"float:{value!r}".encode()
        if isinstance(value, enum.Enum):
            return f"enum:{type(value).__name__}.{value.name}".encode()
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            cls = type(value)
            parts = [f"dc:{cls.__module__}.{cls.__qualname__}".encode()]
            parts += [self.digest(getattr(value, name)) for name in _fields(cls)]
            return b"|".join(parts)
        if isinstance(value, tuple | list):
            return b"seq:" + b"".join(self.digest(v) for v in value)
        if isinstance(value, frozenset | set):
            return b"set:" + b"".join(sorted(self.digest(v) for v in value))
        if isinstance(value, Mapping):
            items = sorted(self.digest(k) + self.digest(v) for k, v in value.items())
            return b"map:" + b"".join(items)
        raise TypeError(f"no canonical digest for {type(value).__qualname__}")


def month_digest(digester: Digester, game: Game) -> str:
    """The digest of the game's full state and ledger balances after a month."""
    state = digester.digest(game.state)
    balances = digester.digest(game.balances)
    digester.next_month()
    return hashlib.sha256(state + balances).hexdigest()[:HEX]


def strategy(name: str) -> Callable[[Game], None]:
    from tst.balance.strategies_v2 import STRATEGIES as V2
    from tst.balance.strategies_v3 import V3

    return {**V2, **V3}[name]


def run_hashes(job: tuple[str, int], turns: int = TURNS) -> list[str]:
    """One strategy's game on one seed: a digest after every month played."""
    name, seed = job
    game = start_game(loaded(), seed, SCENARIO)
    script = strategy(name)
    digester = Digester()
    out: list[str] = []
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        out.append(month_digest(digester, game))
    return out


def key(name: str, seed: int) -> str:
    return f"{name}/{seed}"


def jobs() -> list[tuple[str, int]]:
    return [(name, seed) for name in STRATEGIES for seed in SEEDS]


def all_hashes(workers: int = 1, turns: int = TURNS) -> Hashes:
    todo = jobs()
    if workers <= 1:
        return {key(*j): run_hashes(j, turns) for j in todo}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        runs = pool.map(run_hashes, todo, [turns] * len(todo))
        return {key(*j): r for j, r in zip(todo, runs, strict=True)}


def recorded() -> Hashes:
    out: Hashes = json.loads(HASH_FILE.read_text(encoding="utf-8"))
    return out


def write(hashes: Hashes) -> None:
    HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(hashes, indent=0, sort_keys=True) + "\n"
    HASH_FILE.write_text(text, encoding="utf-8", newline="\n")


def first_difference(got: Sequence[str], want: Sequence[str]) -> str | None:
    """None when the runs are identical, else the first month that differs (turn 0 is
    January 2010: the n-th digest is the state after turn n-1)."""
    for turn, (g, w) in enumerate(zip(got, want, strict=False)):
        if g != w:
            return f"first differs after turn {turn}: {g} != {w}"
    if len(got) != len(want):
        return f"{len(got)} months played, {len(want)} recorded"
    return None
