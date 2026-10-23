"""Every worked example in docs/formulas.md sections 6-10 (and the section 3 retirement rule),
with noise off. Numbers come from the real balance.yaml, so a balance change that breaks a
documented example fails here.
"""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.hiring.formulas import (
    acceptance_probability,
    benefits_cents,
    energy_cost,
    fit_term,
    hint_band,
    is_lowball,
    market_mid_cents,
    monthly_salary_cents,
    morale_noise_sd,
    morale_step,
    morale_target,
    offer_score,
    pay_term,
    recruiter_fee_cents,
    resignation_bp,
    retirement_bp,
    runway_term,
    severance_cents,
)

# --- Section 6: founder energy --------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "cost"),
    [
        ("interview", 6),
        ("reference_check", 3),
        ("job_post", 4),
        ("recruiter", 4),
        ("network", 10),
        ("offer", 0),
    ],
)
def test_section_6_energy_costs(loaded: LoadedData, action: str, cost: int) -> None:
    assert energy_cost(action, loaded.balance) == cost
    assert loaded.balance.founder.energy_per_month == 100


# --- Section 7: hiring ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ratio", "score", "acceptance"),
    [(0.95, -0.10, 0.426), (1.00, 0.10, 0.574), (1.10, 0.50, 0.818)],
)
def test_section_7_offer_worked_example(
    loaded: LoadedData, ratio: float, score: float, acceptance: float
) -> None:
    """Stage 0, 50 bp equity, one matching interest, risk appetite 10, ambition 10."""
    offer = loaded.balance.hiring.offer
    s = offer_score(
        ratio=ratio,
        equity_bp=50,
        matching_interests=1,
        risk_appetite=10,
        ambition=10,
        stage=0,
        offer=offer,
    )
    assert s == pytest.approx(score)
    assert round(acceptance_probability(s, offer), 3) == acceptance


def test_section_7_gap_is_at_least_30_points(loaded: LoadedData) -> None:
    offer = loaded.balance.hiring.offer

    def p(ratio: float) -> float:
        kwargs = {"equity_bp": 50, "matching_interests": 1, "risk_appetite": 10, "ambition": 10}
        return acceptance_probability(
            offer_score(ratio=ratio, stage=0, offer=offer, **kwargs), offer
        )

    assert round((p(1.10) - p(0.95)) * 100) == 39


def test_section_7_ambition_boosts_equity_weight(loaded: LoadedData) -> None:
    offer = loaded.balance.hiring.offer
    base = {"ratio": 1.0, "equity_bp": 100, "matching_interests": 0, "risk_appetite": 10}
    calm = offer_score(ambition=15, stage=1, offer=offer, **base)  # not above 15
    hungry = offer_score(ambition=16, stage=1, offer=offer, **base)
    # equity value 100 bp x 0.002 x 0.8 (stage 1) = 0.16; boosted x 1.5 = 0.24
    assert hungry - calm == pytest.approx(0.08)


def test_section_7_lowball_and_hints(loaded: LoadedData) -> None:
    hiring = loaded.balance.hiring
    assert is_lowball(0.84, hiring) and not is_lowball(0.85, hiring)
    assert hint_band(0.5, hiring) == "likely"
    assert hint_band(0.3, hiring) == "likely"
    assert hint_band(0.1, hiring) == "uncertain"
    assert hint_band(-0.3, hiring) == "uncertain"
    assert hint_band(-0.31, hiring) == "unlikely"


def test_section_7_option_pool_numbers(loaded: LoadedData) -> None:
    hiring = loaded.balance.hiring
    assert (hiring.max_offer_equity_bp, hiring.option_pool_bp) == (200, 1000)
    assert hiring.candidate_shelf_turns == 3
    assert loaded.balance.morale.new_hire == 65


@pytest.mark.parametrize(
    ("channel", "size", "mix"),
    [
        ("network", (2, 4), (30, 40, 25, 5)),
        ("job_post", (6, 10), (45, 40, 13, 2)),
        ("recruiter", (4, 6), (10, 35, 40, 15)),
    ],
)
def test_section_7_channels(
    loaded: LoadedData, channel: str, size: tuple[int, int], mix: tuple[int, ...]
) -> None:
    ch = loaded.balance.hiring.channel[channel]
    assert (ch.size.lo, ch.size.hi) == size
    assert tuple(ch.level_mix[k] for k in ("junior", "mid", "senior", "staff")) == mix
    assert loaded.balance.hiring.channel["network"].sociability_bonus == 1
    assert loaded.balance.hiring.channel["network"].sociability_threshold == 15


# --- Section 8: payroll ---------------------------------------------------------------------


