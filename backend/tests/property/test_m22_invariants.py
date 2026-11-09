"""M22 (formulas.md 39.3): the ledger balances with tariffs. For any start year, contract size and
number of months, a China-assembled device company's books move cash by exactly its postings,
its tariffs are never negative, and every tariff equals the schedule's rate on the cost of the
units made in China and sold in the taxing market."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tst.balance import m12b, m22
from tst.sim.calendar import ym_to_turn
from tst.sim.decisions import Decisions
from tst.sim.geopolitics import tariffs
from tst.sim.ledger import CASH, TARIFFS, apply_entries
from tst.sim.rng import RngFactory
from tst.sim.turn import advance_turn

PLAYER = 1


@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    year=st.integers(min_value=2016, max_value=2025),
    units=st.integers(min_value=2_000, max_value=60_000),
    months=st.integers(min_value=1, max_value=4),
)
def test_tariffs_keep_the_ledger_balanced(year: int, units: int, months: int) -> None:
    data = m22.loaded()
    m12b._loaded = lambda: data  # type: ignore[assignment]
    g, pid = m12b.device_company(3, own_chip=False, start=ym_to_turn(year, 1), units=units)
    for _ in range(months):
        result = advance_turn(
            g.state, Decisions(), RngFactory(3), data.balance, data.game_data, g.balances
        )
        for e in result.ledger_entries:
            assert sum(line.amount for line in e.lines) == 0
        cash = sum(
            line.amount
            for e in result.ledger_entries
            if e.company_id == PLAYER
            for line in e.lines
            if line.account == CASH
        )
        before = g.balances.get((PLAYER, CASH), 0)
        g.balances = apply_entries(g.balances, result.ledger_entries)
        assert g.balances.get((PLAYER, CASH), 0) - before == cash
        taxed = [
            line.amount
            for e in result.ledger_entries
            if e.company_id == PLAYER
            for line in e.lines
            if line.account == TARIFFS
        ]
        assert all(x > 0 for x in taxed)
        settled = replace(result.new_state, turn=g.state.turn)  # the month's production rows
        product = settled.product(pid)
        assert product is not None
        assert sum(taxed) == tariffs.product_tariff_cents(
            settled, product, data.balance, data.game_data
        )
        g.state = result.new_state
