"""M18 (formulas.md 34.2): the range rule and the estimate convergence arithmetic."""

from __future__ import annotations

import math

import pytest

from tst.loader import LoadedData
from tst.sim.exploration import formulas as xf


def test_range_rule(loaded: LoadedData) -> None:
    eb = loaded.balance.exploration
    assert xf.range_factor(0, eb) == pytest.approx(eb.skill_base)
    assert xf.range_factor(10, eb) == pytest.approx(eb.skill_base - 10 * eb.skill_slope)
    assert xf.range_factor(100, eb) == eb.skill_floor  # never below the floor
    # 34.6 target 2: a team at skill 15 has ranges 25-40% narrower than one at skill 8
    narrower = 1 - xf.range_factor(15, eb) / xf.range_factor(8, eb)
    assert 0.25 <= narrower <= 0.40


def test_z_of_confidence() -> None:
    assert xf.z_of(0.9) == pytest.approx(1.6449, abs=1e-4)
    assert xf.z_of(0.95) == pytest.approx(1.9600, abs=1e-4)


def test_finite_population_correction() -> None:
    assert xf.fpc(1, 66) == pytest.approx(1.0)
    assert xf.fpc(20, 66) == pytest.approx(math.sqrt(46 / 65))
    assert xf.fpc(66, 66) == 0.0


def test_grade_estimate_worked_example() -> None:
    """Holes 1%, 2%, 4% (log mean ln 2%), hole_sd 0.5, factors 1, 66 cells, 90%:
    centre ln 0.02, half-width 1.645 x 0.5 x sqrt(3)/3 x sqrt(63/65)."""
    center, hw = xf.grade_estimate([0.01, 0.02, 0.04], [1.0, 1.0, 1.0], 0.5, 66, 0.9)
    assert center == pytest.approx(math.log(0.02))
    assert hw == pytest.approx(1.6449 * 0.5 * math.sqrt(3) / 3 * math.sqrt(63 / 65), rel=1e-4)


def test_convergence_with_holes() -> None:
    """With N cells, the half-width falls faster than 1/sqrt(n): 40 holes give about half
    the range of 20 (34.6 target 1's +/-15% and +/-8%)."""
    _, hw20 = xf.grade_estimate([0.01] * 20, [1.0] * 20, 0.5, 66, 0.9)
    _, hw40 = xf.grade_estimate([0.01] * 40, [1.0] * 40, 0.5, 66, 0.9)
    assert hw40 / hw20 == pytest.approx(
        math.sqrt(20 / 40) * math.sqrt((66 - 40) / (66 - 20)), rel=1e-9
    )
    assert 1.8 < xf.half_width_pct(hw20) / xf.half_width_pct(hw40) < 2.0


def test_skill_narrows_the_estimate() -> None:
    _, wide = xf.grade_estimate([0.01] * 10, [1.0] * 10, 0.5, 66, 0.9)
    _, narrow = xf.grade_estimate([0.01] * 10, [0.6] * 10, 0.5, 66, 0.9)
    assert narrow == pytest.approx(0.6 * wide)


def test_half_width_pct_is_symmetric_in_display() -> None:
    assert xf.half_width_pct(math.asinh(0.6)) == pytest.approx(0.6)


def test_categories(loaded: LoadedData) -> None:
    e = loaded.balance.exploration.estimate
    assert (e.inferred, e.indicated, e.measured) == (8, 20, 40)  # 34.2
    cat = [xf.category_for(n, e.inferred, e.indicated, e.measured) for n in (7, 8, 20, 39, 40)]
    assert cat == [None, "inferred", "indicated", "indicated", "measured"]


def test_npv_worked_example(loaded: LoadedData) -> None:
    """30 Mt at 1% with 90% recovery over a 15-year life is 18,000 t a year; at $8,000/t less
    5% royalty and $4,000/t, $64.8M a year; capex $400M over 3 years at 8%."""
    fb = loaded.balance.exploration.feasibility
    npv = xf.npv_usd(
        tonnage_mt=30,
        grade=0.01,
        recovery=0.9,
        capex_usd=400e6,
        opex_per_t=4000,
        price_now=8000,
        price_long=8000,
        build_years=3,
        fb=fb,
    )
    r = fb.discount_rate
    cash = 18_000 * (8000 * (1 - fb.royalty) - 4000)
    expect = cash * xf.annuity(r, fb.life_years) * (1 + r) ** -3 - 400e6 / 3 * xf.annuity(r, 3)
    assert npv == pytest.approx(expect)
    assert xf.annuity(0.08, 15) == pytest.approx(8.5595, abs=1e-4)
