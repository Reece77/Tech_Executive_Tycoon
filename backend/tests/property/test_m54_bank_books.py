"""M54 sub-task 3 property test (formulas.md 64.1): a bank's balance sheet balances every month, and
CET1 is computed exactly. For any accounts, beta, lending and securities shares, duration, start
year, seed and months: every entry balances; the ledger's net postings to 1060, 1310, 1320 and 2310
equal the bank's reserves, loans, securities and deposits each month; CET1 is an integer equal to
assets less deposits; and its change over the run equals the bank's income less its costs plus the
capital moved (no cent appears or vanishes)."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tests.unit.test_m54_banks import banking_line, chartered
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.finserv import banks, phase
from tst.sim.ledger import CASH, DISPOSAL
from tst.sim.rng import RngFactory

PLAYER = 1
INCOME = ("4500_interest_income", "4510_interchange", "4530_securities_gains")
COSTS = ("5500_deposit_interest", "6800_loan_losses")


@settings(
    max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    seed=st.integers(min_value=1, max_value=10_000),
    consumers=st.floats(min_value=0, max_value=500_000),
    businesses=st.floats(min_value=0, max_value=60_000),
    beta=st.floats(min_value=0.1, max_value=0.9),
    ltd=st.floats(min_value=0.0, max_value=0.8),
    sec=st.floats(min_value=0.0, max_value=0.15),
    duration=st.floats(min_value=1.0, max_value=10.0),
    year=st.integers(min_value=2012, max_value=2030),
    months=st.integers(min_value=1, max_value=30),
    capital=st.integers(min_value=0, max_value=10**11),
)
def test_bank_balance_sheet_balances(
    loaded: LoadedData,
    seed: int,
    consumers: float,
    businesses: float,
    beta: float,
    ltd: float,
    sec: float,
    duration: float,
    year: int,
    months: int,
    capital: int,
) -> None:
    b, d = loaded.balance, loaded.game_data
    start = ym_to_turn(year, 1)
    state = banking_line(replace(fresh_game(loaded), turn=start), consumers, businesses)
    state = chartered(
        state,
        reserves_cents=capital,
        capital_in_cents=capital,
        beta=beta,
        loan_to_deposit=ltd,
        securities_share=sec,
        duration=duration,
    )
    rng = RngFactory(seed)
    net = {banks.RESERVES: capital, banks.LOANS: 0, banks.SECURITIES: 0, banks.DEPOSITS: 0}
    pnl = 0
    paid_out = 0
    for k in range(months):
        state, entries, _ = phase.after_sales(replace(state, turn=start + k), rng, b, d)
        for e in entries:
            assert sum(x.amount for x in e.lines) == 0
            if e.company_id != PLAYER:
                continue
            for x in e.lines:
                if x.account in net:
                    net[x.account] += x.amount
                if x.account in INCOME or x.account in COSTS or x.account == DISPOSAL:
                    pnl -= x.amount
                if x.account == CASH and e.memo == "Dividend from the bank":
                    paid_out += x.amount
        bank = state.finserv.banks[0]
        if bank.status == "failed":
            assert bank.assets_cents == bank.deposits_cents == 0
            return
        assert net[banks.RESERVES] == bank.reserves_cents >= 0
        assert net[banks.LOANS] == bank.loans_cents >= 0
        assert net[banks.SECURITIES] == bank.securities_cents >= 0
        assert -net[banks.DEPOSITS] == bank.deposits_cents >= 0
        cet1 = bank.equity_cents
        assert isinstance(cet1, int)
        assert (
            cet1
            == bank.reserves_cents + bank.loans_cents + bank.securities_cents - bank.deposits_cents
        )
        assert cet1 == capital + pnl - paid_out
