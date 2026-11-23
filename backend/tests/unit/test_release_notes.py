"""M58: the release notes (the game's "What's new") come from CHANGELOG.md."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[3] / "packaging" / "release_notes.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_notes", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OLD = """# Changelog

## Unreleased

- M57 old work (detail):
  - a sub-point
"""
NEW = """# Changelog

## Unreleased

- M58 a real executable: the game installs like any program.
  - packaging
- M57 old work (detail):
  - a sub-point
"""


def test_entries_new_since_the_previous_release() -> None:
    notes = _module().notes("6.1.0", NEW, OLD)
    assert notes == "- M58 a real executable: the game installs like any program.\n"


def test_a_written_section_wins() -> None:
    text = NEW + "\n## v6.1.0\n\nHand-written notes.\n"
    assert _module().notes("v6.1.0", text, OLD).strip() == "Hand-written notes."


def test_first_release_lists_the_newest_entries_and_never_comes_back_empty() -> None:
    rn = _module()
    assert rn.notes("6.0.0", NEW).splitlines() == [
        "- M58 a real executable: the game installs like any program.",
        "- M57 old work (detail):",
    ]
    assert rn.notes("6.0.1", OLD, OLD) == "Fixes and improvements.\n"


def test_the_real_changelog_gives_notes(tmp_path: Path) -> None:
    out = tmp_path / "notes.md"
    assert _module().main(["6.0.0", "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("- ")
