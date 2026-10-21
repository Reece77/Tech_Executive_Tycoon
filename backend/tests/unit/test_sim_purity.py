"""ADR-0002 purity guard: scan tst/sim for forbidden imports and calls.

The scanner is also run against throwaway fixture modules that each break one rule, to
prove that it actually catches violations.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

SIM_DIR = Path(__file__).resolve().parents[2] / "tst" / "sim"

BANNED_MODULES = (
    "random",
    "time",
    "os",
    "io",
    "pathlib",
    "yaml",
    "socket",
    "subprocess",
    "shutil",
    "urllib",
    "http",
    "importlib",
    "tst.db",
    "tst.api",
    "tst.llm",
    "tst.loader",
    "tst.config",
    "sqlalchemy",
    "fastapi",
    "anthropic",
)
BANNED_BUILTIN_CALLS = ("open", "__import__", "eval", "exec")
CLOCK_ATTRS = ("now", "utcnow", "today")
CLOCK_RECEIVERS = ("datetime", "date")
# Only rng.py may construct generators; elsewhere numpy.random is limited to the type name.
RNG_MODULE = "rng.py"
NP_RANDOM_ALLOWED = ("Generator",)


def _is_banned(module: str) -> bool:
    return any(module == banned or module.startswith(banned + ".") for banned in BANNED_MODULES)


def _module_name(path: Path, root: Path) -> list[str]:
    rel = path.relative_to(root.parent.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return parts


def _resolve_from(node: ast.ImportFrom, package: list[str]) -> str:
    if node.level == 0:
        return node.module or ""
    base = package[: len(package) - node.level + 1]
    return ".".join([*base, *([node.module] if node.module else [])])


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _dotted(node.value)
        return f"{inner}.{node.attr}" if inner else None
    return None


def find_violations(path: Path, sim_root: Path = SIM_DIR) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module = _module_name(path, sim_root)
    package = module if path.name == "__init__.py" else module[:-1]
    is_rng = path.name == RNG_MODULE
    problems: list[str] = []

    def report(node: ast.AST, msg: str) -> None:
        problems.append(f"{path.name}:{getattr(node, 'lineno', '?')}: {msg}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_banned(alias.name):
                    report(node, f"imports {alias.name}")
                if alias.name.startswith("numpy.random") and not is_rng:
                    report(node, "imports numpy.random")
        elif isinstance(node, ast.ImportFrom):
            source = _resolve_from(node, package)
            targets = [source] + [f"{source}.{a.name}" for a in node.names]
            for target in targets:
                if _is_banned(target):
                    report(node, f"imports {target}")
                    break
            if source == "numpy.random" and not is_rng:
                for alias in node.names:
                    if alias.name not in NP_RANDOM_ALLOWED:
                        report(node, f"imports numpy.random.{alias.name}")
            if source == "numpy" and any(a.name == "random" for a in node.names) and not is_rng:
                report(node, "imports numpy.random")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_BUILTIN_CALLS:
                report(node, f"calls {func.id}()")
            if isinstance(func, ast.Attribute) and func.attr in CLOCK_ATTRS:
                receiver = _dotted(func.value) or ""
                if receiver.split(".")[-1] in CLOCK_RECEIVERS:
                    report(node, f"reads the clock via {receiver}.{func.attr}()")
        elif isinstance(node, ast.Attribute) and not is_rng:
            dotted = _dotted(node) or ""
            parts = dotted.split(".")
            if (
                len(parts) == 3
                and parts[0] in ("np", "numpy")
                and parts[1] == "random"
                and parts[2] not in NP_RANDOM_ALLOWED
            ):
                report(node, f"uses {dotted}")
    return problems


def _sim_files() -> Iterator[Path]:
    yield from sorted(SIM_DIR.rglob("*.py"))


def test_sim_package_is_pure() -> None:
    files = list(_sim_files())
    assert files, "no sim modules found"
    problems = [p for f in files for p in find_violations(f)]
    assert problems == []


@pytest.fixture
def fake_sim(tmp_path: Path) -> Path:
    """A throwaway tst/sim package where test cases write forbidden modules."""
    root = tmp_path / "tst" / "sim"
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("")
    return root


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import random\n", "imports random"),
        ("from time import monotonic\n", "imports time"),
        ("import os\n", "imports os"),
        ("from pathlib import Path\n", "imports pathlib"),
        ("import yaml\n", "imports yaml"),
        ("import io\n", "imports io"),
        ("from tst.db import repository\n", "imports tst.db"),
        ("from tst import api\n", "imports tst.api"),
        ("from .. import llm\n", "imports tst.llm"),
        ("from tst.loader import load_all\n", "imports tst.loader"),
        ("import sqlalchemy\n", "imports sqlalchemy"),
        ("from fastapi import FastAPI\n", "imports fastapi"),
        ("import anthropic\n", "imports anthropic"),
        ("data = open('x').read()\n", "calls open()"),
        ("import datetime\nx = datetime.datetime.now()\n", "reads the clock"),
        ("from datetime import date\nx = date.today()\n", "reads the clock"),
        ("import numpy as np\nx = np.random.default_rng(1)\n", "uses np.random.default_rng"),
        ("import numpy as np\nx = np.random.rand()\n", "uses np.random.rand"),
        ("from numpy.random import default_rng\n", "imports numpy.random.default_rng"),
    ],
)
def test_scanner_flags_forbidden_module(fake_sim: Path, source: str, expected: str) -> None:
    module = fake_sim / "bad_module.py"
    module.write_text(source)
    problems = find_violations(module, fake_sim)
    assert any(expected in p for p in problems), problems


def test_scanner_allows_generator_annotation(fake_sim: Path) -> None:
    module = fake_sim / "ok_module.py"
    module.write_text(
        "import numpy as np\n"
        "from datetime import timedelta\n"
        "def draw(gen: np.random.Generator) -> float:\n"
        "    return float(gen.random())\n"
    )
    assert find_violations(module, fake_sim) == []
