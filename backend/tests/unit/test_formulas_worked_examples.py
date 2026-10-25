"""Every worked example in docs/formulas.md sections 1-5, with noise off.

The numbers come from the real balance.yaml, so a balance change that breaks a documented
example fails here.
"""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.people.formulas import (
    current_ability,
    displayed_range,
    growth_delta,
    narrow,
    pa_gap_mean,
    potential_phrase,
    salary_expectation_cents,
    scout_factor,
)
from tst.sim.scale import ATTR_MAX, ATTR_MIN

# --- Section 1 ------------------------------------------------------------------------------


def test_section_1_software_engineer_ca_is_114() -> None:
    skills = {
        "software_engineering": 14,
        "infrastructure": 11,
        "data": 9,
        "security": 8,
        "communication": 12,
        "product": 10,
    }
    primary = ["software_engineering", "infrastructure"]
    secondary = ["data", "security", "communication", "product"]
    assert current_ability(skills, primary, secondary) == pytest.approx(114)


def test_section_1_skills_outside_the_role_do_not_count() -> None:
    skills = {"a": 10.0, "b": 10.0, "c": 20.0}
    assert current_ability(skills, ["a"], ["b"]) == pytest.approx(100)


# --- Section 2 ------------------------------------------------------------------------------


def test_section_2_senior_engineer_salary_is_122000(loaded: LoadedData) -> None:
    people = loaded.balance.people
    assert people.level_ca["senior"].mean == 120
    expectation = salary_expectation_cents(
        band_mid_cents=11_500_000,
        ca=126,
        level_mean=people.level_ca["senior"].mean,
        region_multiplier_bp=10_000,
        round_to_cents=loaded.balance.payroll.salary_round_to_cents,
    )
    assert expectation == 12_200_000  # $121,900 -> $122,000


@pytest.mark.parametrize(
    ("level", "mean", "sd", "ages"),
    [
        ("junior", 70, 12, (21, 28)),
        ("mid", 95, 12, (25, 35)),
        ("senior", 120, 12, (29, 45)),
        ("staff", 140, 10, (32, 50)),
        ("principal", 155, 10, (35, 58)),
        ("exec", 150, 15, (38, 62)),
    ],
)
def test_section_2_level_table(
    loaded: LoadedData, level: str, mean: int, sd: int, ages: tuple[int, int]
) -> None:
    people = loaded.balance.people
    assert (people.level_ca[level].mean, people.level_ca[level].sd) == (mean, sd)
    assert (people.level_age[level].lo, people.level_age[level].hi) == ages


@pytest.mark.parametrize(
    ("age", "gap"),
    [
        (21, 45),
        (24, 45),
        (25, 30),
        (29, 30),
        (30, 18),
        (34, 18),
        (35, 8),
        (44, 8),
        (45, 2),
        (70, 2),
    ],
)
def test_section_2_pa_gap_by_age(loaded: LoadedData, age: int, gap: int) -> None:
    assert pa_gap_mean(age, loaded.balance.people) == gap


# --- Section 3 ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("age", "ca", "pa", "professionalism", "per_month", "per_year"),
    [
        (24, 106, 160, 14, 0.0737, 0.88),
        (38, 120, 128, 10, 0.0030, 0.04),
        (58, 130, 132, 12, -0.0150, -0.18),
    ],
)
def test_section_3_growth_examples(
    loaded: LoadedData,
    age: int,
    ca: float,
    pa: float,
    professionalism: float,
    per_month: float,
    per_year: float,
) -> None:
    delta = growth_delta(
        in_role=True,
        age=age,
        ca=ca,
        pa=pa,
        professionalism=professionalism,
        growth=loaded.balance.growth,
    )
    assert round(delta, 4) == per_month
    assert round(delta * 12, 2) == per_year


@pytest.mark.parametrize(
    ("age", "decline"), [(30, 0.0), (49, 0.0), (50, 0.005), (54, 0.005), (55, 0.015)]
)
def test_section_3_skills_outside_role_only_decline(
    loaded: LoadedData, age: int, decline: float
) -> None:
    delta = growth_delta(
        in_role=False, age=age, ca=100, pa=150, professionalism=20, growth=loaded.balance.growth
    )
    assert delta == pytest.approx(-decline)


