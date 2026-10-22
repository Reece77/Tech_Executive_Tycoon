"""ADR-0013: one stream name per call site in tst/sim.

Two call sites drawing from the same (turn, name, key) would reuse identical numbers, so
every `.stream(turn, "<name>", ...)` call must use a literal name no other call site uses.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tst.sim.rng import STREAM_IDS

SIM_DIR = Path(__file__).resolve().parents[2] / "tst" / "sim"


def stream_calls(path: Path, root: Path = SIM_DIR) -> list[tuple[str | None, str]]:
    """(stream name or None if not a literal, "file:line") for each .stream(...) call."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str | None, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "stream"
        ):
            arg = node.args[1] if len(node.args) > 1 else None
            name = (
                arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None
            )
            found.append((name, f"{path.relative_to(root).as_posix()}:{node.lineno}"))
    return found


def check_call_sites(files: list[Path], root: Path = SIM_DIR) -> list[str]:
    problems: list[str] = []
    seen: dict[str, str] = {}
    for path in files:
        for name, where in stream_calls(path, root):
            if name is None:
                problems.append(f"{where}: stream name must be a string literal")
            elif name not in STREAM_IDS:
                problems.append(f"{where}: unknown stream {name!r}")
            elif name in seen:
                problems.append(f"{where}: stream {name!r} already used at {seen[name]}")
            else:
                seen[name] = where
    return problems


def test_each_stream_name_has_one_call_site() -> None:
    files = sorted(SIM_DIR.rglob("*.py"))
    assert check_call_sites(files) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("a = rng.stream(t, 'growth', 1)\nb = rng.stream(t, 'growth', 2)\n", "already used"),
        ("name = 'growth'\na = rng.stream(t, name)\n", "must be a string literal"),
        ("a = rng.stream(t, 'nonsense')\n", "unknown stream"),
    ],
)
def test_scanner_catches_violations(tmp_path: Path, source: str, expected: str) -> None:
    module = tmp_path / "bad.py"
    module.write_text(source)
    problems = check_call_sites([module], tmp_path)
    assert any(expected in p for p in problems), problems


def test_scanner_accepts_distinct_names(tmp_path: Path) -> None:
    module = tmp_path / "ok.py"
    module.write_text("a = rng.stream(t, 'growth', 1)\nb = rng.stream(t, 'reveal', 1, 2)\n")
    assert check_call_sites([module], tmp_path) == []
