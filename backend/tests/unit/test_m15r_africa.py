"""M15r addendum c (playtest 4: "Why are there no offices to lease in Africa?"): Lagos,
Nairobi and Cape Town, priced in line with the region, and an office leases there."""

from __future__ import annotations

from tests.helpers import fresh_game
from tests.unit.test_geo import FOUNDER, _run
from tst.loader import LoadedData
from tst.sim.actions.geo import LeaseOffice

AFRICA = ("lagos", "nairobi", "cape_town")


def test_every_region_has_a_city_and_africa_has_three(loaded: LoadedData) -> None:
    data = loaded.game_data
    assert {c.region for c in data.cities} == set(data.region_keys)
    assert [c.key for c in data.cities if c.region == "africa"] == list(AFRICA)
    # appended: the M9 cities keep their places (their order is part of old saves)
    assert [c.key for c in data.cities][:15][-1] == "sydney"


def test_africas_cities_are_in_line_with_the_region(loaded: LoadedData) -> None:
    """Pay at or below the region's multiplier, as other emerging-market hubs (Bangalore,
    Sao Paulo) sit below theirs; rent among the cheapest hubs; small talent pools."""
    data = loaded.game_data
    region_bp = data.region("africa").salary_multiplier_bp
    bangalore, sao_paulo = data.city("bangalore"), data.city("sao_paulo")
    for key in AFRICA:
        city = data.city(key)
        assert bangalore.salary_multiplier_bp <= city.salary_multiplier_bp <= region_bp
        assert bangalore.rent_index <= city.rent_index <= sao_paulo.rent_index
        assert 1 <= city.talent_weight <= 2


def test_an_office_leases_in_lagos(loaded: LoadedData) -> None:
    state = _run(loaded, fresh_game(loaded), LeaseOffice(FOUNDER, "lagos", 25))
    offices = state.company_offices(1)
    assert [o.city for o in offices] == ["lagos"] and offices[0].status == "open"
