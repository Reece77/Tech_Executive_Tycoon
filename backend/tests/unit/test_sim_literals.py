"""ADR-0008 guard: tunable numbers live in balance.yaml, not as literals in tst/sim.

Numeric literals other than 0, 1, -1, 2, 12 and 100 fail, except in rng.py and calendar.py
or on a line carrying `# tunable-exempt: <reason>` (for definitions such as the attribute
scale, which are not tunables). The scanner is also run against throwaway fixture modules.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SIM_DIR = Path(__file__).resolve().parents[2] / "tst" / "sim"
ALLOWED = frozenset({0, 1, -1, 2, 12, 100})
EXEMPT_FILES = frozenset({"rng.py", "calendar.py"})
EXEMPT_RE = re.compile(r"#\s*tunable-exempt:\s*\S")


def _numeric(node: ast.AST) -> float | int | None:
    if (
        isinstance(node, ast.Constant)
        and not isinstance(node.value, bool)
        and isinstance(node.value, int | float)
    ):
        return node.value
    return None


def find_literals(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    negated: set[int] = set()
    problems: list[str] = []

    def check(node: ast.AST, value: float | int) -> None:
        if value in ALLOWED:
            return
        line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
        if EXEMPT_RE.search(line):
            return
        problems.append(f"{path.name}:{node.lineno}: literal {value!r}")

    for node in ast.walk(tree):
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            value = _numeric(node.operand)
            if value is not None:
                negated.add(id(node.operand))
                check(node, -value)
    for node in ast.walk(tree):
        value = _numeric(node)
        if value is not None and id(node) not in negated:
            check(node, value)
    return problems


def test_sim_has_no_unexempted_literals() -> None:
    files = [p for p in sorted(SIM_DIR.rglob("*.py")) if p.name not in EXEMPT_FILES]
    assert files
    problems = [p for f in files for p in find_literals(f)]
    assert problems == []


@pytest.mark.parametrize(
    ("source", "flagged"),
    [
        ("RATE = 0.12\n", ["literal 0.12"]),
        ("x = -5\n", ["literal -5"]),
        ("CAP = 18  # tunable-exempt:\n", ["literal 18"]),  # a reason is required
        ("x = [0, 1, -1, 2, 12, 100, 1.0, 0.0]\n", []),
        ("SCALE = 20.0  # tunable-exempt: attribute scale definition\n", []),
        ("flag = True\nname = '42'\n", []),
    ],
)
def test_scanner(tmp_path: Path, source: str, flagged: list[str]) -> None:
    module = tmp_path / "module.py"
    module.write_text(source)
    found = find_literals(module)
    assert [p.split(": ", 1)[1] for p in found] == flagged
