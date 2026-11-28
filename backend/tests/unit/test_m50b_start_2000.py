"""M50b (formulas.md 60.4-60.7): the 2000 start, the start-year floor, history eras, the 2000
world's own companies and their exits, the shut IPO window."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tst.balance import m50
from tst.balance.game import Game
from tst.history_coverage import coverage_problems
from tst.loader import LoadedData
from tst.sim.actions.products import launch_problems
from tst.sim.calendar import (
    END_YEAR_2008_READ,
    HISTORY_START_TURN,
    START_YEARS,
    from_2010,
    history_floor_turn,
    history_floor_year,
    start_turn_of,
    world_year_of,
    ym_to_turn,
)
from tst.sim.markets_public import ipo
from tst.sim.modes.models import world_start_turn
from tst.sim.products.models import Product
from tst.sim.research import history_eras
from tst.sim.research.models import EraArrival
from tst.sim.state import with_era_arrival

# --- The calendar and the floor ----------------------------------------------------------------


def test_january_2000_is_turn_minus_120() -> None:
    assert START_YEARS == (2000, 2008, 2010)
    assert start_turn_of(2000) == HISTORY_START_TURN == -120
    assert [history_floor_turn(t) for t in (-120, -25, -24, -1, 0, 400)] == [
        -120,
        -120,
        -24,
        -24,
        0,
        0,
    ]
    assert [world_year_of(y) for y in (2000, 2005, 2008, 2009, 2010, 2020)] == [
        2000,
        2000,
        2008,
        2008,
        2010,
        2010,
    ]


def test_a_read_from_2008_ignores_2000_to_2007() -> None:
    points = {2000: 1.0, 2004: 2.0, 2008: 3.0, 2009: 4.0, 2010: 5.0}
    assert from_2010(points, 2010.0) == {2010: 5.0}
    assert from_2010(points, 2008.0) == {2008: 3.0, 2009: 4.0, 2010: 5.0}
    assert from_2010(points, 2007.54) == {2008: 3.0, 2009: 4.0, 2010: 5.0}  # Jan 2008 mid-year
    assert from_2010(points, 2007.46) == points  # December 2007
    # a year-end reader: January 2008 reads 2007.08, December 2007 reads 2007.0
    assert from_2010(points, 2007.08, boundary_2008=END_YEAR_2008_READ) == {
        2008: 3.0,
        2009: 4.0,
        2010: 5.0,
    }
    assert from_2010(points, 2007.0, boundary_2008=END_YEAR_2008_READ) == points
    assert from_2010({2000: 1.0, 2004: 2.0}, 2009.0) == {2000: 1.0, 2004: 2.0}


@given(st.integers(min_value=-120, max_value=720))
def test_the_floor_is_the_latest_start_at_or_before(turn: int) -> None:
    floor = history_floor_turn(turn)
    assert floor <= turn
    assert floor in {start_turn_of(y) for y in START_YEARS}
    assert not any(floor < start_turn_of(y) <= turn for y in START_YEARS)


@given(
    st.dictionaries(st.integers(2000, 2030), st.floats(0, 10), min_size=1, max_size=12),
    st.floats(1999.0, 2031.0),
)
def test_a_floored_read_never_sees_before_its_start_year(
    points: dict[int, float], at: float
) -> None:
    out = from_2010(points, at)
    floor = history_floor_year(at)
    assert set(out) <= set(points)
    if any(y >= floor for y in points) and floor > START_YEARS[0]:
        assert all(y >= floor for y in out)


def test_the_coverage_check_reaches_back_to_2000() -> None:
    assert coverage_problems({"s": {2008: 1, 2009: 1, 2010: 1, 2011: 2}}, "f") == [
        "f.s starts in 2008; it needs entries from 2000"
    ]
    full = {y: 1 for y in range(2000, 2012)}
    assert coverage_problems({"s": full}, "f") == []
    assert coverage_problems({"early_scale": {2008: 0.5}}, "f") == []  # keyed by start year


# --- A 2000 game ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def game_2000() -> Game:
    return m50.start(1, 2000)


def test_a_2000_game_starts_at_minus_120(game_2000: Game) -> None:
    state = game_2000.state
    assert state.turn == -120
    assert state.mode is not None and state.mode.start_turn == -120
    assert world_start_turn(state.mode) == -120


def test_the_2000_world_has_its_own_companies_and_later_worlds_do_not(
    game_2000: Game, loaded: LoadedData
) -> None:
    own = {c.name for c in loaded.game_data.incumbents if c.history_only}
    assert {"Compaq", "Sun Microsystems", "Yahoo", "AOL", "Google"} <= own
    assert own <= {c.name for c in game_2000.state.companies}
    for year in (2008, 2010):
        assert not own & {c.name for c in m50.start(1, year).state.companies}


def test_later_launches_wait_for_their_month(game_2000: Game) -> None:
    names = {p.name for p in game_2000.state.products}
    assert "Sales Cloud" in names  # on sale in January 2000
    assert not {"iPhone", "Facebook"} & names  # 2007 and 2004


# --- History eras ------------------------------------------------------------------------------


def _product(category: str) -> Product:
    return Product(
        id=999_999,
        company_id=1,
        category=category,
        name="Test",
        status="in_development",
        quality=100.0,
        feature_points=10_000.0,
        brand=0.0,
        marketing_budget_cents=0,
        created_turn=-120,
    )


def test_cloud_hosting_is_closed_until_its_era(game_2000: Game, loaded: LoadedData) -> None:
    state, data, balance = game_2000.state, loaded.game_data, loaded.balance
    assert not history_eras.category_open(state, data, "cloud_hosting")
    assert history_eras.category_open(state, data, "b2b_saas")
    problems = launch_problems(state, _product("cloud_hosting"), balance, data)
    assert any("Public cloud era (Mar 2006" in p for p in problems)
    arrived = with_era_arrival(state, EraArrival("public_cloud", state.turn, 1, 74))
    assert history_eras.category_open(arrived, data, "cloud_hosting")
    assert history_eras.still_to_come(arrived, data)  # the other history eras


def test_history_eras_are_not_played_in_a_2008_or_2010_world(loaded: LoadedData) -> None:
    for year in (2008, 2010):
        state = m50.start(1, year).state
        assert not history_eras.still_to_come(state, loaded.game_data)
        for category in ("cloud_hosting", "devices", "social", "vehicles"):
            assert history_eras.category_open(state, loaded.game_data, category)


def test_history_eras_arrive_on_their_months_in_order(game_2000: Game, loaded: LoadedData) -> None:
    data, balance = loaded.game_data, loaded.balance
    state = replace(game_2000.state, turn=ym_to_turn(2004, 2))
    state, logs = history_eras.arrive_history_eras(state, data, balance)
    assert [a.key for a in state.era_arrivals] == ["social_networks"]
    assert [i.template for i in logs] == ["history_era_arrived"]
    # music streaming (software platform) waits for video streaming, listed before it
    late = replace(state, turn=ym_to_turn(2008, 1))
    late, _ = history_eras.arrive_history_eras(late, data, balance)
    assert {a.key for a in late.era_arrivals} == {e.key for e in data.eras.history_eras}
    assert not history_eras.still_to_come(late, data)


# --- The bust's IPO window ---------------------------------------------------------------------


def test_the_ipo_window_is_shut_mid_2000_to_2003(game_2000: Game, loaded: LoadedData) -> None:
    mh = loaded.game_data.macro_history
    assert mh is not None
    assert mh.ipo_closed_at(2000, 6) is None
    assert mh.ipo_closed_at(2000, 7) == ("2000-07", "2003-12")
    assert mh.ipo_closed_at(2003, 12) is not None and mh.ipo_closed_at(2004, 1) is None
    player = game_2000.state.player
    staged = replace(game_2000.state, turn=ym_to_turn(2001, 6))
    staged = replace(
        staged,
        companies=tuple(
            replace(c, stage=loaded.balance.ipo.min_stage) if c.id == player.id else c
            for c in staged.companies
        ),
    )
    problem = ipo.eligibility_problem(staged, player.id, loaded.balance, loaded.game_data)
    assert problem is not None and "IPO window is shut" in problem


# --- Exits ---------------------------------------------------------------------------------------


def test_compaq_merges_into_hp_in_may_2002(loaded: LoadedData) -> None:
    game = m50.start(2, 2000)
    while game.state.turn < ym_to_turn(2002, 5):
        game.turn()
    state = game.state
    compaq = next(c for c in state.companies if c.name == "Compaq")
    assert not compaq.alive
    assert all(p.status == "retired" for p in state.company_products(compaq.id))
    hp = next(c for c in state.companies if c.name == "HPE")
    assert any(p.status == "live" for p in state.company_products(hp.id))
    moves = [m for m in state.rival_moves if m.company_id == compaq.id and m.action == "failed"]
    assert moves and "merged into HPE" in moves[-1].detail


# --- Finance rows before 2008 ------------------------------------------------------------------


def test_finance_rows_before_2008_are_read_only_before_it(loaded: LoadedData) -> None:
    fin = loaded.game_data.finserv
    assert fin is not None
    banking, payments = fin.banking, fin.payments
    assert banking.limit_at("north_america", ym_to_turn(2004, 1)) > 0
    assert banking.limit_at("north_america", ym_to_turn(2008, 1)) == 0.0  # as on main
    assert payments.interchange_at("north_america", ym_to_turn(2004, 1)) == 170
    assert payments.interchange_at("north_america", ym_to_turn(2009, 1)) == 156
