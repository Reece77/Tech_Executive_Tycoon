"""M50 (ADR-0024, formulas.md 60): negative turns, the 2008 start, 2008-2009 data."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from tst.history_coverage import coverage_problems
from tst.loader import LoadedData
from tst.sim.calendar import (
    HISTORY_START_TURN,
    START_YEARS,
    format_turn,
    from_2010,
    start_turn_of,
    turn_to_ym,
    ym_to_turn,
)
from tst.sim.dynasty.mode import standard_end_turn
from tst.sim.errors import InvalidDateError, InvalidSeedError
from tst.sim.modes.models import GameMode, began_in, world_start_turn
from tst.sim.products.formulas import expected_features
from tst.sim.products.setup import addressable_at
from tst.sim.rivals.startups import founding_turn
from tst.sim.rng import NEGATIVE_TURN_BASE, RngFactory, turn_key
from tst.sim.setup import DEFAULT_FOUNDER, new_game


def _game(loaded: LoadedData, year: int, seed: int = 7):  # type: ignore[no-untyped-def]
    sd = loaded.game_data.scenario("garage_bootstrap")
    assert sd is not None
    return new_game(
        save_name="m50",
        master_seed=seed,
        scenario=sd,
        difficulty="standard",
        company_name="M50 Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
        start_year=year,
    )


# --- The calendar and RNG (ADR-0024 1-3) ---------------------------------------------------


def test_january_2008_is_turn_minus_24() -> None:
    assert START_YEARS == (2008, 2010)
    assert start_turn_of(2008) == HISTORY_START_TURN == -24
    assert start_turn_of(2010) == 0
    assert format_turn(-24) == "Jan 2008"
    assert format_turn(-1) == "Dec 2009"
    with pytest.raises(InvalidDateError):
        start_turn_of(2009)


@given(st.integers(min_value=-24 * 12, max_value=720))
def test_turn_and_month_round_trip(turn: int) -> None:
    assert ym_to_turn(*turn_to_ym(turn)) == turn


def test_turns_from_zero_derive_exactly_as_before() -> None:
    """A 2010 game's draws are unchanged: from turn 0 the spawn key is the turn itself."""
    rng = RngFactory(42)
    for turn in (0, 1, 359, 719):
        assert turn_key(turn) == turn
        seq = np.random.SeedSequence(entropy=42, spawn_key=(turn, 2, 5))
        expected = np.random.Generator(np.random.PCG64(seq)).random(3)
        assert np.array_equal(rng.stream(turn, "hiring", 5).random(3), expected)


@given(st.integers(min_value=-600, max_value=-1), st.integers(min_value=0, max_value=10**6))
def test_negative_turns_are_seeded_and_never_meet_a_later_turn(turn: int, seed: int) -> None:
    rng = RngFactory(seed)
    a = rng.stream(turn, "market", 1).random(2)
    b = RngFactory(seed).stream(turn, "market", 1).random(2)
    assert np.array_equal(a, b)  # same seed and turn: identical draws
    assert turn_key(turn) == NEGATIVE_TURN_BASE - turn > 10**9  # far above any reachable turn
    assert not np.array_equal(a, rng.stream(-turn, "market", 1).random(2))


def test_a_turn_out_of_range_or_not_an_int_is_refused() -> None:
    with pytest.raises(InvalidSeedError):
        RngFactory(1).stream(-NEGATIVE_TURN_BASE, "market")
    with pytest.raises(InvalidSeedError):
        RngFactory(1).stream(True, "market")  # type: ignore[arg-type]


# --- The start and the end -------------------------------------------------------------------


def test_a_2008_game_starts_at_minus_24_and_records_its_start(loaded: LoadedData) -> None:
    state, entries = _game(loaded, 2008)
    assert state.turn == -24
    assert state.mode == GameMode(kind="campaign", start_turn=-24)
    assert world_start_turn(state.mode) == -24
    assert state.player.founded_turn == -24
    assert all(e.turn == -24 for e in entries)
    assert standard_end_turn(state, loaded.balance) == ym_to_turn(2038, 1)  # after Dec 2037


def test_a_2010_game_has_no_mode_as_before(loaded: LoadedData) -> None:
    state, _ = _game(loaded, 2010)
    assert state.turn == 0 and state.mode is None
    assert world_start_turn(state.mode) == 0
    assert standard_end_turn(state, loaded.balance) == 360


def test_the_prompt_says_when_the_game_began() -> None:
    text = "a game that began in January 2010."
    assert began_in(text, None) == text
    assert began_in(text, GameMode(kind="campaign", start_turn=-24)) == text.replace("2010", "2008")
    assert began_in(text, GameMode(kind="sandbox", start_turn=60)) == text


# --- Markets and incumbents in 2008 ----------------------------------------------------------


def test_2008_demand_grows_back_to_d0_by_2010(loaded: LoadedData) -> None:
    data = loaded.game_data
    for cat in data.categories:
        for m in cat.markets:
            back = addressable_at(data, cat.key, m.segment, -24)
            g = (1 + cat.growth_in(2008)) * (1 + cat.growth_in(2009))
            assert back * g == pytest.approx(m.addressable, rel=1e-9)
            assert addressable_at(data, cat.key, m.segment, 0) == m.addressable


