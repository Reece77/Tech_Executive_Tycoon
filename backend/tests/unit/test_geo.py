"""M9 cities, HQ, market rates and offices (docs/formulas.md 19.1-19.2)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, with_employee
from tst.loader import LoadedData
from tst.sim.data_models import DEFAULT_DIFFICULTY
from tst.sim.geo.cities import home_city, home_region, hq_city, work_city
from tst.sim.org.morale import market_mid_for
from tst.sim.people.founder import FounderSpec
from tst.sim.setup import new_game
from tst.sim.state import GameState, with_company

BAND_MID = 9_000_000  # software engineer, mid level


def _with_engineer(loaded: LoadedData, region: str = "north_america") -> GameState:
    state = fresh_game(loaded)
    person = replace(make_person(loaded, 2), region=region)
    return with_employee(loaded, state, person, 9_000_000)


def test_new_game_hq_defaults_to_san_francisco(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    assert state.player.hq_city == "san_francisco"
    assert home_region(state, loaded.balance, loaded.game_data) == "north_america"
    founder = state.founder_of(1)
    assert founder is not None and founder.city == "san_francisco"


def test_new_game_with_another_hq(loaded: LoadedData) -> None:
    scenario = loaded.game_data.scenario("ex_big_tech_founders")
    assert scenario is not None
    state, _ = new_game(
        save_name="t",
        master_seed=3,
        scenario=scenario,
        difficulty=DEFAULT_DIFFICULTY,
        company_name="Co",
        founder=FounderSpec(background="engineer"),
        balance=loaded.balance,
        data=loaded.game_data,
        hq_city="berlin",
    )
    assert home_region(state, loaded.balance, loaded.game_data) == "europe"
    # The home region's markets are v1's; North America is a regional market at 1/0.8.
    smb = state.market("b2b_saas", "smb")
    na = state.regional_market("b2b_saas", "smb", "north_america")
    assert smb is not None and na is not None
    assert smb.addressable == pytest.approx(400_000)
    assert na.addressable == pytest.approx(500_000)
    assert state.regional_market("b2b_saas", "smb", "europe") is None


def test_v1_people_live_in_their_regions_first_city(loaded: LoadedData) -> None:
    data = loaded.game_data
    person = make_person(loaded, 2)
    assert person.city is None or person.city == "san_francisco"
    for region, city in (
        ("north_america", "san_francisco"),
        ("europe", "london"),
        ("east_asia", "shenzhen"),
        ("south_southeast_asia", "bangalore"),
        ("latin_america", "sao_paulo"),
        ("oceania", "sydney"),
        ("africa", "london"),
    ):
        assert home_city(replace(person, region=region, city=None), data) == city


def test_market_rate_follows_the_work_city(loaded: LoadedData) -> None:
    """In the HQ's flexible space a European engineer works in San Francisco and is rated
    there; remote, at their home city's rate (19.1)."""
    b, data = loaded.balance, loaded.game_data
    state = _with_engineer(loaded, region="europe")
    employment = state.employment_of(2)
    assert employment is not None
    assert work_city(state, employment, b, data) == "san_francisco"
    assert market_mid_for(state, employment, b, data) == BAND_MID
    remote = with_company(state, replace(state.player, work_policy="remote"))
    assert work_city(remote, employment, b, data) == "london"
    assert market_mid_for(remote, employment, b, data) == BAND_MID * 85 // 100


def test_san_francisco_hq_keeps_v1_rates_for_north_americans(loaded: LoadedData) -> None:
    """A San Francisco HQ with no offices: North American staff keep v1's market rate and
    office cost (19.1-19.2)."""
    b, data = loaded.balance, loaded.game_data
    state = _with_engineer(loaded)
    employment = state.employment_of(2)
    assert employment is not None
    v1 = BAND_MID * data.region("north_america").salary_multiplier_bp // 10_000
    assert market_mid_for(state, employment, b, data) == v1
    assert hq_city(state.player, b) == "san_francisco"
