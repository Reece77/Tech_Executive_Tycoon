"""M22 at the M21 merge (formulas.md 39.3): export controls on fabs' tools. A fab order in a
restricted destination needs a tool licence for EUV nodes (euv_tools) and 16/14 nm and below
(chip_equipment); a ban or an entity listing refuses it outright."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.balance import m22
from tst.balance.game import start_game
from tst.sim.calendar import ym_to_turn
from tst.sim.errors import GeopoliticsRuleError
from tst.sim.fabs.actions import BuildFab
from tst.sim.geopolitics import fabs
from tst.sim.geopolitics.models import EntityListing, Licence
from tst.sim.state import with_licence

PLAYER = 1


def _state(year: int, month: int):  # type: ignore[no-untyped-def]
    data = m22.loaded()
    return replace(start_game(data, 1, "funded_spinout").state, turn=ym_to_turn(year, month)), data


def _check(state, data, country: str, node: str) -> None:  # type: ignore[no-untyped-def]
    fabs.check_order(state, PLAYER, country, node, False, data.balance, data.game_data)


def test_october_2022_needs_a_licence_for_advanced_fabs_in_china() -> None:
    before, data = _state(2022, 9)
    _check(before, data, "china", "n7")  # before the rules: allowed
    state = replace(before, turn=ym_to_turn(2022, 10))
    for node in ("n7", "n16"):
        with pytest.raises(GeopoliticsRuleError):
            _check(state, data, "china", node)
    _check(state, data, "china", "n28")  # a mature node: no controlled tools
    _check(state, data, "japan", "n7")  # outside the destination


def test_a_tool_licence_opens_it_until_a_ban() -> None:
    state, data = _state(2022, 10)
    licensed = with_licence(
        state,
        Licence(1, PLAYER, fabs.TOOLS, "us_oct_2022", "china", state.turn, state.turn, "approved"),
    )
    _check(licensed, data, "china", "n16")
    banned = replace(licensed, turn=ym_to_turn(2024, 12))  # the December 2024 ban
    with pytest.raises(GeopoliticsRuleError):
        _check(banned, data, "china", "n16")


def test_a_listed_company_gets_no_advanced_tools_anywhere() -> None:
    state, data = _state(2021, 1)
    listed = replace(state, entity_listings=(EntityListing(PLAYER, "us", state.turn, "t"),))
    with pytest.raises(GeopoliticsRuleError):
        _check(listed, data, "japan", "n7")
    _check(listed, data, "japan", "n28")


def test_the_build_action_is_checked() -> None:
    from tst.sim.actions import apply_action
    from tst.sim.rng import RngFactory

    data = m22.loaded()
    g, _ = m22.accelerator_company(1, data, ym_to_turn(2023, 1))
    action = BuildFab(g.founder_id, "n7", "east_asia", 20_000)  # East Asia's default: China
    with pytest.raises(GeopoliticsRuleError):
        apply_action(
            g.state, action, RngFactory(1), data.balance, data.game_data, g.balances, seq=1
        )


def test_request_a_tool_licence() -> None:
    data = m22.loaded()
    g, _ = m22.accelerator_company(1, data, ym_to_turn(2022, 10))
    assert g.act(fabs.RequestToolLicence(g.founder_id, "china"))
    [x] = [x for x in g.state.licences if x.product_id == fabs.TOOLS]
    assert x.rule_key == "us_oct_2022" and x.status == "pending"
