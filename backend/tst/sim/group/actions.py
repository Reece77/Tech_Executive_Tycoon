"""The group's actions (docs/formulas.md 31, M16): immediate actions (ADR-0014) the founder
takes as Chair of the holding company."""

from __future__ import annotations

from tst.sim.actions.hiring import Outcome
from tst.sim.data_models import Balance, GameData
from tst.sim.group.holding import FormHolding, form
from tst.sim.group.subsidiaries import (
    AnswerGroupPitch,
    ReplaceSubsidiaryCeo,
    SetMandate,
    answer_pitch,
    replace_ceo,
    set_mandate,
)
from tst.sim.ledger import LedgerBalances
from tst.sim.state import GameState

type GroupAction = FormHolding | SetMandate | ReplaceSubsidiaryCeo | AnswerGroupPitch
GROUP_ACTIONS = (FormHolding, SetMandate, ReplaceSubsidiaryCeo, AnswerGroupPitch)


def apply_group(
    state: GameState,
    action: GroupAction,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    match action:
        case FormHolding():
            return form(state, action, balances, balance, data)
        case SetMandate():
            return set_mandate(state, action, balance, data, balances)
        case ReplaceSubsidiaryCeo():
            return replace_ceo(state, action)
        case AnswerGroupPitch():
            return answer_pitch(state, action, balances)


__all__ = [
    "GROUP_ACTIONS",
    "AnswerGroupPitch",
    "FormHolding",
    "GroupAction",
    "ReplaceSubsidiaryCeo",
    "SetMandate",
    "apply_group",
]
