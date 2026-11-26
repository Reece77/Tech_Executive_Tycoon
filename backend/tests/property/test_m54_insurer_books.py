"""M54 sub-tasks 4-5 property test (formulas.md 64.2-64.3): an insurer's and an acquirer's books
balance. For any policies, prices, capital, start year, seed and months: every entry balances; the
ledger's net postings to 1330 and 2320 equal the insurer's investments and reserves; own funds
change only by investment income and capital; acquiring costs are never negative."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tests.unit.test_m54_payments_insurance import line
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.finserv import insurance, phase
from tst.sim.finserv.models import Insurer, Licence
from tst.sim.rng import RngFactory

PLAYER = 1
NA = "north_america"


@settings(
    max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    seed=st.integers(min_value=1, max_value=10_000),
    property_n=st.floats(min_value=0, max_value=300_000),
    life_n=st.floats(min_value=0, max_value=100_000),
    price_mult=st.floats(min_value=0.5, max_value=2.0),
    merchants=st.floats(min_value=0, max_value=5_000),
    capital=st.integers(min_value=0, max_value=10**11),
    year=st.integers(min_value=2012, max_value=2032),
    months=st.integers(min_value=1, max_value=24),
)
def test_insurer_books_balance(
    loaded: LoadedData,
    seed: int,
    property_n: float,
    life_n: float,
    price_mult: float,
    merchants: float,
    capital: int,
    year: int,
    months: int,
) -> None:
    b, d = loaded.balance, loaded.game_data
    start = ym_to_turn(year, 1)
    state = replace(fresh_game(loaded), turn=start)
    state = line(
        state,
        9401,
        "insurance",
        {
            "ins_property": (max(1, round(10000 * price_mult)), property_n),
            "ins_life": (max(1, round(25000 * price_mult)), life_n),
        },
    )
    state = line(state, 9402, "payments", {"pay_merchants": (57500, merchants)})
    ins = Insurer(1, PLAYER, (Licence(NA, "active", 0, 0),), investments_cents=capital)
    state = replace(state, finserv=replace(state.finserv, insurers=(ins,)))
    rng = RngFactory(seed)
    net = {insurance.INVESTMENTS: capital, insurance.RESERVES: 0}
    income = 0
    for k in range(months):
        state, entries, _ = phase.after_sales(replace(state, turn=start + k), rng, b, d)
        for e in entries:
            assert sum(x.amount for x in e.lines) == 0
            if e.company_id != PLAYER:
                continue
            for x in e.lines:
                if x.account in net:
                    net[x.account] += x.amount
                if x.account == insurance.INVESTMENT_INCOME:
                    income -= x.amount
                if x.account in ("5520_interchange_fees", "5530_fraud_losses"):
                    assert x.amount >= 0
        ins = state.finserv.insurers[0]
        assert net[insurance.INVESTMENTS] == ins.investments_cents
        assert -net[insurance.RESERVES] == ins.reserves_cents >= 0
        assert ins.own_funds_cents == capital + income
