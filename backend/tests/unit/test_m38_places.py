"""countries.yaml's plain data apart from its geopolitics (M38 decision 16; product manager,
2026-11-16): GameData.places carries every country's region, demand share and default, and the
file's sites and rivals, without blocs; M38's subsidies read it, so they are the same with
geopolitics off (M22 target 7's counterfactual)."""

from __future__ import annotations

from tst.loader import LoadedData
from tst.sim.geopolitics.config import PlaceDef
from tst.sim.vehicles import subsidies


def test_places_are_the_countries_without_geopolitics(loaded: LoadedData) -> None:
    d = loaded.game_data
    assert d.countries is not None and d.places is not None
    assert [p.key for p in d.places.places] == [c.key for c in d.countries.countries]
    for c in d.countries.countries:
        p = d.places.place(c.key)
        assert p is not None
        assert (p.label, p.aliases, p.region, p.demand_share, p.default) == (
            c.label,
            c.aliases,
            c.region,
            c.demand_share,
            c.default,
        )
    assert d.places.sites == d.countries.sites and d.places.rivals == d.countries.rivals
    assert not {"bloc", "bloc_history", "tension_history"} & set(PlaceDef.model_fields)


def test_subsidy_shares_hold_without_geopolitics(loaded: LoadedData) -> None:
    d = loaded.game_data
    off = d.model_copy(update={"countries": None, "controls": None, "tariffs": None})
    assert d.places is not None
    for p in d.places.places:
        assert subsidies.country_share(p.key, off) == subsidies.country_share(p.key, d)
        assert subsidies.country_share(p.key, d) == p.demand_share