def test_section_8_senior_engineer_costs_12100_a_month(loaded: LoadedData) -> None:
    payroll = loaded.balance.payroll
    salary = monthly_salary_cents(11_500_000)
    benefits = benefits_cents(salary, payroll)
    office = payroll.office_cost_per_head_cents
    assert (salary, benefits, office) == (958_333, 191_667, 60_000)
    assert salary + benefits + office == 1_210_000


def test_section_8_other_costs(loaded: LoadedData) -> None:
    balance = loaded.balance
    assert balance.company.base_monthly_cost_cents == 50_000  # $500 from M1b
    assert balance.hiring.job_post_cost_cents == 50_000
    assert recruiter_fee_cents(11_500_000, balance.hiring) == 2_300_000  # 20%
    assert severance_cents(11_500_000, balance.payroll) == 958_333  # one month


# --- Section 9: morale ----------------------------------------------------------------------


def test_section_9_worked_example(loaded: LoadedData) -> None:
    """$85,000 against a $90,000 market mid, one matching interest, healthy runway."""
    morale = loaded.balance.morale
    pay = pay_term(8_500_000, 9_000_000, morale)
    assert round(pay, 2) == -3.33
    fit = fit_term(1, style_mismatch=False, morale=morale)
    assert fit == 5
    runway = runway_term(10**9, 10**9 - 10**6, morale)  # 999 months of runway
    assert runway == 0
    target = morale_target(pay, fit, runway, morale)
    assert round(target, 2) == 51.67
    value = 65.0
    for _ in range(6):
        value = morale_step(value, target, 0.0, morale)
    assert round(value, 1) == 53.2


def test_section_9_terms(loaded: LoadedData) -> None:
    morale = loaded.balance.morale
    assert market_mid_cents(9_000_000, 8_500) == 7_650_000  # Europe 0.85x
    assert pay_term(20_000_000, 9_000_000, morale) == 15  # capped
    assert pay_term(1_000_000, 9_000_000, morale) == -20  # floored
    assert fit_term(0, style_mismatch=True, morale=morale) == -5
    # runway: cash / (opening - cash)
    assert runway_term(1_000, 1_000, morale) == 0  # cash has not fallen
    assert runway_term(1_000, 900, morale) == 0  # 9 months
    assert runway_term(1_000, 850, morale) == -10  # 5.7 months
    assert runway_term(1_000, 700, morale) == -20  # 2.3 months
    assert runway_term(1_000, 0, morale) == -20  # cash <= 0 counts as critical
    assert runway_term(-500, -600, morale) == -20
    assert morale_step(99.0, 100.0, 5.0, morale) == 100  # clamped
    assert morale_step(1.0, 0.0, -5.0, morale) == 0
    assert morale_noise_sd(1, morale) == pytest.approx(2.0)
    assert morale_noise_sd(20, morale) == pytest.approx(0.1)


# --- Section 10: resignations (and section 3 retirement) ------------------------------------


@pytest.mark.parametrize(
    ("morale", "loyalty", "hopper", "chance"),
    [(70, 12, False, 45.0), (25, 6, False, 131.25), (25, 6, True, 262.5)],
)
def test_section_10_resignation_table(
    loaded: LoadedData, morale: float, loyalty: float, hopper: bool, chance: float
) -> None:
    """The formulas.md table shows these rounded: 45, 131 and 263 bp."""
    assert resignation_bp(morale, loyalty, hopper, loaded.balance.resign) == pytest.approx(chance)


def test_section_10_cap(loaded: LoadedData) -> None:
    resign = loaded.balance.resign
    # With the defaults the chance tops out at 50 x 3 x 2 x 2 = 600 bp (morale 0, loyalty 1,
    # job hopper), so the 2,000 bp cap does not bind; check it with a larger base.
    assert resignation_bp(0, 1, True, resign) == pytest.approx(600)
    steep = resign.model_copy(update={"base_bp": 500})
    assert resignation_bp(0, 1, True, steep) == resign.cap_bp == 2000


@pytest.mark.parametrize(("age", "chance"), [(59, 0.0), (60, 50.0), (62, 150.0), (70, 550.0)])
def test_section_3_retirement(loaded: LoadedData, age: int, chance: float) -> None:
    """A 62-year-old retires with 150 bp (1.5%) chance per month."""
    assert retirement_bp(age, loaded.balance.people) == pytest.approx(chance)


def test_section_10_tag_reveal_rates(loaded: LoadedData) -> None:
    tags = loaded.balance.tags
    assert (tags.reveal_bp_per_month, tags.reveal_bp_on_check) == (500, 1500)
