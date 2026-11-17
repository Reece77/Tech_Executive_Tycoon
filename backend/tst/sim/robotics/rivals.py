"""Rival robot makers (docs/formulas.md 53.1-53.2).

- **History holds:** before `robotics.start` the industrial robot makers do not decide (rivals'
  month skips them, `holds`); their customers follow the data (`demand.pin`).
- **Humanoid makers** hold until the humanoid era has arrived (and the history has ended): they
  have no price and no customers before it.
- From then on they decide by 15.3's rules and personality like every incumbent.
"""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.robotics.data import era_turn, file
from tst.sim.state import CompanyState, GameState


def holds(state: GameState, company: CompanyState, balance: Balance, data: GameData) -> bool:
    if data.robotics is None or company.is_player:
        return False
    f = file(data)
    if f.maker(company.name) is not None:
        return state.turn < balance.robotics.start_turn
    if f.humanoid_maker(company.name) is not None:
        return state.turn < balance.robotics.start_turn or era_turn(state, data) is None
    return False
