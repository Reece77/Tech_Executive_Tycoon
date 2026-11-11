"""M23a sub-task 5 (formulas.md 39.1, 39.3; playtest 5): a country choice for new subsidiaries and
facilities, suppliers' countries wherever a supplier is listed, and tariffs carried in transfer
prices between group companies."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from tests.unit.test_m23a_group import _energy, chain, found
from tst.balance import m21
from tst.sim.fabs import market as fm
from tst.sim.fabs.actions import BuildFab
from tst.sim.geopolitics import world
from tst.sim.ledger import TARIFFS


def test_a_subsidiary_sits_in_the_country_chosen() -> None:
    lg = m21.loaded()
    game = m21.game_at(1, m21.ym_to_turn(2016, 1))
    sub = _found_in(game, "Tokyo Chips", "east_asia", "japan")
    company = game.state.company(sub)
    assert world.company_country(game.state, company, lg.balance, lg.game_data) == "japan"
    default = found(game, "Default Chips", "east_asia")
    dflt = game.state.company(default)
    assert world.company_country(game.state, dflt, lg.balance, lg.game_data) == "china"


def _found_in(game, name: str, region: str, country: str) -> int:  # type: ignore[no-untyped-def]
    from tests.unit.test_m23a_group import SUB_CENTS, _stage3
    from tst.sim.mining.actions import FoundSubsidiary

    _stage3(game)
    _energy(game)
    before = {c.id for c in game.state.companies}
    ok = game.act(FoundSubsidiary(game.founder_id, name, region, SUB_CENTS, country=country))
    if not ok:
        return 0
    (cid,) = {c.id for c in game.state.companies} - before
    return cid


def test_a_country_outside_the_region_is_refused() -> None:
    game = m21.game_at(1, m21.ym_to_turn(2016, 1))
    assert _found_in(game, "Wrong Place", "east_asia", "us") == 0
    _energy(game)
    assert not game.act(BuildFab(game.founder_id, "n28", "east_asia", 10_000, country="germany"))


def test_a_fab_in_taiwan_is_not_under_chinas_tool_controls() -> None:
    """October 2022: tools for a 7 nm fab in China need a licence; in Taiwan they do not."""
    lg = m21.loaded()
    game = m21.game_at(1, m21.ym_to_turn(2023, 1))
    _energy(game)
    assert not game.act(BuildFab(game.founder_id, "n7", "east_asia", 10_000, duv=True))
    _energy(game)
    fid = game.state.next_ids.facility
    assert game.act(
        BuildFab(game.founder_id, "n7", "east_asia", 10_000, duv=True, country="taiwan")
    ), dict(game.refused)
    f = game.state.facility(fid)
    assert f is not None and world.facility_country(game.state, f, lg.game_data) == "taiwan"


def test_suppliers_are_listed_with_their_country() -> None:
    from tst.api.commodity_views import supplier_country_label

    d = m21.loaded().game_data
    assert supplier_country_label(d, "dowa", "east_asia") == "Japan"
    assert supplier_country_label(d, "chalco", "east_asia") == "China"


def test_intra_group_chips_carry_the_border_tariff_in_their_transfer_price() -> None:
    """2019: a China fab subsidiary supplying its US parent's SoC: the parent pays the Section
    301 chips rate (25%) on the transfer price as it imports the starts."""
    game, co, ids = chain(start=(2019, 1))
    for _ in range(3):
        game.turn()
    before = dict(game.balances)
    game.turn()
    month = replace(game.state, turn=game.state.turn - 1)
    fab = fm.fab_of(month, ids["fab"])
    assert fab is not None and fab.month is not None
    price = next(p for cid, _, p, _ in fab.month.group if cid == co["device"])
    assert price > 0
    paid = game.balances.get((co["device"], TARIFFS), 0) - before.get((co["device"], TARIFFS), 0)
    border = round(Fraction(round(price)) * Fraction("0.25"))
    assert paid >= border  # the border tariff, and any on the devices' own sales
    assert game.balances.get((co["fab"], TARIFFS), 0) == before.get((co["fab"], TARIFFS), 0)


@pytest.mark.parametrize("country", ["japan", "south_korea"])
def test_a_refinery_built_in_a_chosen_country(country: str) -> None:
    from tst.balance import m20
    from tst.sim.refining.actions import BuildRefinery

    lg = m20.loaded()
    game = m20.game_at(1, m20.ym_to_turn(2016, 1))
    _energy(game)
    fid = game.state.next_ids.facility
    assert game.act(
        BuildRefinery(game.founder_id, "ree_separator", "east_asia", 1_000, country=country)
    ), dict(game.refused)
    f = game.state.facility(fid)
    assert f is not None and world.facility_country(game.state, f, lg.game_data) == country
