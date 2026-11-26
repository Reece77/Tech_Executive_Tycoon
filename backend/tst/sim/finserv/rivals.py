"""Rival banks, card networks, acquirers and insurers (docs/formulas.md 64.5).

- **History holds:** before `finserv.start` they do not decide (rivals' month skips them,
  `holds`), are never failed for cash and are not ranked; their customers follow the data
  (`history.pin`). Silicon Valley Bank's line closes in March 2023 (its failure).
- From then on they decide by 15.3's rules and personality like every incumbent.
"""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.finserv.data import is_finance_rival
from tst.sim.state import CompanyState, GameState


def holds(state: GameState, company: CompanyState, balance: Balance, data: GameData) -> bool:
    if data.finserv is None or company.is_player:
        return False
    return state.turn < balance.finserv.start_turn and is_finance_rival(company, data)
