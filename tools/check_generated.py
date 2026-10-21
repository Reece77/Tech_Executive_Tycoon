"""Regenerate frontend/src/api and fail if it differs from what git has (ADR-0009).

Used by `make check` and the pre-commit hook. Compares content with `git diff` (which
normalizes line endings) rather than `git status`, so a CRLF checkout on Windows that is
regenerated with LF endings does not count as a change.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GENERATED = "frontend/src/api"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def main() -> int:
    subprocess.run(
        ["pnpm", "gen:api"], cwd=REPO / "frontend", check=True, shell=sys.platform == "win32"
    )
    changed = _git("diff", "--name-only", "--", GENERATED).stdout.strip()
    untracked = _git("ls-files", "--others", "--exclude-standard", "--", GENERATED).stdout.strip()
    if changed or untracked:
        print(f"{GENERATED} is out of date with the backend schema. Commit these changes:")
        print("\n".join(line for line in (changed, untracked) if line))
        return 1
    print(f"{GENERATED} is in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
