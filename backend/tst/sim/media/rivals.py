"""Rival media companies (docs/formulas.md 65.7).

- **History holds:** before `media.start` the media incumbents do not decide (rivals' month skips
  them, `holds`), are never failed for cash and are not ranked; their customers (and social lines'
  prices) follow the data (`history.pin`).
- From then on they decide by 15.3's rules and personality like every incumbent; a social line's
  price stays the ad market's (65.1).
"""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.media.data import is_media_rival
from tst.sim.state import CompanyState, GameState


def holds(state: GameState, company: CompanyState, balance: Balance, data: GameData) -> bool:
    if data.media is None or company.is_player:
        return False
    return state.turn < balance.media.start_turn and is_media_rival(company, data)
