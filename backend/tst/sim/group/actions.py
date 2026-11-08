"""The group's actions (docs/formulas.md 31, M16): immediate actions (ADR-0014) the founder
takes as Chair of the holding company."""

from __future__ import annotations

from tst.sim.actions.hiring import Outcome
from tst.sim.data_models import Balance, GameData
from tst.sim.group.capital import (
    BuyOutMinorities,
    BuyStake,
    CapitalAction,
    CarveOut,
    SellStake,
    SpinOff,
    VentureInvest,
    buy_out,
    buy_stake,
    carve_out,
    sell_stake,
    spin_off,
    venture,
)
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
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

type GroupAction = (
    FormHolding | SetMandate | ReplaceSubsidiaryCeo | AnswerGroupPitch | CapitalAction
)


def apply_group(
    state: GameState,
    action: GroupAction,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    match action:
        case SellStake():
            return sell_stake(state, action, rng, balances, balance, data)
        case BuyOutMinorities():
            return buy_out(state, action, balances, balance, data)
        case CarveOut():
            return carve_out(state, action, balances, balance, data)
        case SpinOff():
            return spin_off(state, action, balances, balance, data)
        case BuyStake():
            return buy_stake(state, action, balances, balance, data)
        case VentureInvest():
            return venture(state, action, rng, balances, balance, data)
        case FormHolding():
            return form(state, action, balances, balance, data)
        case SetMandate():
            return set_mandate(state, action, balance, data, balances)
        case ReplaceSubsidiaryCeo():
            return replace_ceo(state, action)
        case AnswerGroupPitch():
            return answer_pitch(state, action, balances)


__all__ = [
    "AnswerGroupPitch",
    "BuyOutMinorities",
    "BuyStake",
    "CarveOut",
    "FormHolding",
    "GroupAction",
    "ReplaceSubsidiaryCeo",
    "SellStake",
    "SetMandate",
    "SpinOff",
    "VentureInvest",
    "apply_group",
]
