"""M50b (the 2000 start, formulas.md 60.4-60.7): readings and the 2008/2010 guard.

The guard (brief, "Lane"): a 2008 game and a 2010 game are identical to `main` before M50b.
`identity_hashes` plays M30's strategies from January 2008 and January 2010 on seeds 1-2 in
memory and digests the full state and ledger balances after every month (M30's digester);
`tests/fixtures/m50b_identity_hashes.json` holds the digests recorded on `main` before any
M50b change (`tools/m50b_identity.py --write`), and the nightly test compares with them.
"""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Final

from tst.balance import m30, m50

IDENTITY_SEEDS: Final = (1, 2)
IDENTITY_STRATEGIES: Final = ("full_integrator", "research_heavy")
IDENTITY_YEARS: Final = (2008, 2010)
IDENTITY_MONTHS: Final = 120  # ten years from each start (2008-2017, 2010-2019)
IDENTITY_FILE: Final = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "m50b_identity_hashes.json"
)

type Job = tuple[str, int, int]  # strategy, seed, start year


def identity_key(job: Job) -> str:
    name, seed, year = job
    return f"{year}/{name}/{seed}"


def identity_jobs() -> list[Job]:
    return [
        (name, seed, year)
        for year in IDENTITY_YEARS
        for name in IDENTITY_STRATEGIES
        for seed in IDENTITY_SEEDS
    ]


def identity_run(job: Job, months: int = IDENTITY_MONTHS) -> list[str]:
    """One strategy's game from January of its start year: a digest after every month."""
    name, seed, year = job
    game = m50.start(seed, year)
    script = m30.strategy(name)
    digester = m30.Digester()
    out: list[str] = []
    while len(out) < months and not game.state.ended:
        script(game)
        game.turn()
        out.append(m30.month_digest(digester, game))
    return out


def identity_hashes(workers: int = 1, months: int = IDENTITY_MONTHS) -> m30.Hashes:
    todo = identity_jobs()
    if workers <= 1:
        return {identity_key(j): identity_run(j, months) for j in todo}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        runs = pool.map(identity_run, todo, [months] * len(todo))
        return {identity_key(j): r for j, r in zip(todo, runs, strict=True)}


def identity_recorded() -> m30.Hashes:
    out: m30.Hashes = json.loads(IDENTITY_FILE.read_text(encoding="utf-8"))
    return out


def identity_write(hashes: m30.Hashes) -> None:
    text = json.dumps(hashes, indent=0, sort_keys=True) + "\n"
    IDENTITY_FILE.write_text(text, encoding="utf-8", newline="\n")


def identity_differences(got: m30.Hashes, want: m30.Hashes) -> list[str]:
    return [
        f"{k}: {d}"
        for k in sorted(want)
        if (d := m30.first_difference(got.get(k, []), want[k])) is not None
    ]
