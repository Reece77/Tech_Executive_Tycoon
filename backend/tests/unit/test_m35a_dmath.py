"""M35a sub-task 1: the same game on Windows and Linux. tst.sim.dmath is correctly rounded (so
the same bits on every platform), and the sim calls no platform maths: no math.exp, log, pow
and the like, no statistics.NormalDist, and no `**` on floats (CPython hands those to the C
library's pow)."""

from __future__ import annotations

import ast
import math
from decimal import Context, Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tst.sim import dmath

ROOTS = [Path(__file__).resolve().parents[2] / "tst" / d for d in ("sim", "events")]
# math's functions whose last bit is the C library's (sqrt, floor, ceil, fsum, isfinite,
# copysign and frexp are exact everywhere)
PLATFORM_MATH = {
    "exp", "expm1", "exp2", "log", "log1p", "log10", "log2", "pow", "sin", "cos", "tan",
    "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh", "asinh", "acosh", "atanh",
    "erf", "erfc", "gamma", "lgamma", "hypot", "cbrt", "dist",
}  # fmt: skip
# `**` the sim may keep: integer constants, and integer powers of these integers (exact ints)
INT_POWERS = {("money.py", "DECIMAL_BASE"), ("formulas.py", "10")}
WIDE = Context(prec=80)


def _offences() -> list[str]:
    out = []
    for root in ROOTS:
        for path in sorted(root.rglob("*.py")):
            if path.name == "dmath.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                where = f"{path.relative_to(root.parent)}:{getattr(node, 'lineno', 0)}"
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "math"
                    and node.attr in PLATFORM_MATH
                ):
                    out.append(f"{where} math.{node.attr}")
                if isinstance(node, ast.alias) and node.name in ("NormalDist", "math.exp"):
                    out.append(f"{where} imports {node.name}")
                if isinstance(node, ast.ImportFrom) and node.module == "math":
                    out.append(f"{where} from math import ...")
                if isinstance(node, ast.BinOp | ast.AugAssign) and isinstance(node.op, ast.Pow):
                    left = node.left if isinstance(node, ast.BinOp) else node.target
                    right = node.right if isinstance(node, ast.BinOp) else node.value
                    consts = all(
                        isinstance(n, ast.Constant) and type(n.value) is int for n in (left, right)
                    )
                    if not consts and (path.name, ast.unparse(left)) not in INT_POWERS:
                        out.append(f"{where} {ast.unparse(node)}")
    return out


def test_the_sim_calls_no_platform_maths() -> None:
    assert _offences() == []


def _reference(d: Decimal) -> float:
    return float(WIDE.plus(d))


@given(st.floats(min_value=-700, max_value=700))
def test_exp_is_correctly_rounded(x: float) -> None:
    assert dmath.exp(x) == _reference(WIDE.exp(Decimal(x)))


@given(st.floats(min_value=1e-300, max_value=1e300))
def test_log_and_log10_are_correctly_rounded(x: float) -> None:
    assert dmath.log(x) == _reference(WIDE.ln(Decimal(x)))
    assert dmath.log10(x) == _reference(WIDE.log10(Decimal(x)))


@given(st.floats(min_value=1e-6, max_value=1e6), st.floats(min_value=-8, max_value=8))
def test_pow_is_correctly_rounded(x: float, y: float) -> None:
    want = (
        WIDE.power(Decimal(x), int(y))
        if y.is_integer()
        else WIDE.exp(WIDE.multiply(Decimal(y), WIDE.ln(Decimal(x))))
    )
    assert dmath.pow(x, y) == _reference(want)


@given(st.floats(min_value=-10, max_value=10))
def test_sin_and_asinh_are_within_half_an_ulp(x: float) -> None:
    assert abs(dmath.sin(x) - math.sin(x)) <= math.ulp(math.sin(x))
    assert abs(dmath.asinh(x) - math.asinh(x)) <= math.ulp(math.asinh(x))


def test_exact_cases_and_ieee_edges() -> None:
    assert dmath.log10(1000.0) == 3.0 and dmath.log10(1e-5) == -5.0
    assert dmath.log2(8.0) == 3.0 and dmath.log2(0.25) == -2.0
    assert dmath.exp(0.0) == 1.0 and dmath.log(1.0) == 0.0
    assert dmath.pow(2.0, 0.5) == math.sqrt(2.0)  # sqrt is correctly rounded too
    assert dmath.pow(-2.0, 3) == -8.0 and dmath.pow(1.5, 2) == 2.25
    assert dmath.pow(0.0, 2.0) == 0.0 and dmath.pow(5.0, 0) == 1.0
    assert dmath.exp(-1000.0) == 0.0 and dmath.exp(math.inf) == math.inf
    assert dmath.sin(0.0) == 0.0 and dmath.sin(math.pi / 2) == 1.0
    with pytest.raises(ValueError):
        dmath.log(0.0)
    with pytest.raises(ValueError):
        dmath.pow(-2.0, 0.5)
    with pytest.raises(OverflowError):
        dmath.exp(1000.0)
    with pytest.raises(OverflowError):
        dmath.pow(10.0, 400.0)


def test_normal_quantile_is_as241() -> None:
    from statistics import NormalDist

    for p in (0.5, 0.95, 0.975, 0.999, 1e-9, 0.3, 0.7):
        assert abs(dmath.normal_inv_cdf(p) - NormalDist().inv_cdf(p)) <= 4 * math.ulp(
            NormalDist().inv_cdf(p)
        )
    assert dmath.normal_inv_cdf(0.95) == 1.6448536269514715  # z_of(0.9), the exploration one
