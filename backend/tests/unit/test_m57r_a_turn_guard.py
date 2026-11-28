"""M57r-A sub-task 6 (review 10 item 30): `x_turn or y` treats turn 0 as missing.

In a 2008 game January 2010 (turn 0) is an ordinary month, so an optional turn is tested with
`is not None`, never truthiness. This AST guard fails on any `<...>turn or <...>` in tst/sim."""

from __future__ import annotations

import ast
from pathlib import Path

SIM = Path(__file__).resolve().parents[2] / "tst" / "sim"


def turn_ors(root: Path = SIM) -> list[str]:
    out = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
                continue
            first = node.values[0]
            name = (
                first.attr
                if isinstance(first, ast.Attribute)
                else first.id
                if isinstance(first, ast.Name)
                else None
            )
            if name is not None and name.endswith("turn"):
                out.append(f"{path.relative_to(root)}:{node.lineno}: {ast.unparse(node)}")
    return out


def test_no_optional_turn_is_tested_by_truthiness() -> None:
    assert turn_ors() == []


def test_the_guard_catches_one(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text("def f(p):\n    return p.resolved_turn or p.turn\n")
    assert turn_ors(tmp_path) == ["m.py:2: p.resolved_turn or p.turn"]
