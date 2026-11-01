"""docs/formulas.md 18.10 worked examples, plus the M8 data as loaded (M8 sub-task 1)."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.calendar import turn_to_ym, ym_to_turn
from tst.sim.org.formulas import (
    allocate_shared,
    coo_factor,
    coverage,
    layer_factor,
    seat_effect,
    seat_multiplier,
    support_churn,
    support_factor,
    support_morale,
    support_need,
)
from tst.sim.products.formulas import hosting_cents, monthly_growth
from tst.sim.products.setup import addressable_at
from tst.sim.rng import STREAM_IDS


def test_seat_effect(loaded: LoadedData) -> None:
    """A CTO with s = 14 has e = 0.5: builder output x 1.05; vacant at stage 3: x 0.95."""
    ex = loaded.balance.exec_seats
    cto = ex.seats["cto"].effect
    e = seat_effect(14, ex)
    assert e == pytest.approx(0.5)
    assert seat_multiplier(e, cto) == pytest.approx(1.05)
    assert seat_multiplier(ex.vacant_effect, cto) == pytest.approx(0.95)
    assert seat_effect(30, ex) == ex.effect_max
    assert seat_effect(1, ex) == ex.effect_min


def test_support_shortfall(loaded: LoadedData) -> None:
    """120 staff, 5 support: need 8, c = 0.625, output x 0.944, morale -2.25; with a COO at
    e = 0.5, k_COO = 0.75 and output x 0.958."""
    org = loaded.balance.org
    ex = loaded.balance.exec_seats
    assert support_need(120, org) == 8
    c = coverage(120, 5, org)
    assert c == pytest.approx(0.625)
    assert support_factor(c, 1.0, org) == pytest.approx(0.94375)
    assert round(support_factor(c, 1.0, org), 3) == 0.944
    assert support_morale(c, org) == pytest.approx(-2.25)
    k = coo_factor(0.5, ex.seats["coo"].effect)
    assert k == pytest.approx(0.75)
    assert round(support_factor(c, k, org), 3) == 0.958
    assert coverage(0, 0, org) == 1.0
    assert coverage(30, 5, org) == 1.0


def test_layer_tax(loaded: LoadedData) -> None:
    """Depth 3: lambda = 0.97; with the COO at e = 0.5: 0.9775. Never below 0.85."""
    org = loaded.balance.org
    assert layer_factor(3, 1.0, org) == pytest.approx(0.97)
    assert layer_factor(3, 0.75, org) == pytest.approx(0.9775)
    assert layer_factor(2, 1.0, org) == 1.0
    assert layer_factor(1, 1.0, org) == 1.0
    assert layer_factor(20, 1.0, org) == org.layer_floor


def test_allocation() -> None:
    """Corporate 12 staff and $520,000 of costs; Platform 128 (central), Fintech 46
    (embedded): Platform $475,429, Fintech $0, corporate keeps $44,571."""
    shares = allocate_shared(52_000_000, 12, {1: 128})
    assert shares == {1: 47_542_857}
    assert 52_000_000 - sum(shares.values()) == 4_457_143


def test_cross_division_factor(loaded: LoadedData) -> None:
    assert loaded.balance.org.cross_division_factor == pytest.approx(0.90)


def test_seat_weights_cover_six_seats(loaded: LoadedData) -> None:
    seats = loaded.balance.exec_seats.seats
    assert list(seats) == ["coo", "cfo", "cto", "cpo", "cmo", "cro"]
    assert seats["cto"].weights["ml_research"] == pytest.approx(0.10)


def test_new_categories(loaded: LoadedData) -> None:
    data = loaded.game_data
    keys = [c.key for c in data.categories]
    assert keys[-2:] == ["fintech", "ai_models"]  # appended: market stream keys unchanged
    fintech = data.category("fintech")
    assert fintech.launch_quality == 30
    assert fintech.growth_in(2015) == pytest.approx(0.25)
    ai = data.category("ai_models")
    assert ai.growth_in(2010) == pytest.approx(0.30)
    assert ai.growth_in(2022) == pytest.approx(1.50)
    assert ai.growth_in(2023) == pytest.approx(2.00)
    assert ai.growth_in(2040) == pytest.approx(0.25)
    assert monthly_growth(ai, 2023) ** 12 == pytest.approx(3.0)


def test_ai_demand_target(loaded: LoadedData) -> None:
    """18.9 target 4: AI's total addressable demand in January 2024 is 100-400 x 2010's."""
    data = loaded.game_data
    ai = data.category("ai_models")
    jan_2024 = ym_to_turn(2024, 1)
    ratio = sum(addressable_at(data, ai.key, s, jan_2024) for s in ai.segment_keys) / sum(
        m.addressable for m in ai.markets
    )
    print(f"AI demand January 2024 / January 2010: {ratio:.0f}x")
    assert 100 <= ratio <= 400


def test_compute_index(loaded: LoadedData) -> None:
    index = loaded.game_data.compute_index
    assert index.of(2010) == 1.0
    assert index.of(2016) == pytest.approx(0.85**6)
    assert index.of(2018) == pytest.approx(0.85**6 * 1.1**2)
    assert index.of(2022) == pytest.approx(index.of(2018))
    assert index.of(2024) == pytest.approx(index.of(2022) * 1.6 * 1.3)
    assert index.of(2025) == pytest.approx(index.of(2024) * 0.85)
    ai = loaded.game_data.category("ai_models")
    assert hosting_cents(ai, "smb", index.of(2016)) == pytest.approx(4000 * 0.85**6)
    fintech = loaded.game_data.category("fintech")
    assert hosting_cents(fintech, "smb", index.of(2016)) == 500  # only AI is indexed


def test_entrants(loaded: LoadedData) -> None:
    entrants = loaded.game_data.entrants
    assert [(e.name, e.year, e.month) for e in entrants] == [
        ("Square", 2010, 3),
        ("Stripe", 2011, 9),
        ("Plaid", 2013, 5),
        ("OpenAI", 2015, 12),
        ("Anthropic", 2021, 1),
    ]
    assert turn_to_ym(ym_to_turn(2011, 9)) == (2011, 9)
    assert STREAM_IDS["entrants"] == 20


def test_new_incumbents(loaded: LoadedData) -> None:
    names = [c.name for c in loaded.game_data.incumbents]
    assert names[-5:] == ["PayPal", "Intuit", "Fiserv", "IBM", "Nuance"]
    mix = loaded.balance.rivals.function_mix
    assert mix["fintech"] == {"builder": 0.50, "seller": 0.30, "marketer": 0.20}
    assert mix["ai_models"] == {"builder": 0.75, "seller": 0.10, "marketer": 0.15}


def test_redesigned_seat_effects(loaded: LoadedData) -> None:
    """18.10 (2026-10-31): a holder at s = 14 (e = 0.5) and a vacant seat (e = -0.5)."""
    seats = loaded.balance.exec_seats.seats
    e = 0.5
    assert seat_multiplier(e, seats["cto"].qcap) == pytest.approx(1.05)  # Q_cap 50 -> 52.5
    assert 1 - seats["cpo"].churn * e == pytest.approx(0.925)  # base churn 3% -> 2.775%
    assert seat_multiplier(e, seats["cmo"].brand) == pytest.approx(1.05)  # B* 80 -> 84
    assert min(100.0, 98 * seat_multiplier(e, seats["cmo"].brand)) == 100.0  # capped
    assert seat_multiplier(e, seats["cmo"].awareness) == pytest.approx(1.10)
    assert seat_multiplier(e, seats["cro"].pricing) == pytest.approx(1.05)  # p_ref $800 -> $840
    assert 1 - seats["cpo"].churn * -0.5 == pytest.approx(1.075)  # vacant CPO
    assert seat_multiplier(-0.5, seats["cro"].pricing) == pytest.approx(0.95)


def test_support_churn_and_delegate_energy(loaded: LoadedData) -> None:
    """120 staff, 5 support (c = 0.625): churn x 1.15; with the COO at e = 0.5, x 1.1125.
    A delegate's 100 energy becomes 62."""
    org = loaded.balance.org
    c = coverage(120, 5, org)
    assert support_churn(c, 1.0, org) == pytest.approx(1.15)
    assert support_churn(c, 0.75, org) == pytest.approx(1.1125)
    assert support_churn(1.0, 1.25, org) == 1.0
    assert int(loaded.balance.delegates.energy_per_month * c) == 62
