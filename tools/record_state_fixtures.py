"""Re-record a long state fixture and print it to the log (M46).

The state fixtures take hours to play (M30's nine 360-month runs, M37's nine runs with M37's
fields left out, M45's three 720-month dynasty runs, M32's history to 2025), longer than a local session should run
(CLAUDE.md §9 rule 7). CI's weekly workflow runs `make record-fixture FIXTURE=<name>` as a part
(the `parts` input); this writes the fixture and prints it between BEGIN and END marker lines,
so a session can copy it from the job log into backend/tests/fixtures/. Re-record only for an
intentional result change, with the reason in CHANGELOG.md (CLAUDE.md §6).

    uv run --project backend python tools/record_state_fixtures.py m30|m32|m37|m45
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tst.balance import m30, m32_history, m37, m45


def _record(name: str) -> Path:
    jobs = os.cpu_count() or 1
    if name == "m30":
        m30.write(m30.all_hashes(jobs))
        return m30.HASH_FILE
    if name == "m37":  # target 1's reference: the nine standard runs, M37's fields left out
        runs = m37.all_pre_2040(jobs, (False,))
        hashes = {key.rsplit("/", 1)[0]: digests for key, digests in runs.items()}
        text = json.dumps(hashes, indent=0, sort_keys=True) + "\n"
        m37.LEGACY_FILE.write_text(text, encoding="utf-8", newline="\n")
        return m37.LEGACY_FILE
    if name == "m45":
        m45.write(m45.all_hashes(jobs))
        return m45.HASH_FILE
    if name == "m32":  # M32's history (46.8 target 1): only for scripts that now build differently
        m32_history.write_history(m32_history.history_all(workers=jobs))
        return m32_history.HISTORY_FILE
    raise SystemExit(f"unknown fixture {name!r}: m30, m32, m37 or m45")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    path = _record(argv[0])
    print(f"BEGIN FIXTURE {path.name}")
    print(path.read_text(encoding="utf-8"), end="")
    print(f"END FIXTURE {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
