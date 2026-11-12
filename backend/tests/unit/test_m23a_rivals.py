"""M23a sub-task 4 (formulas.md 39.3; playtest 5: "rivals should also be affected"): rivals in a
rule's jurisdiction lose restricted sales as the player does, selling only through history's
compliant variants (NVIDIA's A800 and H20); the demand they lose goes to products free there (a
Chinese accelerator maker); a software-only company plays exactly as before."""

from __future__ import annotations

from dataclasses import replace
from functools import cache

import pytest

from tst.balance import m22
from tst.balance.game import Game, start_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.geopolitics import sales


@cache
def _uncontrolled() -> LoadedData:
    lg = m22.loaded()
    geo = lg.balance.geopolitics.model_copy(update={"rivals_controlled": False})
    return replace(lg, balance=lg.balance.model_copy(update={"geopolitics": geo}))


def _nvidia(state):  # type: ignore[no-untyped-def]
    company = next(c for c in state.companies if c.name == "NVIDIA")
    return next(
        p for p in state.company_products(company.id) if p.category == "chips_ai_accelerator"
    )


@pytest.mark.parametrize(
    ("ym", "blocked", "variant"),
    [
        ((2022, 9), False, False),  # before October 2022's rules
        ((2022, 10), True, False),  # restricted, no variant yet
        ((2023, 1), True, True),  # the A800
        ((2023, 11), True, False),  # October 2023 voids variants launched before it
        ((2024, 6), True, True),  # the H20
        ((2025, 6), True, False),  # April 2025's H20 rule voids it
    ],
)
def test_nvidia_in_china_follows_history(ym: tuple[int, int], blocked: bool, variant: bool) -> None:
    lg = m22.loaded()
    b, d = lg.balance, lg.game_data
    state = replace(start_game(lg, 1, "funded_spinout").state, turn=ym_to_turn(*ym))
    a = sales.access(state, _nvidia(state), "east_asia", b, d)
    assert (a.blocked > 0) == blocked
    assert (a.variant > 0) == variant
    assert sales.access(state, _nvidia(state), "north_america", b, d).free
    off = _uncontrolled()
    assert sales.access(state, _nvidia(state), "east_asia", off.balance, off.game_data).free


def _play(lg: LoadedData, start: tuple[int, int], months: int) -> Game:
    g = start_game(lg, 1, "funded_spinout")
    g.state = replace(g.state, turn=ym_to_turn(*start))
    for _ in range(months):
        g.turn()
    return g


def _east_asia_customers(g: Game, name: str) -> float:
    company = next((c for c in g.state.companies if c.name == name), None)
    if company is None:
        return 0.0
    return sum(
        r.customers
        for p in g.state.company_products(company.id)
        for r in g.state.regional_segments_of(p.id, "east_asia")
    )


def test_nvidia_loses_china_and_a_chinese_rival_gains() -> None:
    on = _play(m22.loaded(), (2018, 9), 55)  # to April 2023: the Huawei entrant, then the rules
    off = _play(_uncontrolled(), (2018, 9), 55)
    assert _east_asia_customers(on, "NVIDIA") < _east_asia_customers(off, "NVIDIA")
    assert _east_asia_customers(on, "Huawei Ascend") > _east_asia_customers(off, "Huawei Ascend")


def test_a_software_only_company_plays_exactly_as_before() -> None:
    """The funded spin-out (software, no chips) from September 2022 through 2023: every one of
    its own records is the same with rivals controlled or not."""
    on = _play(m22.loaded(), (2022, 9), 16)
    off = _play(_uncontrolled(), (2022, 9), 16)
    player = on.state.player.id
    assert on.state.player == off.state.player
    assert on.state.company_products(player) == off.state.company_products(player)
    own = [
        s for s in on.state.product_segments if on.state.product(s.product_id).company_id == player
    ]  # type: ignore[union-attr]
    own_off = [
        s
        for s in off.state.product_segments
        if off.state.product(s.product_id).company_id == player
    ]  # type: ignore[union-attr]
    assert own == own_off
    assert {k: v for k, v in on.balances.items() if k[0] == player} == {
        k: v for k, v in off.balances.items() if k[0] == player
    }
    assert [s for s in on.snapshots] == [s for s in off.snapshots]


def test_a_chinese_supplier_signs_no_gallium_offtake_into_a_ban() -> None:
    """December 2024: China bans gallium exports to the US. Chalco (China) cannot sign a new
    offtake with a US buyer; Dowa (Japan) can."""
    from tst.sim.actions import apply_action
    from tst.sim.actions.commodities import SignOfftake
    from tst.sim.rng import RngFactory
    from tst.sim.state import with_person_state

    lg = m22.loaded()
    state = replace(start_game(lg, 1, "funded_spinout").state, turn=ym_to_turn(2025, 1))
    founder = state.founder_of(state.player.id)
    assert founder is not None
    state = with_person_state(state, replace(state.person_state(founder.id), energy=100))
    cash = {(state.player.id, "1000_cash"): 10**12}

    def sign(supplier: str) -> bool:
        try:
            apply_action(
                state,
                SignOfftake(founder.id, "gallium", supplier, 3, 1.0, 0.0),
                RngFactory(1),
                lg.balance,
                lg.game_data,
                cash,
                seq=1,
            )
        except Exception as exc:
            return "cannot sell" not in str(exc)
        return True

    assert not sign("chalco")
    assert sign("dowa")
