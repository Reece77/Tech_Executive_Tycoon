"""M43a (formulas.md 54.1): market ceilings, saturation and long-run growth."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.markets import saturation as sat
from tst.sim.markets.longrun import _path, with_long_run
from tst.sim.products.phases import brand_and_demand


def test_factor_fades_and_stops() -> None:
    assert sat.factor(0.0, 100.0) == 1.0
    assert sat.factor(25.0, 100.0) == pytest.approx(0.75)
    assert sat.factor(100.0, 100.0) == 0.0
    assert sat.factor(150.0, 100.0) == 0.0  # never negative: the clamp brings it back
    assert sat.factor(1.0, 0.0) == 0.0


def test_gdp_history_interpolates_and_trend_follows(loaded: LoadedData) -> None:
    data, balance = loaded.game_data, loaded.balance
    assert data.macro_history is not None
    table = data.macro_history.gdp["north_america"]
    assert sat.gdp_trend(balance, data, "north_america", 0) == pytest.approx(table[2010])
    jan_2025 = sat.gdp_trend(balance, data, "north_america", ym_to_turn(2025, 1))
    assert jan_2025 == pytest.approx(table[2025])
    # mid-2012: geometric between 2010 and 2015, 2.5 years in
    mid = sat.gdp_trend(balance, data, "north_america", ym_to_turn(2012, 7))
    assert mid == pytest.approx(table[2010] * (table[2015] / table[2010]) ** 0.5)
    g = balance.markets.gdp_growth["north_america"]
    later = sat.gdp_trend(balance, data, "north_america", ym_to_turn(2035, 1))
    assert later == pytest.approx(table[2025] * (1 + g) ** 10)


def test_ceiling_worked_example(loaded: LoadedData) -> None:
    """C = share x GDP x economy_scale.money x (1 + lift x eras): AI models in North America in
    January 2010, before any era, is 1.5% of $17.7T x 0.0849 = $22.5B a year in game dollars."""
    data, balance = loaded.game_data, loaded.balance
    state = fresh_game(loaded)
    c = sat.ceiling_cents(state, balance, data, "ai_models", "north_america")
    share = balance.markets.ceiling_of("ai_models")
    assert c == pytest.approx(share * 17.7e12 * 100 * balance.economy_scale.money)
    arrived = replace(state, turn=ym_to_turn(2023, 1))
    from tst.sim.research.models import EraArrival

    for key in ("deep_learning", "transformers", "large_language_models"):
        arrived = replace(
            arrived, era_arrivals=(*arrived.era_arrivals, EraArrival(key, 0, None, 0))
        )
    n = sat.eras_lifting(arrived, data, "ai_models")
    assert n == 3
    lifted = sat.ceiling_cents(arrived, balance, data, "ai_models", "north_america")
    gdp = sat.gdp_trend(balance, data, "north_america", arrived.turn)
    assert lifted == pytest.approx(
        share
        * gdp
        * 1e14
        * balance.economy_scale.money
        * (1 + balance.markets.era_ceiling_lift * 3)
    )


def test_unit_and_medical_values(loaded: LoadedData) -> None:
    """A unit-sale customer is worth units / replacement months x price a month; a medical
    device adds its consumables (54.1's A)."""
    data = loaded.game_data
    dev = data.category("devices").market("consumer")
    assert dev.replacement_months is not None
    v = sat.segment_value(data, "devices", "consumer", "north_america", "north_america")
    assert v == pytest.approx(
        dev.reference_price_cents * dev.units_per_customer / dev.replacement_months * 12
    )
    sr = data.category("surgical_robotics").market("enterprise")
    assert sr.replacement_months is not None
    v = sat.segment_value(data, "surgical_robotics", "enterprise", "north_america", "north_america")
    assert v == pytest.approx(
        (
            sr.reference_price_cents * sr.units_per_customer / sr.replacement_months
            + sr.units_per_customer * 5740000
        )
        * 12
    )


def test_growth_fades_near_the_ceiling(loaded: LoadedData) -> None:
    """A home market at half its ceiling grows at half its rate (54.1)."""
    data, balance = loaded.game_data, loaded.balance
    state = replace(fresh_game(loaded), turn=ym_to_turn(2026, 1))
    m = next(x for x in state.markets if x.category == "b2b_saas" and x.segment == "smb")
    others = [x for x in state.markets if x.category == "b2b_saas"]
    home = "north_america"
    rows = [(x.category, x.segment, home, x.addressable) for x in others]
    value = sat.market_values(state, rows, data, home)[("b2b_saas", home)]
    cap = sat.ceiling_cents(state, balance, data, "b2b_saas", home)
    scale = 0.5 * cap / value
    markets = tuple(
        replace(x, addressable=x.addressable * scale) if x.category == "b2b_saas" else x
        for x in state.markets
    )
    before = replace(state, markets=markets)
    after = brand_and_demand(before, balance, data)
    grown = next(x for x in after.markets if x.category == "b2b_saas" and x.segment == "smb")
    g = data.category("b2b_saas").growth_in(2026)
    assert grown.addressable / (m.addressable * scale) == pytest.approx((1 + g * 0.5) ** (1 / 12))


def test_no_ceiling_before_2026(loaded: LoadedData) -> None:
    """PM, 2026-11-18: the history to 2025 grows as before M43a, whatever a market's size."""
    data, balance = loaded.game_data, loaded.balance
    state = replace(fresh_game(loaded), turn=ym_to_turn(2025, 12))
    assert not sat.active(state, balance, data)
    assert sat.active(replace(state, turn=ym_to_turn(2026, 1)), balance, data)
    big = replace(
        state, markets=tuple(replace(x, addressable=x.addressable * 1e6) for x in state.markets)
    )
    after = brand_and_demand(big, balance, data)
    m = next(x for x in after.markets if x.category == "b2b_saas" and x.segment == "smb")
    b = next(x for x in big.markets if x.category == "b2b_saas" and x.segment == "smb")
    g = data.category("b2b_saas").growth_in(2025)
    assert m.addressable / b.addressable == pytest.approx((1 + g) ** (1 / 12))


def test_long_run_decays_after_its_start(loaded: LoadedData) -> None:
    """54.1: AI models' base growth from markets.mature_start_year halves its gap to the
    economy's growth plus its premium every half-life; M37's maturity takes over in 2040."""
    data, balance = loaded.game_data, loaded.balance
    mb = balance.markets
    table = data.eras.base_growth["ai_models"]
    target = mb.mature_gdp_growth + mb.premium_of("ai_models")
    start = mb.mature_start_year
    g0 = table[start]
    for y in (start + 1, start + 5, 2039):
        want = target + (g0 - target) * 0.5 ** ((y - start) / mb.mature_half_life_years)
        assert table[y] == pytest.approx(want)
    # a rate at or below its target, or a table with its own later years, is unchanged
    low = mb.model_copy(update={"mature_gdp_growth": 5.0})
    assert _path({2010: 0.2}, 0.2, "b2b_saas", low, 2039) is None
    replaced = _path({2010: 0.2, 2035: 0.1}, 0.2, "b2b_saas", mb, 2039)
    floor = mb.mature_gdp_growth + mb.premium_of("b2b_saas")
    hl, start = mb.mature_half_life_years, mb.mature_start_year
    assert replaced is not None  # a rate listed after the start gives way to the decay
    assert replaced[2035] == pytest.approx(floor + (0.2 - floor) * 0.5 ** ((2035 - start) / hl))
    assert _path({2010: 0.2}, 0.2, "b2b_saas", mb, 2039) is not None
    assert with_long_run(data.categories, data.eras, low, 2039)[0] == data.categories


def test_markets_whose_demand_is_set_have_no_ceiling(loaded: LoadedData) -> None:
    data = loaded.game_data
    assert not sat.grows(data, "vehicles")
    assert sat.grows(data, "ai_models") and sat.grows(data, "b2b_saas")
