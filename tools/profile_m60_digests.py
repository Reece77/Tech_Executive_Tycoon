"""M60's identical-results harness (a measuring tool, never part of the game): play `--months`
months on a copy of a save as the timing guards do, and print, each month, M30's state digest
(`tst.balance.m30.Digester`) and a digest of every row of every table in the save. Run it before
and after a speed-up on the same save: the two outputs must match line for line.

    uv run --project backend python tools/profile_m60_digests.py <save.tst.sqlite> [--months 6]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

# Written outside the turn's transaction or by wall-clock helpers: not results.
SKIP_TABLES = frozenset({"alembic_version"})


def db_digest(path: Path) -> str:
    h = hashlib.sha256()
    con = sqlite3.connect(path)
    try:
        tables = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ]
        for t in tables:
            if t in SKIP_TABLES:
                continue
            h.update(t.encode())
            for row in con.execute(f'SELECT * FROM "{t}" ORDER BY 1, 2'):  # noqa: S608
                h.update(repr(row).encode())
    finally:
        con.close()
    return h.hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("save", type=Path)
    parser.add_argument("--months", type=int, default=6)
    args = parser.parse_args()

    from tests.helpers import answer_critical, continue_at_end
    from tst.balance.m30 import Digester
    from tst.db import migrate
    from tst.db.repository import load_state, open_session, run_turn
    from tst.loader import load_all

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / args.save.name
        shutil.copy(args.save, path)
        migrate.ensure_current(path)
        data = load_all(BACKEND / "data")
        continue_at_end(path, data)
        digester = Digester()
        for _ in range(args.months):
            answer_critical(path, data)
            run_turn(path, data)
            with open_session(path) as session:
                state = load_state(session)
            digester.next_month()
            print(
                f"turn {state.turn}: state {digester.digest(state).hex()[:16]} "
                f"db {db_digest(path)}",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
