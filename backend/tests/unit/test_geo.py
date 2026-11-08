"""M9 cities, HQ, market rates and offices (docs/formulas.md 19.1-19.2)."""

from __future__ import annotations

import statistics
from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, with_employee
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    ActionResult,
    CreateUnit,
    MovePerson,
    OpenSearch,
    apply_action,
)
from tst.sim.actions.geo import CloseOffice, LeaseOffice, SetUnitOffice
from tst.sim.data_models import DEFAULT_DIFFICULTY
from tst.sim.errors import (
    GeoRuleError,
    InsufficientCashError,
    InvalidActionError,
    UnknownCityError,
)
from tst.sim.geo.cities import home_city, home_region, hq_city, work_city
from tst.sim.geo.models import ANYWHERE
from tst.sim.geo.offices import crowded_people, employee_office_cents
from tst.sim.hiring.phases import _relocate, monthly_costs
from tst.sim.ledger import CASH, RECRUITING, RENT
from tst.sim.org.morale import market_mid_for, morale_terms
from tst.sim.org.rules import org_view
from tst.sim.people.founder import FounderSpec
from tst.sim.people.generator import draw_city, generate_pool
from tst.sim.people.models import Employment, Person, current_ability
from tst.sim.rng import RngFactory
from tst.sim.scale import ABILITY_PER_ATTR
from tst.sim.setup import new_game
from tst.sim.state import GameState, with_company, with_employment, with_person

BAND_MID = 9_000_000  # software engineer, mid level
# geo.pay_level 0.876 x each city's multiplier, in bp (19.1)
SF_BP, LONDON_BP, BERLIN_BP = 8_760, 7_446, 5_694


def rate(bp: int) -> int:
    return BAND_MID * bp // 10_000


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
    # The home region's markets are v1's; North America is a regional market at 1/0.55 (M10d).
    smb = state.market("b2b_saas", "smb")
    na = state.regional_market("b2b_saas", "smb", "north_america")
    assert smb is not None and na is not None
    assert smb.addressable == pytest.approx(400_000)
    assert na.addressable == pytest.approx(400_000 / 0.55)
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
    assert market_mid_for(state, employment, b, data) == rate(SF_BP)
    remote = with_company(state, replace(state.player, work_policy="remote"))
    assert work_city(remote, employment, b, data) == "london"
    assert market_mid_for(remote, employment, b, data) == rate(LONDON_BP)


def test_san_francisco_pay_matches_v1s_regional_mix(loaded: LoadedData) -> None:
    """geo.pay_level: a San Francisco company's market rate is v1's average over its
    regional candidate mix (people.region_weights x regions' multipliers), within a point."""
    b, data = loaded.balance, loaded.game_data
    weights = b.people.region_weights
    v1_mix = sum(weights[r] * data.region(r).salary_multiplier_bp for r in weights) / sum(
        weights.values()
    )
    assert b.geo.pay_level == pytest.approx(v1_mix / 10_000, abs=0.01)
    state = _with_engineer(loaded)
    employment = state.employment_of(2)
    assert employment is not None
    assert market_mid_for(state, employment, b, data) == rate(SF_BP)
    assert hq_city(state.player, b) == "san_francisco"


# --- Offices (19.2) ---------------------------------------------------------------------------

FOUNDER = 1
CASH_START = 50_000_000


def _act(loaded: LoadedData, state: GameState, action: Action) -> ActionResult:
    balances = {(1, CASH): CASH_START}
    return apply_action(
        state, action, RngFactory(1), loaded.balance, loaded.game_data, balances, seq=1
    )


def _run(loaded: LoadedData, state: GameState, *actions: Action) -> GameState:
    for action in actions:
        state = _act(loaded, state, action).new_state
    return state


def _team_game(loaded: LoadedData, staff: int = 3) -> GameState:
    state = fresh_game(loaded)
    for pid in range(2, 2 + staff):
        state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000, morale=60)
    state = _run(loaded, state, CreateUnit(FOUNDER, "team", "Platform"))
    return _run(loaded, state, *(MovePerson(FOUNDER, p, 1) for p in range(2, 2 + staff)))


