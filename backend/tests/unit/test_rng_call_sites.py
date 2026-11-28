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


# --- M57r-B (review 10 item 36 b): the families inside a package's one stream ------------------
# Each package's draws.gen(rng, turn, family, *key) wraps its single .stream call, so the guard
# above sees one call site however many draws it serves. Two sites sharing a (family, key) would
# reuse numbers; the families are the first half of that key, so each is checked: every
# draws.gen call names one of its package's declared key families (a constant or literal, never
# computed), and a package's key families are distinct integers.

FAMILY_PASS_THROUGH = {"pharma/pipeline.py"}  # helpers taking `family` from their callers


def _family_groups(draws: Path) -> list[dict[str, int]]:
    """The draws module's `A, B, C = 0, 1, 2  # ... key families` groups."""
    groups = []
    source = draws.read_text(encoding="utf-8")
    lines = source.splitlines()
    for node in ast.parse(source).body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target, value = node.targets[0], node.value
        if not (isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple)):
            continue
        if "key families" not in lines[node.lineno - 1]:
            continue
        names = [t.id for t in target.elts if isinstance(t, ast.Name)]
        values = [v.value for v in value.elts if isinstance(v, ast.Constant)]
        groups.append(dict(zip(names, values, strict=True)))
    # `FAMILIES = range(n)  # key families` then `A, B, ... = FAMILIES` (pharma's form)
    ranges: dict[str, int] = {}
    for node in ast.parse(source).body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "range"
            and "key families" in lines[node.lineno - 1]
        ):
            arg = node.value.args[0]
            if isinstance(arg, ast.Constant) and type(arg.value) is int:
                ranges[node.targets[0].id] = arg.value
        elif (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Tuple)
            and isinstance(node.value, ast.Name)
            and node.value.id in ranges
        ):
            names = [t.id for t in node.targets[0].elts if isinstance(t, ast.Name)]
            groups.append({n: i for i, n in enumerate(names)})
    return groups


def _module_ints(tree: ast.Module) -> dict[str, int]:
    """A module's top-level `NAME = <int>` and `A, B = <int>, <int>` constants."""
    out: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t, v = node.targets[0], node.value
            if isinstance(t, ast.Name) and isinstance(v, ast.Constant) and type(v.value) is int:
                out[t.id] = v.value
            elif isinstance(t, ast.Tuple) and isinstance(v, ast.Tuple):
                for n, c in zip(t.elts, v.elts, strict=False):
                    if (
                        isinstance(n, ast.Name)
                        and isinstance(c, ast.Constant)
                        and type(c.value) is int
                    ):
                        out[n.id] = c.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            v = node.value
            if isinstance(v, ast.Constant) and type(v.value) is int:
                out[node.target.id] = v.value
    return out


def family_problems(root: Path = SIM_DIR) -> list[str]:
    problems: list[str] = []
    for draws in sorted(root.rglob("draws.py")):
        pkg = draws.parent
        groups = _family_groups(draws)
        for g in groups:
            if len(set(g.values())) != len(g):
                problems.append(f"{draws.relative_to(root)}: key families share a value: {g}")
        declared = {name: v for g in groups for name, v in g.items()}
        by_value: dict[int, set[str]] = {}
        for path in sorted(pkg.rglob("*.py")):
            if path == draws:
                continue
            rel = path.relative_to(root).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            local = _module_ints(tree)
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "gen"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "draws"
                    and len(node.args) >= 3
                ):
                    continue
                fam = node.args[2]
                where = f"{rel}:{node.lineno}"
                value: int | None = None
                label = ""
                if (
                    isinstance(fam, ast.Attribute)
                    and isinstance(fam.value, ast.Name)
                    and fam.value.id == "draws"
                ):
                    value, label = declared.get(fam.attr), fam.attr
                    if value is None:
                        problems.append(f"{where}: family {fam.attr} is not a declared key family")
                        continue
                elif (
                    isinstance(fam, ast.Attribute)
                    and isinstance(fam.value, ast.Name)
                    and (pkg / f"{fam.value.id}.py").is_file()
                ):  # a sibling module's constant (power's plants.QUEUE_FAMILY)
                    sibling = ast.parse((pkg / f"{fam.value.id}.py").read_text(encoding="utf-8"))
                    value, label = _module_ints(sibling).get(fam.attr), fam.attr
                    if value is None:
                        problems.append(f"{where}: family {fam.attr} is not an int constant")
                        continue
                elif isinstance(fam, ast.Name) and fam.id in local:
                    value, label = local[fam.id], fam.id  # one name, one family, any module
                elif isinstance(fam, ast.Constant) and type(fam.value) is int:
                    value, label = fam.value, "a literal"
                elif (
                    isinstance(fam, ast.Name) and fam.id == "family" and rel in FAMILY_PASS_THROUGH
                ):
                    continue
                else:
                    problems.append(f"{where}: the family must be a draws constant or literal")
                    continue
                by_value.setdefault(value, set()).add(label)
        for value, labels in sorted(by_value.items()):
            named = {x for x in labels if x != "a literal"}
            if len(named) > 1:
                problems.append(f"{pkg.name}: family {value} under several names: {sorted(named)}")
    return problems


def test_each_draws_family_is_declared_and_distinct() -> None:
    assert family_problems() == []


def test_the_family_scanner_catches_violations(tmp_path: Path) -> None:
    pkg = tmp_path / "x"
    pkg.mkdir()
    (pkg / "draws.py").write_text("A, B = 0, 0  # tunable-exempt: key families\n")
    (pkg / "use.py").write_text(
        "K = 7\nL = 7\ng = draws.gen(rng, t, draws.C, 1)\nh = draws.gen(rng, t, n, 1)\n"
        "i = draws.gen(rng, t, K, 1)\nj = draws.gen(rng, t, L, 2)\n"
    )
    problems = family_problems(tmp_path)
    assert any("share a value" in p for p in problems)
    assert any("not a declared key family" in p for p in problems)
    assert any("must be a draws constant" in p for p in problems)
    assert any("under several names" in p for p in problems)
