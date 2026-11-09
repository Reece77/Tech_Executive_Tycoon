"""M19 (formulas.md 35): depletion, the reclamation provision, royalties, the accident-rate
formula and the other pure arithmetic of mines."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.mining import formulas as mf


def test_units_of_production_depletion() -> None:
    # $100M capitalized on an estimated 50 Mt: 10 Mt mined depletes a fifth
    assert mf.depletion_target(10_000_000_000, 10.0, 50.0) == 2_000_000_000
    assert mf.depletion_target(10_000_000_000, 60.0, 50.0) == 10_000_000_000  # never more
    assert mf.depletion_target(10_000_000_000, 0.0, 50.0) == 0
    assert mf.depletion_target(5, 1.0, 0.0) == 5  # no estimate: all of it


def test_reclamation_provision_and_royalties(loaded: LoadedData) -> None:
    per_t = loaded.balance.mining.reclamation_per_t_cents
    assert mf.reclamation_cents(1_000.0, per_t["open_pit"]) == 1_000 * per_t["open_pit"]
    assert mf.reclamation_cents(0.0, per_t["brine"]) == 0
    africa = loaded.game_data.region("africa").royalty_rate
    assert mf.royalty_cents(1_000_000, africa) == round(1_000_000 * africa)
    assert 0 < loaded.game_data.region("europe").royalty_rate < africa


def test_accident_rate_at_average_safety_is_the_base(loaded: LoadedData) -> None:
    """35.4: at a full crew of skill_ref and normal spend the chance a year is the subtype's
    base; the skill and coverage factors are relative to that (M19 decision)."""
    mb = loaded.balance.mining
    ab = mb.accident
    for sub in mb.subtypes.values():
        year = mf.accident_chance(sub.accident_base, ab.skill_ref, 1.0, "normal", ab) * 12
        assert year == pytest.approx(sub.accident_base)
        assert 0.001 <= sub.accident_base <= 0.005  # 35.6 target 3: 0.1-0.5% a mine-year
    base = mb.subtypes["open_pit"].accident_base
    f8 = mf.accident_chance(base, 8.0, 1.0, "normal", ab)
    f15 = mf.accident_chance(base, 15.0, 1.0, "normal", ab)
    assert f15 <= 0.6 * f8  # 35.6 target 3: skill 15 cuts it by at least 40% against 8
    half = mf.accident_chance(base, 10.0, 0.5, "normal", ab)
    assert half > mf.accident_chance(base, 10.0, 1.0, "normal", ab)  # a short crew: riskier
    high = mf.accident_chance(base, 10.0, 1.0, "high", ab)
    low = mf.accident_chance(base, 10.0, 1.0, "low", ab)
    assert high < f8 and low > high
    # the formula's own shape: (1.6 - slope s) x (1.3 - c), floored
    raw = mf.accident_factor(12.0, 0.8, ab)
    assert raw == pytest.approx((ab.skill_base - ab.skill_slope * 12) * (ab.cover_base - 0.8))
    assert mf.accident_factor(30.0, 2.0, ab) == pytest.approx(ab.floor * ab.floor)


def test_ramp_construction_and_overrun(loaded: LoadedData) -> None:
    mb = loaded.balance.mining
    pit, brine = mb.subtypes["open_pit"], mb.subtypes["brine"]
    assert [mf.ramp_share(pit, m) for m in (0, 11, 12, 24, 120)] == [0.4, 0.4, 0.75, 1.0, 1.0]
    assert mf.ramp_share(brine, 36) < 1.0 and mf.ramp_share(brine, 48) == 1.0  # 2 more years
    assert mf.construction_months(0.0, 24, 36) == 24 and mf.construction_months(1.0, 24, 36) == 36
    assert mf.overrun(0.5, 0.0, 0.6) == pytest.approx(0.3)
    lo = {k: v.hi for k, v in mb.overrun.items()}
    assert lo["definitive"] < lo["pre_feasibility"] < lo["scoping"] <= 0.6  # narrower when sure
    assert mf.reveal_month(10, 40, 0.5) == 25


def test_capex_payments_sum_to_the_total() -> None:
    total, paid = 1_000_003, 0
    for left in range(7, 0, -1):
        paid += mf.capex_payment(total, paid, left)
    assert paid == total


def test_capacity_scaling_and_staff(loaded: LoadedData) -> None:
    mb = loaded.balance.mining
    assert mf.capex_for(1_000_000, 100.0, 100.0, mb.capex_scale) == 1_000_000
    assert mf.capex_for(1_000_000, 125.0, 100.0, mb.capex_scale) < 1_250_000  # economies
    assert mf.staff_needed(500.0, mb.staff_per_kt) == 1
    assert mf.staff_needed(25_000.0, mb.staff_per_kt) == 3


def test_project_irr() -> None:
    assert mf.project_irr([-100.0, 110.0]) == pytest.approx(0.10, abs=1e-6)
    assert mf.project_irr([-100.0, -5.0]) is None
    flows = [-265.0, -325, -394, -88, 74, 128, 399, 395, 349, 439, 470, 304, 442, 168, 176, -18]
    irr = mf.project_irr(flows)
    assert irr is not None and 0.1 < irr < 0.3  # long flows do not overflow


def test_nationalization_history_is_cited_and_in_order(loaded: LoadedData) -> None:
    hist = loaded.game_data.nationalization
    assert hist is not None and hist.last_month == "2025-12"
    titles = " ".join(e.title for e in hist.events)
    for country in ("Bolivia", "Zimbabwe", "Chile", "Indonesia", "DR Congo", "Mexico"):
        assert country in " ".join(e.country for e in hist.events), country
    assert "cobalt" in titles.lower() and "lithium" in titles.lower()
    assert all(e.source.startswith("dossier 5") for e in hist.events)
    regions = loaded.game_data.region_keys
    assert all(e.region in regions for e in hist.events)
    risky = {r.key: r.resource_nationalism for r in loaded.game_data.regions}
    assert risky["africa"] > risky["europe"] and risky["latin_america"] > risky["oceania"]
