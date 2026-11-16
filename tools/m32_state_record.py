"""M32 (TEMPORARY, removed next commit): one pass of M30's nine runs, digesting each month
twice: the full state (the new fixture, written with --write) and the state without M32's
fields (compared with the fixture on disk, main's).
Usage: uv run python <this> [--write] [--workers N] [--turns N]"""

from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

from tst.balance import m30
from tst.balance.game import start_game
from tst.balance.report import SCENARIO
from tst.sim.state import GameState

M32 = {
    "plants",
    "ppas",
    "grid_queue",
    "power_months",
    "grid_outages",
    "region_paths",
    "power_world",
}


class Stripped(m30.Digester):
    def _encode(self, value: object) -> bytes:
        if isinstance(value, GameState):
            cls = type(value)
            parts = [f"dc:{cls.__module__}.{cls.__qualname__}".encode()]
            parts += [self.digest(getattr(value, n)) for n in m30._fields(cls) if n not in M32]
            return b"|".join(parts)
        return super()._encode(value)


def both(job: tuple[str, int], turns: int) -> tuple[list[str], list[str]]:
    name, seed = job
    game = start_game(m30.loaded(), seed, SCENARIO)
    script = m30.strategy(name)
    full, strip = m30.Digester(), Stripped()
    a: list[str] = []
    b: list[str] = []
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        a.append(m30.month_digest(full, game))
        b.append(m30.month_digest(strip, game))
    return a, b


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    p.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    p.add_argument("--turns", type=int, default=m30.TURNS)
    args = p.parse_args()
    t0 = time.perf_counter()
    todo = m30.jobs()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        runs = list(pool.map(both, todo, [args.turns] * len(todo)))
    want = m30.recorded()
    full = {}
    for job, (a, b) in zip(todo, runs, strict=True):
        k = m30.key(*job)
        full[k] = a
        diff = m30.first_difference(b, want.get(k, [])[: args.turns])
        print(
            f"{k}: without M32's fields {'identical to the fixture' if diff is None else diff}",
            flush=True,
        )
    print(f"{time.perf_counter() - t0:.0f} s")
    if args.write:
        m30.write(full)
        print("wrote", m30.HASH_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
