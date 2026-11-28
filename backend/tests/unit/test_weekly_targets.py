"""M57r-B (review 10 item 27): every test file with a `weekly` test is run by a Makefile weekly
target that weekly.yml runs by default, so no weekly guard sits where nothing can fail it (M52's
2100 target did)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"


def _weekly_files() -> set[str]:
    out = set()
    for path in (BACKEND / "tests").rglob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s*@pytest\.mark\.weekly\b|^pytestmark = .*weekly", text, re.M):
            out.add(path.relative_to(BACKEND).as_posix())
    return out


def _targets() -> dict[str, str]:
    """weekly-* target -> its recipe."""
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    out: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        m = re.match(r"^(weekly-[\w-]+):", line)
        if m:
            current = m[1]
            out[current] = ""
        elif current is not None and line.startswith("\t"):
            out[current] += line + "\n"
        elif line.strip() and not line.startswith("#"):
            current = None
    return out


def _scheduled() -> set[str]:
    text = (ROOT / ".github" / "workflows" / "weekly.yml").read_text(encoding="utf-8")
    found = re.search(r"inputs\.parts \|\| '(\[.*?\])'", text)
    assert found, "weekly.yml's default parts list"
    return set(yaml.safe_load(found[1]))


def test_every_weekly_test_file_runs_in_a_scheduled_weekly_target() -> None:
    targets = _targets()
    scheduled = _scheduled()
    assert set(scheduled) <= set(targets), set(scheduled) - set(targets)
    covered = {
        f
        for name, recipe in targets.items()
        if name in scheduled
        for f in re.findall(r"tests/[\w/]+\.py", recipe)
    }
    missing = sorted(_weekly_files() - covered)
    assert not missing, f"weekly tests no scheduled weekly target runs: {missing}"