def test_section_3_no_growth_at_potential(loaded: LoadedData) -> None:
    delta = growth_delta(
        in_role=True, age=22, ca=150, pa=150, professionalism=20, growth=loaded.balance.growth
    )
    assert delta == 0


# --- Section 4 ------------------------------------------------------------------------------


def test_section_4_worked_example(loaded: LoadedData) -> None:
    reveal = loaded.balance.reveal
    true, offset, judgment = 14.0, 0.2, 12

    assert scout_factor(judgment, reveal) == pytest.approx(0.8)

    hw = reveal.initial_hw.skill
    assert (round(hw, 2), displayed_range(true, hw, offset, ATTR_MIN, ATTR_MAX)) == (5.0, (8, 18))

    hw = narrow(hw, reveal.strength["job_post_screen"], judgment, reveal)
    assert (round(hw, 2), displayed_range(true, hw, offset, ATTR_MIN, ATTR_MAX)) == (4.2, (8, 18))

    hw = narrow(hw, reveal.strength["interview"], judgment, reveal)
    assert (round(hw, 2), displayed_range(true, hw, offset, ATTR_MIN, ATTR_MAX)) == (3.02, (10, 17))

    for _ in range(6):
        hw = narrow(hw, reveal.strength["employed_month"], judgment, reveal)
    assert (round(hw, 2), displayed_range(true, hw, offset, ATTR_MIN, ATTR_MAX)) == (2.03, (11, 16))


def test_section_4_initial_half_widths(loaded: LoadedData) -> None:
    hw = loaded.balance.reveal.initial_hw
    assert (hw.skill, hw.personality, hw.pa) == (5.0, 7.0, 67.0)  # PA raised in M2b (formulas.md 4)


def test_section_4_exact_below_half_point() -> None:
    assert displayed_range(13.4, 0.49, 0.3, ATTR_MIN, ATTR_MAX) == (13, 13)
    assert displayed_range(13.6, 0.0, 0.0, ATTR_MIN, ATTR_MAX) == (14, 14)


def test_section_4_range_is_clamped_to_scale() -> None:
    assert displayed_range(19.5, 5.0, 0.0, ATTR_MIN, ATTR_MAX) == (14, 20)
    assert displayed_range(1.5, 5.0, 0.0, ATTR_MIN, ATTR_MAX) == (1, 7)


# --- Section 5 ------------------------------------------------------------------------------


def test_section_5_founder_build_numbers(loaded: LoadedData) -> None:
    founder = loaded.balance.founder
    assert (founder.skill_base, founder.skill_points, founder.skill_cap) == (5, 70, 18)
    assert founder.default_age == 28
    assert (founder.age_range.lo, founder.age_range.hi) == (22, 60)
    assert founder.default_region == "north_america"


@pytest.mark.parametrize(
    ("noise", "multiplier"), [(0.0, 1.0), (0.25, 1.25), (-0.5, 0.5), (-1.0, 0.0), (-3.0, 0.0)]
)
def test_section_3_noise_is_multiplicative(
    loaded: LoadedData, noise: float, multiplier: float
) -> None:
    """Noise scales the growth term by max(0, 1 + noise); it never adds loss of its own."""
    kwargs = {"age": 52, "ca": 106, "pa": 160, "professionalism": 14}
    growth = loaded.balance.growth
    decline = 0.005  # d(52)
    base = growth_delta(in_role=True, growth=growth, **kwargs) + decline  # type: ignore[arg-type]
    noisy = growth_delta(in_role=True, growth=growth, noise=noise, **kwargs)  # type: ignore[arg-type]
    assert noisy == pytest.approx(base * multiplier - decline)
    assert growth.noise_rel_sd == 0.25


@pytest.mark.parametrize(
    ("lo", "hi", "phrase"),
    [
        (40, 69, "limited"),
        (70, 99, "decent"),
        (105, 135, "good to excellent"),
        (130, 159, "excellent"),
        (95, 165, "decent to outstanding"),
        (160, 200, "outstanding"),
    ],
)
def test_section_4_potential_phrase(loaded: LoadedData, lo: int, hi: int, phrase: str) -> None:
    """PA is shown only as a phrase for each bucket the displayed range touches."""
    bounds = loaded.balance.reveal.pa_phrase_bounds
    assert bounds == (70, 100, 130, 160)
    assert potential_phrase(lo, hi, bounds) == phrase
