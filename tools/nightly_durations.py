"""Merge the nightly shards' measured test durations into backend/tests/durations.json (M46).

The nightly jobs (`make nightly-ci`, .github/workflows/nightly.yml) print every test's
setup, call and teardown time with `--durations=0`. Save each shard's log (the Actions log
download, or `gh run view --log`) and run

    uv run --project backend python tools/nightly_durations.py LOG [LOG ...]

Each test's phases are summed and written into the durations file, which `--shard` reads to
balance the nightly matrix; entries for tests not in the logs are kept. The `check` shards are
unaffected: their marker filter deselects nightly tests before sharding (tests/conftest.py).
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DURATIONS = Path(__file__).resolve().parents[1] / "backend" / "tests" / "durations.json"
# "  123.45s call     tests/balance/test_x.py::test_y[a-b]" (a log line may carry a timestamp)
LINE = re.compile(r"(\d+(?:\.\d+)?)s\s+(setup|call|teardown)\s+(tests/\S+::\S+)")


def parse(text: str) -> dict[str, float]:
    totals: defaultdict[str, float] = defaultdict(float)
    for match in LINE.finditer(text):
        totals[match.group(3)] += float(match.group(1))
    return dict(totals)


def merge(existing: dict[str, float], measured: dict[str, float]) -> dict[str, float]:
    merged = {**existing, **{n: round(d, 2) for n, d in measured.items()}}
    return dict(sorted(merged.items()))


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__)
        return 2
    measured: dict[str, float] = {}
    for p in paths:
        measured |= parse(Path(p).read_text(encoding="utf-8", errors="replace"))
    existing = json.loads(DURATIONS.read_text()) if DURATIONS.exists() else {}
    DURATIONS.write_text(json.dumps(merge(existing, measured), indent=1) + "\n")
    minutes = sum(measured.values()) / 60
    print(f"{len(measured)} tests, {minutes:.0f} minutes, merged into {DURATIONS}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
