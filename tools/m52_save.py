"""Build M52's 2100 sandbox save and print 66.4 target 4 (a fixture tool, never used by the
game): M45's dynasty game (full_integrator with a family) played by the engine from January 2010
to December 2069 on seeds 1-3, continued in sandbox and played to December 2100
(`tst.balance.m52.play_2100`); seed 1's game is written to `<save dir>/<name>.tst.sqlite` for
the 2100 turn-time guard (tests/integration/test_m52_perf.py, TST_M52_SAVE).

    uv run --project backend python tools/m52_save.py <save dir> <name> [--seeds 1,2,3]
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent))

if TYPE_CHECKING:
    from tst.balance.m52 import LongPlay


def _line(r) -> str:  # type: ignore[no-untyped-def]
    from tst.balance import m52

    late = sorted(r.late_ms)
    median = late[len(late) // 2] if late else 0
    return (
        f"seed {r.seed}: to {r.reached} ({r.ended}), error {r.error}; largest integer"
        f" {r.largest_int:.3e} ({m52.INT64 / max(1, r.largest_int):,.0f}x below int64); largest"
        f" balance {r.largest_balance:.3e}; 2100 revenue {r.revenue_2100:.3e} cents"
        f" ({m52.INT64 / max(1, r.revenue_2100):,.0f}x below); 2100 months in memory median"
        f" {median} ms, at most {max(late, default=0)} ms; to 2069 against M45's fixture:"
        f" {r.m45_difference or 'identical'}"
    )


def _failures(runs: list[LongPlay]) -> list[str]:
    """Target 4's checks on each seed (as tests/balance/test_m52_balance.py): no error, December
    2100 reached and active, every integer within int64, the economy within its known miss."""
    from tst.balance import m52
    from tst.balance.known_misses import Reading, verdict

    out = []
    for r in runs:
        if r.error is not None:
            out.append(f"seed {r.seed}: {r.error}")
            continue
        if r.reached != "Dec 2100" or r.ended != "active":
            out.append(f"seed {r.seed}: reached {r.reached}, {r.ended}")
        if r.largest_int >= m52.INT64:
            out.append(f"seed {r.seed}: an integer past int64 ({r.largest_int})")
        score = r.revenue_2100 * m52.ECONOMY_MARGIN / m52.INT64
        if verdict(Reading("M52.economy_2100", score <= 1, score)) == "fail":
            out.append(f"seed {r.seed}: the 2100 economy at {score:.2f} is past its bound")
    return out


def main() -> int:
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("save_dir", type=Path)
    parser.add_argument("name")
    parser.add_argument("--seeds", default="1,2,3")
    args = parser.parse_args()
    seeds = [int(x) for x in args.seeds.split(",")]
    from e2e_m38_save import _write
    from tst.balance import m30, m52
    from tst.db.repository import create_save, ledger_balances, open_session
    from tst.sim.setup import DEFAULT_FOUNDER

    others = seeds[1:]
    with ProcessPoolExecutor(max_workers=max(1, len(others))) as pool:
        later = pool.map(m52.sandbox_2100, others) if others else iter(())
        game, first = m52.play_2100(seeds[0])
        print(_line(first), flush=True)
        runs = [first]
        for r in later:
            print(_line(r), flush=True)
            runs.append(r)
    # M57r-B (review 10 item 27): a failed run fails the job (it printed and exited 0 before)
    bad = _failures(runs)
    for line in bad:
        print(f"FAIL {line}", file=sys.stderr)
    if bad:
        return 1
    data = m30.loaded()
    args.save_dir.mkdir(parents=True, exist_ok=True)
    from tst.balance.m37 import FAMILY_AGES
    from tst.balance.report import SCENARIO
    from tst.sim.family.setup import FamilySpec

    old = args.save_dir / f"{args.name}.tst.sqlite"
    old.unlink(missing_ok=True)
    path = create_save(
        args.name,
        seeds[0],
        SCENARIO,
        company_name="Dynasty Co",
        data=data,
        save_dir=args.save_dir,
        founder=DEFAULT_FOUNDER,
        family=FamilySpec("children", FAMILY_AGES),
        length="dynasty",
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    _write(path, game.state, game.balances, start)
    print(f"wrote {path} at {game.state.turn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
