"""The same game on every platform (M35a sub-task 1): play M30's three strategies on seeds 1-3
for 120 months in memory (M52: and one custom scenario, the edited EV maker, for its first 24
months: formulas.md 66.4 target 3; M57r-A: and the 2030 dynasty start for 24 months, whose
draws include Generator.poisson with large means) and record every month's full-state digest (tst.balance.m30's
canonical digest), with a digest of each top-level state field, so two platforms' records name
the first month and the first part of the state that differ. CI
(.github/workflows/determinism.yml) runs `run` on Linux and Windows and `compare` on the two.

    uv run --project backend python tools/platform_digests.py run OUT.json [--turns N]
        [--workers N] [--dump JOB@TURN ...]
    uv run --project backend python tools/platform_digests.py compare A.json B.json

`--dump full_integrator/1@57` also writes every leaf of that job's state after turn 57
(path, type and exact value) so `compare` lists the leaves that differ.
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import hashlib
import json
import os
import sys
import time
from collections.abc import Iterator, Mapping
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

TURNS = 120
SHORT = 12  # hex characters kept per sub-digest


def _parts(value: object) -> Iterator[tuple[str, object]]:
    """A value's children with stable names: fields, indexes, sorted keys."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for f in dataclasses.fields(value):
            if f.compare:
                yield f".{f.name}", getattr(value, f.name)
    elif isinstance(value, tuple | list):
        for i, v in enumerate(value):
            yield f"[{i}]", v
    elif isinstance(value, Mapping):
        for k in sorted(value, key=repr):
            yield f"[{k!r}]", value[k]
    elif isinstance(value, frozenset | set):
        for v in sorted(value, key=repr):
            yield "{}", v


def _leaf(value: object) -> str | None:
    if value is None or isinstance(value, bool | int | str):
        return f"{type(value).__name__}:{value!r}"
    if isinstance(value, float):
        return f"float:{value!r} ({value.hex()})"
    if isinstance(value, enum.Enum):
        return f"enum:{type(value).__name__}.{value.name}"
    return None


def leaves(value: object, path: str = "state") -> Iterator[tuple[str, str]]:
    text = _leaf(value)
    if text is not None:
        yield path, text
        return
    for name, child in _parts(value):
        yield from leaves(child, path + name)


def _tree(digester: Any, root: object, prefix: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, child in _parts(root):
        out[prefix + name] = digester.digest(child).hex()[:SHORT]
    return out


CUSTOM = "custom_ev"  # M52 (66.4 target 3): one custom scenario, its first CUSTOM_MONTHS months
CUSTOM_SEED = 1
CUSTOM_MONTHS = 24
# M57r-A (review 10 item 29, ruling 7): a poisson-heavy run. Generator.poisson with a mean of 10
# or more uses the C library's log, outside dmath's guarantee; the 2030 dynasty start's world
# (pharma rivals' approvals and the other post-2025 draws) draws it every month.
POISSON = "poisson_dynasty"
POISSON_SCENARIO = "the_dynasty"
POISSON_SEED = 1
POISSON_MONTHS = 24


def run_job(job: tuple[str, int, int, tuple[int, ...]]) -> dict[str, Any]:
    from tst.balance import m30
    from tst.balance.game import start_game
    from tst.balance.report import SCENARIO

    name, seed, turns, dumps = job
    if name == CUSTOM:  # M52: the edited EV maker (tst.balance.m52.determinism_spec)
        from tst.balance import m51, m52

        game = m52.custom_game(seed)
        script = m51.ev_sensible
        turns = game.state.turn + min(turns, CUSTOM_MONTHS)
    elif name == POISSON:  # M57r-A: the 2030 start, poisson draws with large means
        from tst.balance import m52

        game = m52.start_historical(m30.loaded(), POISSON_SCENARIO, seed)
        script = m30.strategy("full_integrator")
        turns = game.state.turn + min(turns, POISSON_MONTHS)
    else:
        game = start_game(m30.loaded(), seed, SCENARIO)
        script = m30.strategy(name)
    digester = m30.Digester()
    months: list[dict[str, Any]] = []
    dumped: dict[str, dict[str, str]] = {}
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        played = game.state.turn - 1
        tree = _tree(digester, game.state, "state")
        tree.update(_tree(digester, {"balances": game.balances}, ""))
        months.append({"digest": m30.month_digest(digester, game), "tree": tree})
        if played in dumps:
            dumped[str(played)] = dict(leaves(game.state))
    return {"months": months, "dumps": dumped}


def run(out: Path, turns: int, workers: int, dumps: list[str]) -> int:
    from tst.balance import m30

    wanted: dict[str, set[int]] = {}
    for item in dumps:
        job, _, turn = item.partition("@")
        wanted.setdefault(job, set()).add(int(turn))
    # M52: and one custom scenario; M57r-A: and one poisson-heavy run
    jobs = [*m30.jobs(), (CUSTOM, CUSTOM_SEED), (POISSON, POISSON_SEED)]
    todo = [(n, s, turns, tuple(sorted(wanted.get(m30.key(n, s), ())))) for n, s in jobs]
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(run_job, todo))
    record = {
        "platform": sys.platform,
        "python": sys.version,
        "runs": {m30.key(n, s): r for (n, s, _, _), r in zip(todo, results, strict=True)},
    }
    out.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    digest = hashlib.sha256(
        "".join(m["digest"] for r in results for m in r["months"]).encode()
    ).hexdigest()[:16]
    print(f"{len(todo)} runs, {turns} months, {time.perf_counter() - started:.0f} s: {digest}")
    for (n, s, _, _), r in zip(todo, results, strict=True):
        print(f"{m30.key(n, s)}: {len(r['months'])} months, last {r['months'][-1]['digest']}")
    return 0


