"""Every worked example in docs/formulas.md section 13.12, plus the section 7 pitch examples
and the section 6 M2 energy costs, with noise off. Numbers come from the real balance.yaml,
so a balance change that breaks a documented example fails here.
"""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.hiring.formulas import energy_cost
from tst.sim.org.formulas import (
    growth_multiplier,
    is_raise_bonus,
    manager_morale_term,
    manager_quality,
    pitch,
    remote_term,
    span_factor,
    span_limit,
    tag_term,
)
from tst.sim.setup import DEFAULT_FOUNDER

# --- Section 6: M2 energy costs -------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "cost"),
    [
        ("create_unit", 2),
        ("dissolve_unit", 2),
        ("set_leader", 2),
        ("move_person", 1),
        ("set_policy", 1),
        ("give_raise", 2),
        ("promote", 3),
        ("hiring_plan", 2),
    ],
)
def test_section_6_org_energy_costs(loaded: LoadedData, action: str, cost: int) -> None:
    assert energy_cost(action, loaded.balance) == cost


def test_delegate_energy(loaded: LoadedData) -> None:
    d = loaded.balance.delegates
    assert (d.energy_per_month, d.scout_cost, d.max_ratio_bp) == (100, 20, 12000)


# --- Section 13.12 --------------------------------------------------------------------------


def test_team_lead_with_six_reports(loaded: LoadedData) -> None:
    org = loaded.balance.org
    assert span_limit(14, org) == 8
    s = span_factor(14, 6, org)
    assert s == 1.0
    q = manager_quality(14, 12, 10, s)
    assert q == pytest.approx(12.5)
    assert manager_morale_term(q, org) == pytest.approx(2.0)
    assert growth_multiplier(10, s, False, org) == pytest.approx(1.25)
    assert growth_multiplier(10, s, True, org) == pytest.approx(1.40)


def test_same_lead_with_twelve_reports(loaded: LoadedData) -> None:
    org = loaded.balance.org
    s = span_factor(14, 12, org)
    assert s == pytest.approx(0.667, abs=5e-4)
    q = manager_quality(14, 12, 10, s)
    assert q == pytest.approx(8.33, abs=5e-3)
    assert manager_morale_term(q, org) == pytest.approx(-1.33, abs=5e-3)


def test_founder_managing_twelve_directly(loaded: LoadedData) -> None:
    """The engineer default build gives leadership 11, communication 10, mentoring 5."""
    org = loaded.balance.org
    bg = loaded.game_data.background(DEFAULT_FOUNDER.background)
    assert bg is not None and bg.key == "engineer"
    base = loaded.balance.founder.skill_base

    def skill(key: str) -> float:
        return base + bg.default_allocation.get(key, 0) + bg.bonuses.get(key, 0)

    leadership, communication, mentoring = (
        skill("leadership"),
        skill("communication"),
        skill("mentoring"),
    )
    assert (leadership, communication, mentoring) == (11, 10, 5)
    assert span_limit(leadership, org) == 7
    s = span_factor(leadership, 12, org)
    assert s == pytest.approx(0.583, abs=5e-4)
    q = manager_quality(leadership, communication, mentoring, s)
    assert q == pytest.approx(5.40, abs=5e-3)
    assert manager_morale_term(q, org) == pytest.approx(-3.68, abs=5e-3)
    assert growth_multiplier(mentoring, s, False, org) == pytest.approx(0.90, abs=5e-3)

    # Same founder with two team leads: two direct reports.
    s2 = span_factor(leadership, 2, org)
    q2 = manager_quality(leadership, communication, mentoring, s2)
    assert (s2, q2) == (1.0, pytest.approx(9.25))
    assert manager_morale_term(q2, org) == pytest.approx(-0.60)


def test_lead_b_with_five_reports(loaded: LoadedData) -> None:
    org = loaded.balance.org
    assert span_limit(12, org) == 8
    s = span_factor(12, 5, org)
    q = manager_quality(12, 11, 7, s)
    assert q == pytest.approx(10.5)
    assert manager_morale_term(q, org) == pytest.approx(0.40)
    assert growth_multiplier(7, s, False, org) == pytest.approx(1.10)


@pytest.mark.parametrize(("recruiting", "expected"), [(7, -0.09), (10, 0.0), (15, 0.15)])
def test_offer_pitch(loaded: LoadedData, recruiting: float, expected: float) -> None:
    assert pitch(recruiting, loaded.balance.hiring) == pytest.approx(expected)


def test_manager_term_and_growth_are_capped(loaded: LoadedData) -> None:
    org = loaded.balance.org
    assert manager_morale_term(30, org) == 8 and manager_morale_term(-30, org) == -8
    assert growth_multiplier(20, 1.0, True, org) == 1.5
    assert growth_multiplier(1, 0.01, False, org) >= 0.75  # the floor is the S -> 0 limit


# --- Sections 13.6, 13.8, 13.9 --------------------------------------------------------------


@pytest.mark.parametrize(
    ("tag", "holders", "expected"),
    [
        ("culture_carrier", 1, 2),
        ("culture_carrier", 3, 2),
        ("credit_taker", 1, -2),
        ("credit_taker", 3, -4),
        ("toxic_high_performer", 1, -3),
        ("toxic_high_performer", 2, -6),
        ("toxic_high_performer", 4, -6),
        ("credit_taker", 0, 0),
    ],
)
def test_teammate_tag_terms(loaded: LoadedData, tag: str, holders: int, expected: float) -> None:
    assert tag_term(tag, holders, loaded.balance.org) == expected


@pytest.mark.parametrize(
    ("sociability", "remote", "expected"),
    [(14, True, -3), (18, True, -3), (7, True, 2), (3, True, 2), (10, True, 0), (18, False, 0)],
)
def test_remote_term(loaded: LoadedData, sociability: float, remote: bool, expected: float) -> None:
    assert remote_term(sociability, remote, loaded.balance.org) == expected


@pytest.mark.parametrize(
    ("old", "new", "bonus"),
    [
        (10_000_000, 10_500_000, True),
        (10_000_000, 10_499_999, False),
        (10_000_000, 9_000_000, False),
    ],
)
def test_raise_threshold(loaded: LoadedData, old: int, new: int, bonus: bool) -> None:
    assert is_raise_bonus(old, new, loaded.balance.org) is bonus
