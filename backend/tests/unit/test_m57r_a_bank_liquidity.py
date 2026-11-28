"""M57r-A sub-task 3 (review 10 items 6 and 9): bank liquidity and charter capital."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.errors import FinservRuleError
from tst.sim.finserv import banks
from tst.sim.finserv.actions import ApplyCharter, BankCapital, apply_finserv
from tst.sim.finserv.models import Bank, SecurityLot
from tst.sim.ledger import CASH, LedgerEntry
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

from .test_m54_banks import banking_line

PLAYER = 1
NA = "north_america"


def _reserves_moved(entries: list[LedgerEntry]) -> int:
    return sum(x.amount for e in entries for x in e.lines if x.account == banks.RESERVES)


def _run_months(
    loaded: LoadedData, bank: Bank, months: int, seed: int = 1
) -> tuple[Bank, list[Bank]]:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2022, 1))
    seen = []
    for m in range(months):
        state = replace(state, turn=ym_to_turn(2022, 1) + m)
        state = replace(state, finserv=replace(state.finserv, banks=(bank,)))
        before = bank.reserves_cents
        bank, entries, _, _ = banks.chartered_month(state, bank, RngFactory(seed), b, d)
        assert all(sum(x.amount for x in e.lines) == 0 for e in entries)
        # the books reconcile to 1060: every reserve movement is posted
        assert before + _reserves_moved(entries) == bank.reserves_cents
        seen.append(bank)
        if bank.status == "failed":
            break
    return bank, seen


def test_ordinary_outflows_sell_securities_not_go_negative(loaded: LoadedData) -> None:
    """Codex R10-03: 1e8 deposits, 7.5e7 mortgages, 2.5e7 securities and 6e6 reserves, no
    accounts left: the bank finished with -3,375,834 cents of reserves."""
    bank = Bank(
        1,
        PLAYER,
        NA,
        "chartered",
        0,
        consumer_deposits_cents=100_000_000,
        loans=(("mortgage", 75_000_000),),
        fixed_yields=(("mortgage", 400),),
        securities=(SecurityLot(25_000_000, 300, 1.0, 4.0, 0, ym_to_turn(2030, 1)),),
        reserves_cents=6_000_000,
    )
    final, seen = _run_months(loaded, bank, 36)
    assert all(x.reserves_cents >= 0 for x in seen)
    assert any(x.securities_cents < 25_000_000 for x in seen)  # it sold to pay
    if final.status != "failed":
        assert final.restricted  # forced sales restrict the bank


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    deposits=st.integers(0, 10**10),
    loans=st.integers(0, 10**10),
    securities=st.integers(0, 10**10),
    reserves=st.integers(0, 10**9),
    seed=st.integers(0, 50),
)
def test_reserves_are_never_negative(
    loaded: LoadedData, deposits: int, loans: int, securities: int, reserves: int, seed: int
) -> None:
    bank = Bank(
        1,
        PLAYER,
        NA,
        "chartered",
        0,
        consumer_deposits_cents=deposits // 2,
        business_deposits_cents=deposits - deposits // 2,
        loans=(("mortgage", loans // 2), ("consumer", loans - loans // 2)),
        fixed_yields=(("mortgage", 500),),
        securities=(SecurityLot(securities, 150, 0.5, 6.0, 0, ym_to_turn(2035, 1)),)
        if securities
        else (),
        reserves_cents=reserves,
    )
    _, seen = _run_months(loaded, bank, 12, seed)
    assert all(x.reserves_cents >= 0 for x in seen)


def _applying(loaded: LoadedData) -> tuple[GameState, dict[tuple[int, str], int]]:
    b, d = loaded.balance, loaded.game_data
    state = banking_line(replace(fresh_game(loaded), turn=ym_to_turn(2019, 1)), 0.0, 0.0)
    founder = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    cash = {(PLAYER, CASH): 10**12}
    out = apply_finserv(state, ApplyCharter(founder, NA), cash, b, d)
    return out.state, cash


def test_charter_capital_stays_while_applying(loaded: LoadedData) -> None:
    """Fable 18: 199,999,999 cents came back while the charter was pending."""
    b, d = loaded.balance, loaded.game_data
    state, cash = _applying(loaded)
    founder = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    bank = state.finserv.banks[0]
    with pytest.raises(FinservRuleError):
        apply_finserv(state, BankCapital(founder, bank.id, -199_999_999), cash, b, d)
    # chartered, the charter capital still stays
    state = replace(
        state, finserv=replace(state.finserv, banks=(replace(bank, status="chartered"),))
    )
    with pytest.raises(FinservRuleError):
        apply_finserv(state, BankCapital(founder, bank.id, -1), cash, b, d)
    # capital above it can come back
    up = apply_finserv(state, BankCapital(founder, bank.id, 10**8), cash, b, d).state
    out = apply_finserv(up, BankCapital(founder, bank.id, -(10**8)), cash, b, d)
    assert out.state.finserv.banks[0].equity_cents == b.finserv.bank.charter_capital_cents
