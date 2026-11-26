"""M54 sub-task 3 (formulas.md 64.1): banks' deposits, income, capital, stress tests and runs."""

from __future__ import annotations

from dataclasses import replace

import pytest

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.errors import FinservRuleError
from tst.sim.finserv import banks, phase
from tst.sim.finserv.actions import ApplyCharter, PartnerBank, SetBank, apply_finserv
from tst.sim.finserv.models import Bank, SecurityLot
from tst.sim.ledger import CASH
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_product, with_segments

PLAYER = 1
NA = "north_america"
BANK_LINE = 9101


def banking_line(state: GameState, consumers: float, businesses: float) -> GameState:
    p = Product(
        id=BANK_LINE,
        company_id=PLAYER,
        category="banking",
        name="Player Bank",
        status="live",
        quality=60.0,
        feature_points=0.0,
        brand=50.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )
    rows = [
        ProductSegment(BANK_LINE, "bank_consumer", 800, consumers),
        ProductSegment(BANK_LINE, "bank_business", 6000, businesses),
    ]
    return with_segments(with_product(state, p), rows, [])


def chartered(state: GameState, **changes: object) -> GameState:
    bank = Bank(  # type: ignore[arg-type]
        id=1, company_id=PLAYER, region=NA, status="chartered", applied_turn=0, **changes
    )
    return replace(state, finserv=replace(state.finserv, banks=(bank,)))


def test_a_charter_needs_a_fintech_or_banking_line_and_takes_its_months(
    loaded: LoadedData,
) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2019, 1))
    founder = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    cash = {(PLAYER, CASH): 10**12}
    with pytest.raises(FinservRuleError):
        apply_finserv(state, ApplyCharter(founder, NA), cash, b, d)
    state = banking_line(state, 0.0, 0.0)
    out = apply_finserv(state, ApplyCharter(founder, NA), cash, b, d)
    bank = out.state.finserv.banks[0]
    assert bank.status == "applying"
    months = d.finserv.regulators.bank[NA].charter_months  # type: ignore[union-attr]
    assert bank.charter_turn == state.turn + months
    assert bank.reserves_cents == b.finserv.bank.charter_capital_cents == bank.equity_cents
    assert all(sum(x.amount for x in e.lines) == 0 for e in out.entries)


def test_partner_bank_shares_interest_without_capital(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = banking_line(replace(fresh_game(loaded), turn=ym_to_turn(2019, 1)), 100_000.0, 5_000.0)
    founder = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    state = apply_finserv(state, PartnerBank(founder, NA), {}, b, d).state
    rng = RngFactory(3)
    fees = 0
    for k in range(12):
        s = replace(state, turn=ym_to_turn(2019, 1) + k)
        state, entries, _ = phase.after_sales(s, rng, b, d)
        fees += sum(
            x.amount
            for e in entries
            for x in e.lines
            if x.account == CASH and e.company_id == PLAYER
        )
    bank = state.finserv.banks[0]
    assert bank.status == "partner" and bank.deposits_cents > 0
    assert (
        bank.reserves_cents == bank.loans_cents == bank.securities_cents == 0
    )  # held at the partner
    assert fees > 0


def test_a_chartered_bank_balances_and_earns_a_margin(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    start = ym_to_turn(2016, 1)
    state = banking_line(replace(fresh_game(loaded), turn=start), 200_000.0, 20_000.0)
    state = chartered(state, reserves_cents=10**10, capital_in_cents=10**10)
    rng = RngFactory(5)
    net: dict[str, int] = {}
    for k in range(48):
        s = replace(state, turn=start + k)
        state, entries, _ = phase.after_sales(s, rng, b, d)
        for e in entries:
            assert sum(x.amount for x in e.lines) == 0
            if e.company_id == PLAYER:
                for x in e.lines:
                    net[x.account] = net.get(x.account, 0) + x.amount
    bank = state.finserv.banks[0]
    assert net[banks.RESERVES] + 10**10 == bank.reserves_cents
    assert net[banks.LOANS] == bank.loans_cents > 0
    assert net.get(banks.SECURITIES, 0) == bank.securities_cents
    assert -net[banks.DEPOSITS] == bank.deposits_cents > 0
    assert bank.equity_cents == bank.assets_cents - bank.deposits_cents
    nims = [m.nim for m in state.finserv.bank_months if m.turn >= start + 24]
    assert 0.015 < sum(nims) / len(nims) < 0.06


def test_set_bank_bounds(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = chartered(fresh_game(loaded))
    founder = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    with pytest.raises(FinservRuleError):
        apply_finserv(state, SetBank(founder, 1, 0.95, 0.7, 0.2, 4.0), {}, b, d)
    with pytest.raises(FinservRuleError):
        apply_finserv(state, SetBank(founder, 1, 0.3, 0.8, 0.3, 4.0), {}, b, d)
    out = apply_finserv(state, SetBank(founder, 1, 0.2, 0.6, 0.3, 8.0), {}, b, d)
    assert out.state.finserv.banks[0].beta == 0.2


def test_long_securities_lose_value_when_rates_rise() -> None:
    lot = SecurityLot(10_000_000, 160, 0.1, 10.0, 0, 120)
    assert banks.lot_value_cents(lot, 0.1, 0) == 10_000_000
    assert banks.lot_value_cents(lot, 4.1, 0) == 6_000_000
    assert banks.lot_value_cents(lot, 4.1, 60) == 8_000_000  # half its duration left


def test_a_runnable_bank_runs_on_some_seed_and_a_safe_one_never(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    turn = ym_to_turn(2023, 3)
    lot = SecurityLot(60 * 10**9, 160, 0.1, 10.0, ym_to_turn(2021, 1), ym_to_turn(2031, 1))
    base = replace(fresh_game(loaded), turn=turn)
    risky = Bank(
        1,
        PLAYER,
        NA,
        "chartered",
        0,
        business_deposits_cents=90 * 10**9,
        consumer_deposits_cents=10 * 10**9,
        securities=(lot,),
        reserves_cents=5 * 10**9,
        loans=(("corporate", 40 * 10**9),),
    )
    r_pct = banks.rate_fraction(base, NA, b, d) * 100
    assert banks.run_chance(risky, r_pct, turn, b, d) > 0
    assert banks.risk_band(banks.run_chance(risky, r_pct, turn, b, d)) != "low"
    safe = replace(risky, business_deposits_cents=5 * 10**9, consumer_deposits_cents=95 * 10**9)
    assert banks.run_chance(safe, r_pct, turn, b, d) == 0
    runs = 0
    for seed in range(1, 41):
        out, entries, _ = banks._run(base, risky, RngFactory(seed), r_pct, b, d)
        if out.runs:
            runs += 1
            for e in entries:
                assert sum(x.amount for x in e.lines) == 0
            assert out.status == "failed" or out.equity_cents > 0
    assert runs > 0


def test_stress_test_runs_in_june_above_the_size_line(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    june = ym_to_turn(2018, 6)
    state = replace(fresh_game(loaded), turn=june)
    big = Bank(
        1,
        PLAYER,
        NA,
        "chartered",
        0,
        consumer_deposits_cents=1000 * 10**9,
        reserves_cents=200 * 10**9,
        loans=(("mortgage", 900 * 10**9),),
    )
    out, logs = banks._stress(state, big, RngFactory(1), 2.0, b, d)
    assert len(out.stress) == 1 and logs
    small = replace(
        big, reserves_cents=10**6, loans=(("mortgage", 10**6),), consumer_deposits_cents=10**6
    )
    out, logs = banks._stress(state, small, RngFactory(1), 2.0, b, d)
    assert not out.stress and not logs
