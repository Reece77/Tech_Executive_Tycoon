"""Regenerate frontend/src/api and fail if it differs from what git has (ADR-0009).

Used by `make check` and the pre-commit hook.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GENERATED = "frontend/src/api"


def main() -> int:
    subprocess.run(
        ["pnpm", "gen:api"], cwd=REPO / "frontend", check=True, shell=sys.platform == "win32"
    )
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", GENERATED],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        print(f"{GENERATED} is out of date with the backend schema. Commit these changes:")
        print(status)
        return 1
    print(f"{GENERATED} is in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
