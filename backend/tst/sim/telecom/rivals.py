"""Rival telecom companies (docs/formulas.md 62.4).

- **History holds:** before `telecom.start` operators and equipment vendors do not decide (rivals'
  month skips them, `holds`), are never failed for cash and are not ranked; their customers follow
  the data (`history.pin`).
- From then on they decide by 15.3's rules and personality like every incumbent.
"""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.state import CompanyState, GameState
from tst.sim.telecom.data import is_telecom_rival


def holds(state: GameState, company: CompanyState, balance: Balance, data: GameData) -> bool:
    if data.telecom is None or company.is_player:
        return False
    return state.turn < balance.telecom.start_turn and is_telecom_rival(company, data)
