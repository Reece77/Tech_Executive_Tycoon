"""Rival space companies (docs/formulas.md 56.3).

- **History holds:** before `space.start` launch providers and constellation operators do not
  decide (rivals' month skips them, `holds`) and are never failed for cash; their customers follow
  the data (`history.pin`).
- From then on they decide by 15.3's rules and personality like every incumbent.
"""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.space.data import is_space_rival
from tst.sim.state import CompanyState, GameState


def holds(state: GameState, company: CompanyState, balance: Balance, data: GameData) -> bool:
    if data.space is None or company.is_player:
        return False
    return state.turn < balance.space.start_turn and is_space_rival(company, data)
