"""Merge the nightly's measured durations into fresh duration files (M59; a CI helper).

The nightly (.github/workflows/nightly.yml) measures every `check` and `nightly` backend test
(pytest `--durations-out`, one JSON file a shard) and every Playwright file (the e2e shards'
`TST_E2E_DURATIONS_OUT`), and this tool overlays those measurements on the committed files:

    uv run --project backend python tools/ci_durations.py backend OUT PIECE [PIECE ...]
    uv run --project backend python tools/ci_durations.py e2e OUT PIECE [PIECE ...]

`backend` starts from backend/tests/durations.json (entries the pieces do not measure, such
as the `timing` and `weekly` tests, are kept); `e2e` starts from frontend/e2e/durations.json
and keeps only spec files that exist. The nightly uploads both as the `durations` artifact and
opens no pull request: a session copies them in when the shard guard warns (docs/ci.md).
Note that CI measures a 2-core runner, where `make test-durations` measures the machine it runs
on; the backend guard's CHECK_FACTOR is fitted to local measurements (tests/unit/test_ci_shards.py).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASE = {
    "backend": REPO / "backend" / "tests" / "durations.json",
    "e2e": REPO / "frontend" / "e2e" / "durations.json",
}


def merge(kind: str, pieces: list[Path]) -> dict[str, float]:
    merged: dict[str, float] = json.loads(BASE[kind].read_text())
    for piece in pieces:
        if not piece.exists():  # a shard that measured nothing (its glob left unexpanded)
            continue
        merged.update(json.loads(piece.read_text()))
    if kind == "e2e":
        e2e = REPO / "frontend" / "e2e"
        merged = {f: s for f, s in merged.items() if (e2e / f).exists()}
    return dict(sorted(merged.items()))


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in BASE:
        print(__doc__)
        return 2
    out = Path(argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    merged = merge(argv[0], [Path(p) for p in argv[2:]])
    out.write_text(json.dumps(merged, indent=1) + "\n")
    print(f"{out}: {len(merged)} entries from {len(argv) - 2} measured files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