def compare(a_path: Path, b_path: Path) -> int:
    a, b = (json.loads(p.read_text(encoding="utf-8")) for p in (a_path, b_path))
    for label, rec in (("A", a), ("B", b)):
        print(f"{label}: {rec['platform']}, Python {rec['python'].split()[0]}")
    bad = 0
    for job in sorted(set(a["runs"]) | set(b["runs"])):
        ra, rb = a["runs"].get(job), b["runs"].get(job)
        if ra is None or rb is None:
            print(f"{job}: only on one platform")
            bad += 1
            continue
        first = next(
            (
                t
                for t, (x, y) in enumerate(zip(ra["months"], rb["months"], strict=False))
                if x["digest"] != y["digest"]
            ),
            None,
        )
        if first is None and len(ra["months"]) == len(rb["months"]):
            print(f"{job}: identical over {len(ra['months'])} months")
            continue
        bad += 1
        if first is None:
            print(f"{job}: {len(ra['months'])} months against {len(rb['months'])}")
            continue
        ta, tb = ra["months"][first]["tree"], rb["months"][first]["tree"]
        paths = sorted(p for p in set(ta) | set(tb) if ta.get(p) != tb.get(p))
        print(f"{job}: first differs after turn {first}; {len(paths)} parts differ:")
        for p in paths[:60]:
            print(f"    {p}")
        for turn in sorted(set(ra["dumps"]) & set(rb["dumps"]), key=int):
            la, lb = ra["dumps"][turn], rb["dumps"][turn]
            diff = sorted(p for p in set(la) | set(lb) if la.get(p) != lb.get(p))
            print(f"  leaves after turn {turn}: {len(diff)} of {len(la)} differ")
            for p in diff[:200]:
                print(f"    {p}\n      A {la.get(p)}\n      B {lb.get(p)}")
    print("identical" if not bad else f"{bad} runs differ")
    return 1 if bad else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("out", type=Path)
    r.add_argument("--turns", type=int, default=TURNS)
    r.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    r.add_argument("--dump", action="append", default=[], metavar="JOB@TURN")
    c = sub.add_parser("compare")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)
    args = parser.parse_args()
    if args.cmd == "run":
        return run(args.out, args.turns, args.workers, args.dump)
    return compare(args.a, args.b)


if __name__ == "__main__":
    sys.exit(main())
