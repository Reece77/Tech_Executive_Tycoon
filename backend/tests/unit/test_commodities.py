"""M17 sub-tasks 1-2 (docs/formulas.md 33.1, 33.5): commodity and power goods follow history
to December 2025 on every seed, then a seeded path with shocks; `price` and `deck` (the
interface for M18) never look ahead."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.balance.game import start_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.commodities import commodity
from tst.sim.commodities.config import AnnualHistory
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

LAST_HISTORY = ym_to_turn(2025, 12)


def _walk(loaded: LoadedData, seed: int, first: int, last: int) -> list[GameState]:
    """Phase 4's commodity months from `first` to `last`, month by month."""
    state = start_game(loaded, seed=seed).state
    rng = RngFactory(seed)
    out = []
    for turn in range(first, last + 1):
        state = replace(state, turn=turn)
        state = replace(
            state, supply=commodity.months(state, rng, loaded.balance, loaded.game_data)
        )
        out.append(state)
    return out


def test_history_holds_annual_values_and_shock_months(loaded: LoadedData) -> None:
    h = loaded.game_data.commodity_history
    assert h is not None
    li = h.good("lithium_carbonate")
    assert li.value_at(ym_to_turn(2015, 6)) == 6500  # held for the year
    assert li.value_at(ym_to_turn(2022, 11)) == 80000  # the November 2022 peak
    assert li.value_at(ym_to_turn(2024, 3)) == 11800
    neon = h.good("neon")
    assert neon.value_at(ym_to_turn(2021, 6)) == 1.0
    assert neon.value_at(ym_to_turn(2022, 4)) == pytest.approx(10.0)
    assert neon.value_at(ym_to_turn(2022, 12)) == pytest.approx(2.0)
    assert neon.value_at(ym_to_turn(2023, 1)) == 1.2
    # the index is price / the 2010-2019 mean, so 1.0 is normal (33.1)
    assert li.mean_2010_2019 == pytest.approx(8967.0)
    assert li.long_run == 11800  # the 2015-2025 median


def test_loader_rejects_a_missing_year() -> None:
    years = {y: (1.0, "V") for y in range(2010, 2026) if y != 2017}
    with pytest.raises(ValueError, match="no value"):
        AnnualHistory(key="x", years=years)


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_history_equals_the_file_on_every_seed(loaded: LoadedData, seed: int) -> None:
    """33.6 target 1: every good's monthly price equals the history file through 2025."""
    d = loaded.game_data
    assert d.commodity_history is not None and d.power_history is not None
    for state in _walk(loaded, seed, 0, LAST_HISTORY)[::7]:
        for g in d.commodity_history.goods:
            month = state.good_month(g.key)
            assert month is not None
            assert month.index * g.mean_2010_2019 == pytest.approx(g.value_at(state.turn))
            assert month.allocation == g.allocation_at(state.turn)
        for r in d.power_history.regions:
            power = state.good_month(commodity.power_key(r.key))
            assert power is not None and power.index == pytest.approx(r.value_at(state.turn))


def test_seeded_path_is_deterministic_and_seed_dependent(loaded: LoadedData) -> None:
    first = ym_to_turn(2026, 1)
    last = ym_to_turn(2031, 12)
    a = [s.supply for s in _walk(loaded, 5, LAST_HISTORY, last)]
    b = [s.supply for s in _walk(loaded, 5, LAST_HISTORY, last)]
    c = [s.supply for s in _walk(loaded, 6, LAST_HISTORY, last)]
    assert a == b
    assert a[first - LAST_HISTORY] != c[first - LAST_HISTORY]
    north = [
        g.index for months in a for g in months if g.good == commodity.power_key("north_america")
    ]
    assert set(north) == {1.0}  # North America stays 1.0 (33.5)


def test_shocks_start_after_2025_and_cut_allocation(loaded: LoadedData) -> None:
    """A seeded shock raises the price while it runs and cuts spot allocation (33.1)."""
    states = _walk(loaded, 3, LAST_HISTORY, ym_to_turn(2039, 12))
    shocks = [
        g
        for s in states
        for g in s.supply
        if g.shock_kind is not None and g.shock_turn == s.turn and not commodity.is_power(g.good)
    ]
    assert shocks, "no shock in fourteen years"
    kinds = {g.shock_kind for g in shocks}
    assert kinds <= {"export_ban", "demand_boom", "supply_disruption"}
    g = shocks[0]
    assert g.index == pytest.approx(g.base * (1 + g.shock_rise))
    assert g.allocation == g.shock_allocation < 1.0 or g.shock_allocation == 1.0


def test_export_bans_are_likelier_where_one_country_dominates(loaded: LoadedData) -> None:
    cb = loaded.balance.commodity
    gallium = dict(commodity.shock_chances(cb, 0.99))
    tin = dict(commodity.shock_chances(cb, 0.24))
    assert gallium["export_ban"] == pytest.approx(3 * tin["export_ban"])
    assert gallium["demand_boom"] == tin["demand_boom"]


def test_price_and_deck_never_look_ahead(loaded: LoadedData) -> None:
    d, b = loaded.game_data, loaded.balance
    state = start_game(loaded, seed=1).state
    state = replace(state, turn=ym_to_turn(2022, 11))
    assert commodity.price(state, "lithium_carbonate", state.turn, d, b) == pytest.approx(80000)
    assert commodity.price(state, "copper", ym_to_turn(2015, 1), d, b) == pytest.approx(249.5)
    with pytest.raises(commodity.FutureMonthError):
        commodity.price(state, "copper", state.turn + 1, d, b)
    poly = commodity.price(state, "polysilicon", ym_to_turn(2015, 1), d, b)
    assert poly == pytest.approx(16 * b.commodity.semi_poly_multiple)  # semiconductor grade
    deck = commodity.deck(state, "lithium_carbonate", d, b)
    assert deck.current == pytest.approx(80000)
    assert deck.long_run == 11800
    assert deck.volume_unit == "t" and deck.current_usd == pytest.approx(80000)
    copper = commodity.deck(state, "copper", d, b)
    assert copper.current_usd == pytest.approx(copper.current * 22.046)


def test_price_after_2025_is_the_current_month_only(loaded: LoadedData) -> None:
    d, b = loaded.game_data, loaded.balance
    state = _walk(loaded, 2, LAST_HISTORY, ym_to_turn(2026, 3))[-1]
    now = commodity.price(state, "tin", state.turn, d, b)
    month = state.good_month("tin")
    assert month is not None
    assert now == pytest.approx(month.index * d.commodity_history.good("tin").mean_2010_2019)  # type: ignore[union-attr]
    with pytest.raises(commodity.FutureMonthError):
        commodity.price(state, "tin", state.turn - 1, d, b)  # a past seeded month is not held
