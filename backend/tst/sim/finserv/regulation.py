"""Bank and insurance regulators (docs/formulas.md 64.5): whether a region's regulator is strict
(a charter takes `bank.strict_months` longer), and the review of a bank inside a tech group.
Filled in by sub-task 6."""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.state import GameState


def strict(state: GameState, region: str, kind: str, balance: Balance, data: GameData) -> bool:
    return False
