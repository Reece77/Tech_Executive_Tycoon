"""M43r finding 11 (Codex review 9): a dated space opening sells in its opening month.

Starlink's paid beta opens in October 2020 (space.yaml). The history's pin ran in phase 9, after
phase 5's sales, so October's market still had no price and the first sales came in November
(formulas.md 56.3-56.4). Openings now apply before the sales phase."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.decisions import Decisions
from tst.sim.ledger import LedgerBalances, apply_entries
from tst.sim.rng import RngFactory
from tst.sim.space import history
from tst.sim.turn import advance_turn


def test_starlink_sells_from_its_opening_month(loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    state = history.pin(replace(fresh_game(loaded), turn=ym_to_turn(2020, 9)), b, d)
    spacex = next(c for c in state.companies if c.name == "SpaceX")
    (line,) = [p for p in state.company_products(spacex.id) if p.category == b.space.broadband]
    balances: LedgerBalances = {}
    sales: dict[int, int] = {}
    for month in (9, 10, 11):
        turn = ym_to_turn(2020, month)
        assert state.turn == turn
        result = advance_turn(state, Decisions(), RngFactory(3), b, d, balances)
        sales[month] = sum(
            -line_.amount
            for e in result.ledger_entries
            if e.company_id == spacex.id and e.memo == f"Revenue: {line.name}"
            for line_ in e.lines
            if line_.account.startswith("4")
        )
        balances = apply_entries(balances, result.ledger_entries)
        state = result.new_state
    assert sales[9] == 0  # nothing before the service opens
    assert sales[10] > 0  # the opening month sells
    assert sales[11] > 0
