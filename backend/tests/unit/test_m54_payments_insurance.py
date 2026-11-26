"""M54 sub-tasks 4 and 5 (formulas.md 64.2, 64.3): payments' interchange caps, rails, fraud and the
network effect; insurers' licences, claims, float, solvency and catastrophes."""

from __future__ import annotations

from dataclasses import replace

import pytest

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.finserv import demand, gates, insurance, payments, phase
from tst.sim.finserv.actions import ApplyInsuranceLicence, LaunchNetwork, apply_finserv
from tst.sim.finserv.models import Insurer, Licence, Network
from tst.sim.ledger import CASH
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_product, with_segments

PLAYER = 1
NA = "north_america"


def line(
    state: GameState, pid: int, category: str, rows: dict[str, tuple[int, float]]
) -> GameState:
    p = Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name=f"L{pid}",
        status="live",
        quality=60.0,
        feature_points=0.0,
        brand=50.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )
    segs = [ProductSegment(pid, s, price, n) for s, (price, n) in rows.items()]
    return with_segments(with_product(state, p), segs, [])


def test_interchange_caps_follow_their_dates(loaded: LoadedData) -> None:
    d = loaded.game_data
    assert payments.interchange_bp(NA, ym_to_turn(2011, 9), d) == 156
    assert payments.interchange_bp(NA, ym_to_turn(2011, 10), d) == 132
    assert payments.interchange_bp("europe", ym_to_turn(2015, 11), d) == 56
    assert payments.interchange_bp("europe", ym_to_turn(2015, 12), d) == 24


def test_rails_take_volume_from_their_dates(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    s = fresh_game(loaded)
    asia = "south_southeast_asia"
    assert demand.rails_share(replace(s, turn=ym_to_turn(2016, 3)), asia, b, d) == 0.0
    later = demand.rails_share(replace(s, turn=ym_to_turn(2023, 6)), asia, b, d)
    assert 0.4 < later < 0.7
    assert demand.rails_share(replace(s, turn=ym_to_turn(2020, 10)), "latin_america", b, d) == 0
    after = demand.addressable(
        replace(s, turn=ym_to_turn(2024, 1)), asia, "payments", "pay_networks", b, d
    )
    gross = demand.card_volume_dollars(replace(s, turn=ym_to_turn(2024, 1)), asia, b, d)
    assert after < gross / 1e7 * b.finserv.scale  # rails took their share


def test_acquiring_pays_interchange_and_fraud(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = line(
        replace(fresh_game(loaded), turn=ym_to_turn(2012, 1)),
        9201,
        "payments",
        {"pay_merchants": (57500, 1000.0)},
    )
    entries, shown = payments.acquiring_entries(state, b, d)
    mine = [e for e in entries if e.company_id == PLAYER]
    assert len(mine) == 1 and sum(x.amount for x in mine[0].lines) == 0
    volume, fee, fraud = shown[(PLAYER, NA)]
    assert volume == payments.acquired_cents(1000.0, d)
    assert fee == round(volume * (132 + 25) / 10_000)
    assert 0 < fraud <= round(volume * 6.5 / 10_000) + 1


def test_network_acceptance_compounds_its_appeal(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    assert gates.network_appeal(0.0, b) == b.finserv.payments.appeal_range.lo
    assert (
        gates.network_appeal(0.6, b) > gates.network_appeal(0.3, b) > gates.network_appeal(0.1, b)
    )
    state = replace(fresh_game(loaded), turn=ym_to_turn(2020, 1))
    market = next(m.addressable for m in state.markets if m.segment == "pay_networks")
    state = line(state, 9202, "payments", {"pay_networks": (200000, market * 0.2)})
    net = Network(1, PLAYER, NA, state.turn)
    state = replace(state, finserv=replace(state.finserv, networks=(net,)))
    for _ in range(60):
        state = payments.networks_month(state, b, d)
    acc = state.finserv.networks[0].acceptance
    assert acc == pytest.approx(0.2**0.5, rel=0.01)


def test_launching_a_network_needs_a_payments_line(loaded: LoadedData) -> None:
    from tst.sim.errors import FinservRuleError

    b, d = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    founder = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    cash = {(PLAYER, CASH): 10**12}
    with pytest.raises(FinservRuleError):
        apply_finserv(state, LaunchNetwork(founder, NA), cash, b, d)
    state = line(state, 9203, "payments", {"pay_merchants": (57500, 0.0)})
    out = apply_finserv(state, LaunchNetwork(founder, NA), cash, b, d)
    assert out.state.finserv.networks[0].region == NA
    assert out.entries[0].lines[0].amount == b.finserv.payments.network_cost_cents


def test_an_insurer_reserves_pays_and_earns_on_its_float(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    start = ym_to_turn(2017, 1)
    state = line(
        replace(fresh_game(loaded), turn=start),
        9301,
        "insurance",
        {"ins_property": (10000, 50_000.0), "ins_life": (25000, 20_000.0)},
    )
    founder = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    cash = {(PLAYER, CASH): 10**12}
    state = apply_finserv(state, ApplyInsuranceLicence(founder, NA), cash, b, d).state
    ins = state.finserv.insurers[0]
    assert not ins.licensed(NA)
    rng = RngFactory(1)
    net: dict[str, int] = {insurance.INVESTMENTS: ins.investments_cents, insurance.RESERVES: 0}
    for k in range(36):
        state, entries, _ = phase.after_sales(replace(state, turn=start + k), rng, b, d)
        for e in entries:
            assert sum(x.amount for x in e.lines) == 0
            if e.company_id == PLAYER:
                for x in e.lines:
                    if x.account in net:
                        net[x.account] += x.amount
    ins = state.finserv.insurers[0]
    assert ins.licensed(NA)
    assert net[insurance.INVESTMENTS] == ins.investments_cents
    assert -net[insurance.RESERVES] == ins.reserves_cents > 0
    months = [m for m in state.finserv.insurance_months if m.premiums_cents]
    assert all(0.5 < m.combined_ratio < 1.2 for m in months)
    assert months[-1].investment_income_cents > 0


def test_solvency_gates_new_business(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = line(fresh_game(loaded), 9302, "insurance", {"ins_property": (10000, 100_000.0)})
    poor = Insurer(1, PLAYER, (Licence(NA, "active", 0, 0),), investments_cents=1)
    rich = replace(poor, investments_cents=10**13)
    s1 = replace(state, finserv=replace(state.finserv, insurers=(poor,)))
    s2 = replace(state, finserv=replace(state.finserv, insurers=(rich,)))
    e1 = gates.effects(None, s1, b, d)
    e2 = gates.effects(None, s2, b, d)
    assert e1 is not None and e1.appeal(9302, NA) == 0.0
    assert e2 is None or e2.appeal(9302, NA) == 1.0


def test_catastrophes_are_drawn_only_from_2026_and_stored_once_they_happen(
    loaded: LoadedData,
) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2024, 1))
    assert insurance.draw_cats(state, RngFactory(1), b, d) is state
    start = b.finserv.start_turn
    seen = 0
    for k in range(120):
        s = replace(state, turn=start + k)
        state = insurance.draw_cats(s, RngFactory(9), b, d)
        assert all(c.turn <= state.turn for c in state.finserv.world.cats)
        seen = len(state.finserv.world.cats)
    assert 3 <= seen <= 60
