"""formulas.md 15.8 worked examples, and the 15.1 and 15.5 tables, as tests (M5)."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.rivals import formulas as f


def test_a_cost_leader_answers_a_price_war(loaded: LoadedData) -> None:
    """Zoho's SMB share fell from 47% to 41%: need 1, U = 1.4 (noise off), price x 0.9."""
    rv = loaded.balance.rivals
    need = f.need_price_cut(0.47 - 0.41, rv.need)
    assert need == 1.0
    assert f.utility(need, rv.weights["cost_leader"]["price_cut"], 0.0) == pytest.approx(1.4)
    assert round(2500 * rv.price_cut) == 2250  # $25 to $22.50


def test_a_premium_incumbent_ignores_a_small_threat(loaded: LoadedData) -> None:
    rv = loaded.balance.rivals
    need = f.need_price_cut(0.01, rv.need)
    assert need == pytest.approx(0.2)
    u = f.utility(need, rv.weights["premium"]["price_cut"], 0.0)
    assert u == pytest.approx(0.12) and u < rv.act_threshold


@pytest.mark.parametrize(
    ("ratio", "morale", "loyalty", "unvested", "score", "p", "band"),
    [
        # With the leaving penalty (-0.5) on the employee's side too (M5, Reece's decision).
        (143_750 / 118_000, 62, 12, 0.454, -1.086, 0.102, "likely to stay"),
        (143_750 / 135_000, 62, 12, 0.397, -1.585, 0.040, "likely to stay"),
        (1.218, 40, 8, 0.0, 1.323, 0.934, "likely to go"),
    ],
)
def test_poaching_priya(
    loaded: LoadedData,
    ratio: float,
    morale: float,
    loyalty: float,
    unvested: float,
    score: float,
    p: float,
    band: str,
) -> None:
    pb = loaded.balance.rivals.poach
    s = f.poach_score(ratio, morale, loyalty, unvested, pb)
    assert s == pytest.approx(score, abs=2e-3)
    assert f.poach_probability(s, pb) == pytest.approx(p, abs=1e-3)
    assert f.poach_band(f.poach_probability(s, pb), pb) == band


def test_incumbent_table(loaded: LoadedData) -> None:
    rows = {
        c.name: (c.personality, c.builder_skill, c.target_margin_bp, c.cash_months)
        for c in loaded.game_data.incumbents
    }
    assert rows["Salesforce"] == ("premium", 14, 1500, 24)
    assert rows["Zoho"] == ("cost_leader", 11, 1500, 18)
    assert rows["GitHub"] == ("aggressive", 15, 0, 12)
    assert rows["Check Point"] == ("premium", 14, 3000, 48)
    assert len(rows) == 12


def test_needs_and_labels(loaded: LoadedData) -> None:
    rv = loaded.balance.rivals
    n = rv.need
    assert f.need_price_rise(10, False, n) == pytest.approx(0.5)
    assert f.need_price_rise(10, True, n) == 0.0
    assert f.need_gap(80, 65, n.feature_gap) == 1.0
    assert f.need_gap(80, 74, n.brand_gap) == pytest.approx(0.2)
    assert f.need_enter(0.6, 20, n) == pytest.approx(0.5)
    assert f.need_enter(0.6, 6, n) == 0.0  # not enough cash to enter
    assert f.need_cut_costs(9, n) == pytest.approx(0.5)
    assert f.need_poach(0.6 * n.poach_gain, True, n) == pytest.approx(0.6)  # tuned in M5.9
    assert f.need_poach(0.6 * n.poach_gain, False, n) == 0.0
    assert [f.money_label(m, rv) for m in (40, 20, 5)] == ["deep pockets", "comfortable", "tight"]
    assert [f.rounded_headcount(h, rv) for h in (42.4, 154, 1_236)] == [42, 150, 1240]
    assert f.pool_budget_cents(1_000_000, 1500, 50_000, 80_000) == pytest.approx(720_000)
