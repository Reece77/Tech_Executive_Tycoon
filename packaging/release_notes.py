"""Release notes from CHANGELOG.md (M58 sub-task 5): the "What's new" the game shows.

    python packaging/release_notes.py 6.0.0 [--previous-changelog OLD.md] [--out notes.md]

1. A `## v6.0.0` (or `## 6.0.0`) section, when CHANGELOG has one, is used as written: write
   one before tagging for hand-written notes.
2. Otherwise the top-level entries of `## Unreleased` that the previous release's CHANGELOG
   did not have (the workflow passes it with --previous-changelog), each cut to its first line.
3. With no previous release, the newest MAX_ENTRIES entries the same way.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_ENTRIES = 12
MAX_LINE = 400


def sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        if m := re.match(r"^## +(.+?)\s*$", line):
            current = out.setdefault(m[1].strip().lower(), [])
        elif current is not None:
            current.append(line)
    return out


def entries(lines: list[str]) -> list[str]:
    """Top-level bullets ("- ..." at column 0), first line only."""
    return [ln[2:].strip() for ln in lines if ln.startswith("- ")]


def _short(entry: str) -> str:
    return entry if len(entry) <= MAX_LINE else entry[: MAX_LINE - 1].rstrip() + "…"


def notes(version: str, changelog: str, previous: str | None = None) -> str:
    version = version.removeprefix("v")
    found = sections(changelog)
    for key in (f"v{version}", version):
        if key in found:
            return "\n".join(found[key]).strip() + "\n"
    now = entries(found.get("unreleased", []))
    if previous is not None:
        seen = set(entries(sections(previous).get("unreleased", [])))
        now = [e for e in now if e not in seen]
    else:
        now = now[:MAX_ENTRIES]
    if not now:
        return "Fixes and improvements.\n"
    return "\n".join(f"- {_short(e)}" for e in now) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version")
    parser.add_argument("--changelog", type=Path, default=ROOT / "CHANGELOG.md")
    parser.add_argument("--previous-changelog", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="write here (UTF-8), not stdout")
    args = parser.parse_args(argv)
    previous = args.previous_changelog
    text = notes(
        args.version,
        args.changelog.read_text(encoding="utf-8"),
        previous.read_text(encoding="utf-8") if previous and previous.is_file() else None,
    )
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