def test_expected_features_stay_positive_and_rising_before_2010(loaded: LoadedData) -> None:
    for cat in loaded.game_data.categories:
        if cat.features_per_month <= 0:
            continue
        values = [expected_features(cat, t) for t in range(-24, 13)]
        assert all(v > 0 for v in values)
        assert values == sorted(values)
        assert expected_features(cat, 0) == cat.features_at_start


def test_later_launches_are_missing_at_the_start_and_join_on_their_month(
    loaded: LoadedData,
) -> None:
    from tst.sim.rivals.launches import incumbent_launches

    state, _ = _game(loaded, 2008)
    names = {p.name for p in state.products}
    assert "GitHub" not in names and "Windows Azure" not in names and "Facebook" in names
    in_2010, _ = _game(loaded, 2010)
    assert {"GitHub", "Windows Azure"} <= {p.name for p in in_2010.products}
    joined = incumbent_launches(
        replace(state, turn=ym_to_turn(2008, 3)), loaded.balance, loaded.game_data
    )
    github = next(p for p in joined.products if p.name == "GitHub")
    assert github.launched_turn == ym_to_turn(2008, 4)
    assert all(s.customers == 0 for s in joined.segments_of(github.id))
    azure = incumbent_launches(replace(state, turn=-1), loaded.balance, loaded.game_data)
    product = next(p for p in azure.products if p.name == "Windows Azure")
    assert sum(s.customers for s in azure.segments_of(product.id)) > 0  # its 2010 share
    github_co = next(c for c in state.companies if c.name == "GitHub")
    assert github_co.alive


def test_facebook_starts_2008_at_its_early_scale(loaded: LoadedData) -> None:
    early, _ = _game(loaded, 2008)
    late, _ = _game(loaded, 2010)

    def customers(state, name):  # type: ignore[no-untyped-def]
        p = next(p for p in state.products if p.name == name)
        return sum(s.customers for s in state.segments_of(p.id))

    assert customers(early, "Facebook") == pytest.approx(0.17 * customers(late, "Facebook"))


def test_square_is_founded_on_its_real_month_only_in_an_earlier_world(
    loaded: LoadedData,
) -> None:
    square = next(e for e in loaded.game_data.entrants if e.name == "Square")
    assert founding_turn(square, -24) == ym_to_turn(2009, 2)
    assert founding_turn(square, 0) == ym_to_turn(2010, 3)
    airbnb = next(e for e in loaded.game_data.entrants if e.name == "Airbnb")
    assert founding_turn(airbnb, 0) < 0  # a 2010 game never reaches it


# --- Data coverage (ADR-0024 4) --------------------------------------------------------------


def test_every_series_reaches_back_to_2008(loaded: LoadedData) -> None:
    """The loader's check passed on load; categories list 2008-2009 growth."""
    assert all(sorted(c.early_growth) == [2008, 2009] for c in loaded.game_data.categories)


def test_the_coverage_check_rejects_gaps() -> None:
    assert coverage_problems({"s": {2010: 1, 2011: 2}}, "f") == [
        "f.s starts in 2010; it needs entries from 2008"
    ]
    assert coverage_problems({"s": {2008: 1, 2010: 1, 2011: 2}}, "f") == [
        "f.s has no entry for [2009]"
    ]
    assert coverage_problems({"s": {2008: 1, 2010: 1, 2015: 2}}, "f") == []  # sparse
    assert coverage_problems({"s": {2017: 1, 2018: 2}}, "f") == []  # begins later
    assert coverage_problems({"s": [["2010-01", 1]]}, "f") == [
        "f.s starts in 2010-01; it needs entries from 2008-01"
    ]
    assert coverage_problems({"s": {"2008-01": 1, "2010-01": 2}}, "f") == []
    assert coverage_problems({"growth_by_year": {2010: 1}}, "f") == []  # exempt


def test_a_read_from_2010_ignores_2008_and_2009() -> None:
    points = {2008: 1.0, 2009: 2.0, 2010: 3.0, 2012: 5.0}
    assert from_2010(points, 2010.0) == {2010: 3.0, 2012: 5.0}
    assert from_2010(points, 2009.54) == {2010: 3.0, 2012: 5.0}  # January 2010 mid-year
    assert from_2010(points, 2009.46) == points  # December 2009
    assert from_2010({2011: 1.0}, 2012.0) == {2011: 1.0}


def test_an_active_strategy_plays_from_2008_into_2010() -> None:
    """A founder who hires, raises and is poached from plays 2008-2009 (target 4's run found a
    negative month in an RNG key); the ledger balances every month."""
    from tst.balance import m50
    from tst.balance.strategies_v2 import STRATEGIES

    game = m50.start(3, 2008)
    script = STRATEGIES["blitzscale"]
    while game.state.turn < 2 and not game.state.ended:
        script(game)
        game.turn()
        assert game.last_result is not None
        assert all(sum(ln.amount for ln in e.lines) == 0 for e in game.last_result.ledger_entries)
    assert game.state.turn == 2 or game.state.ended