def test_lease_office_costs_energy_and_fit_out(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    before = state.person_state(FOUNDER).energy or 0
    out = _act(loaded, state, LeaseOffice(FOUNDER, "berlin", 50))
    office = out.new_state.company_offices(1)[0]
    assert (office.city, office.seats, office.opened_turn) == ("berlin", 50, 0)
    assert out.new_state.person_state(FOUNDER).energy == before - loaded.balance.office.lease_energy
    (entry,) = out.ledger_entries
    assert {line.account: line.amount for line in entry.lines} == {
        RENT: 3_037_500,
        CASH: -3_037_500,
    }
    assert out.log_items[0].template == "office_leased"


@pytest.mark.parametrize(
    ("action", "error"),
    [
        (LeaseOffice(FOUNDER, "atlantis", 50), UnknownCityError),
        (LeaseOffice(FOUNDER, "berlin", 40), GeoRuleError),
    ],
)
def test_lease_rules(loaded: LoadedData, action: LeaseOffice, error: type[Exception]) -> None:
    with pytest.raises(error):
        _act(loaded, fresh_game(loaded), action)


def test_lease_needs_the_fit_out_in_cash(loaded: LoadedData) -> None:
    with pytest.raises(InsufficientCashError):
        apply_action(
            fresh_game(loaded),
            LeaseOffice(FOUNDER, "london", 250),
            RngFactory(1),
            loaded.balance,
            loaded.game_data,
            {(1, CASH): 100},
            seq=1,
        )


def test_moving_a_team_to_berlin_changes_rates_costs_and_cities(loaded: LoadedData) -> None:
    """Playwright (a) in the sim: the team's market rate and office cost follow Berlin, and
    its members now live there (19.1-19.2)."""
    b, data = loaded.balance, loaded.game_data
    state = _team_game(loaded)
    state = _run(loaded, state, LeaseOffice(FOUNDER, "berlin", 25))
    office = state.company_offices(1)[0]
    unit = state.active_units(1)[0]
    employment = state.employment_of(2)
    assert employment is not None
    assert market_mid_for(state, employment, b, data) == rate(SF_BP)
    assert employee_office_cents(state, employment, b, data) == 60_000
    state = _run(loaded, state, SetUnitOffice(FOUNDER, unit.id, office.id))
    employment = state.employment_of(2)
    assert employment is not None
    assert market_mid_for(state, employment, b, data) == rate(BERLIN_BP)
    assert employee_office_cents(state, employment, b, data) == 0  # the lease covers seats
    assert state.person(2).city == "berlin"
    costs = dict((memo, amount) for memo, _, amount in monthly_costs(state, 1, b, data))
    assert costs["Rent: Berlin"] == 506_250  # 25 x $600 x 0.45 x 0.75
    assert costs["Office"] == 60_000  # only the founder's flexible seat


def test_closing_a_foreign_office_sends_its_teams_remote(loaded: LoadedData) -> None:
    b, data = loaded.balance, loaded.game_data
    state = _team_game(loaded)
    state = _run(loaded, state, LeaseOffice(FOUNDER, "berlin", 25))
    office = state.company_offices(1)[0]
    unit = state.active_units(1)[0]
    state = _run(loaded, state, SetUnitOffice(FOUNDER, unit.id, office.id))
    out = _act(loaded, state, CloseOffice(FOUNDER, office.id))
    after = out.new_state
    assert after.company_offices(1) == ()
    team = after.unit(unit.id)
    assert team is not None and (team.office_id, team.policy) == (None, "remote")
    employment = after.employment_of(2)
    assert employment is not None
    assert work_city(after, employment, b, data) == "berlin"  # remote from where they lived
    (entry,) = out.ledger_entries
    assert {line.account: line.amount for line in entry.lines}[RENT] == 3 * 506_250


def test_closing_an_hq_office_moves_its_teams_to_flexible_space(loaded: LoadedData) -> None:
    state = _team_game(loaded)
    state = _run(loaded, state, LeaseOffice(FOUNDER, "san_francisco", 25))
    office = state.company_offices(1)[0]
    unit = state.active_units(1)[0]
    state = _run(loaded, state, SetUnitOffice(FOUNDER, unit.id, office.id))
    state = _run(loaded, state, CloseOffice(FOUNDER, office.id))
    team = state.unit(unit.id)
    assert team is not None and (team.office_id, team.policy) == (None, "office")


def test_a_crowded_office_costs_four_morale(loaded: LoadedData) -> None:
    b, data = loaded.balance, loaded.game_data
    state = _team_game(loaded, staff=3)
    state = _run(loaded, state, LeaseOffice(FOUNDER, "austin", 25))
    office = state.company_offices(1)[0]
    unit = state.active_units(1)[0]
    state = _run(loaded, state, SetUnitOffice(FOUNDER, unit.id, office.id))
    employment = state.employment_of(2)
    assert employment is not None
    view = org_view(state, 1)
    assert morale_terms(state, view, employment, b, data, 0, 0).crowded == 0.0
    crowded = replace(state, offices=(replace(office, seats=2),))
    assert crowded_people(crowded, 1) == {2, 3, 4}
    terms = morale_terms(crowded, view, employment, b, data, 0, 0)
    assert terms.crowded == b.office.crowded_morale == -4


# --- Hiring by city (19.3) --------------------------------------------------------------------


def _batch(loaded: LoadedData, city: str, seed: int, count: int = 8) -> tuple[Person, ...]:
    gen = RngFactory(seed).stream(0, "misc", seed)
    levels = ["mid"] * count
    role = loaded.game_data.role("software_engineer")
    return generate_pool(
        gen, loaded.game_data, loaded.balance, 0, role, levels, first_person_id=10, city=city
    )


def role_score(person: Person, loaded: LoadedData) -> float:
    """The CA-weighted mean of the role's skills, in attribute points (19.8 target 4)."""
    return current_ability(person, loaded.game_data) / ABILITY_PER_ATTR


def test_draw_city(loaded: LoadedData) -> None:
    b, data = loaded.balance, loaded.game_data
    assert draw_city(0.0, "bangalore", b, data) == "bangalore"
    assert draw_city(0.849, "bangalore", b, data) == "bangalore"
    assert draw_city(0.85, "bangalore", b, data) == "san_francisco"  # relocators by weight
    assert draw_city(0.9999, "bangalore", b, data) == "cape_town"  # the last city (M15r)
    assert draw_city(0.0, ANYWHERE, b, data) == "san_francisco"


def test_bangalore_search_draws_local_candidates_at_local_pay(loaded: LoadedData) -> None:
    """Playwright (c) in the sim: about 85% live in Bangalore; everyone asks Bangalore pay."""
    people = [p for seed in range(1, 41) for p in _batch(loaded, "bangalore", seed)]
    local = sum(1 for p in people if p.city == "bangalore") / len(people)
    assert 0.78 < local < 0.92
    sf = [p for seed in range(1, 41) for p in _batch(loaded, "san_francisco", seed)]
    mean = statistics.fmean
    asks_blr = mean(p.salary_expectation_cents or 0 for p in people)
    asks_sf = mean(p.salary_expectation_cents or 0 for p in sf)
    assert asks_blr < 0.4 * asks_sf  # x 0.30 against x 1.00, with Bangalore's lower talent
    assert all(p.region == loaded.game_data.city(p.city or "").region for p in people)


def test_cities_differ_target_4(loaded: LoadedData) -> None:
    """19.8 target 4: over 200 seeded software-engineer searches, San Francisco candidates'
    mean role-skill score is 0.8-1.2 points above Austin's."""
    sf = [
        role_score(p, loaded)
        for seed in range(200)
        for p in _batch(loaded, "san_francisco", seed, 4)
    ]
    austin = [
        role_score(p, loaded) for seed in range(200) for p in _batch(loaded, "austin", seed, 4)
    ]
    gap = statistics.fmean(sf) - statistics.fmean(austin)
    print(f"19.8 target 4: San Francisco - Austin role-skill score = {gap:.3f}")
    assert 0.8 <= gap <= 1.2


def test_search_city_defaults_to_the_units_office(loaded: LoadedData) -> None:
    state = _team_game(loaded)
    state = _run(loaded, state, LeaseOffice(FOUNDER, "berlin", 25))
    office = state.company_offices(1)[0]
    unit = state.active_units(1)[0]
    state = _run(loaded, state, SetUnitOffice(FOUNDER, unit.id, office.id))
    state = _run(
        loaded, state, OpenSearch(FOUNDER, "software_engineer", "job_post", unit_id=unit.id)
    )
    state = _run(loaded, state, OpenSearch(FOUNDER, "software_engineer", "network"))
    first, second = state.searches
    assert (first.city, second.city) == ("berlin", "san_francisco")
    with pytest.raises(InvalidActionError):
        _act(loaded, state, OpenSearch(FOUNDER, "designer", "network", city=ANYWHERE))
    remote = with_company(state, replace(state.player, work_policy="remote"))
    out = _act(loaded, remote, OpenSearch(FOUNDER, "designer", "network", city=ANYWHERE))
    assert out.new_state.searches[-1].city == ANYWHERE


def test_a_relocating_hire_pays_the_fee_and_moves(loaded: LoadedData) -> None:
    b, data = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    person = replace(make_person(loaded, 2), city="toronto")
    hire = Employment(2, 2, 1, "software_engineer", "mid", 9_000_000, 0, 0, None, "active")
    state = with_employment(with_person(state, person), hire)
    state, entries = _relocate(state, hire, b, data)
    assert state.person(2).city == "san_francisco"
    (entry,) = entries
    assert {line.account: line.amount for line in entry.lines}[RECRUITING] == 1_500_000
    again, none = _relocate(state, hire, b, data)
    assert none == [] and again == state
