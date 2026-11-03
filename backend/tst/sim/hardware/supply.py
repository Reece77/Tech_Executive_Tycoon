"""Allocation of goods to production contracts (docs/formulas.md 26.2, 26.3): a contract
signed before the running shortage began keeps 100% allocation; one signed during it gets
the good's allocation. History while there is history (the same on every seed), then the
seeded shocks of M12a's goods (22.4)."""

from __future__ import annotations

from tst.sim.data_models import GameData
from tst.sim.facilities import goods
from tst.sim.state import GameState


def delivered_share(
    state: GameState, good: str, signed_turn: int, data: GameData, *, advanced: bool = False
) -> float:
    """The share of a contract's monthly volume delivered this month (26.2)."""
    assert data.components is not None
    history = data.components.good(good)
    turn = state.turn
    if turn <= history.last_turn:
        share = history.allocation_at(turn, advanced=advanced)
        start = history.shortage_start(turn, advanced=advanced)
    else:
        month = goods.current(state, good, data)
        share = month.allocation
        start = month.shock_turn if month.in_shock(turn) else None
    if share >= 1 or (start is not None and signed_turn < start):
        return 1.0
    return share
