"""The founder's own investing (docs/formulas.md 37, M26): join a startup's round, back a new
startup with someone from the network, trade listed shares, and form, fund and direct a
family office. Immediate actions (ADR-0014); only the founder takes them, with personal
money (never the company's)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np

from tst.sim.actions.founder import _founder
from tst.sim.actions.hiring import Outcome, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.founder import angel, family_office, shares
from tst.sim.ledger import LedgerBalances
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class JoinRound:
    """Put `cents` of personal cash into a startup's open round (37.2)."""

    actor_id: int
    company_id: int
    cents: int
    kind: Literal["join_round"] = "join_round"


@dataclass(frozen=True, slots=True)
class BackStartup:
    """Back a new startup in `category` led by `founder_id` from the network (37.2)."""

    actor_id: int
    founder_id: int
    category: str
    cents: int
    kind: Literal["back_startup"] = "back_startup"


@dataclass(frozen=True, slots=True)
class TradeShares:
    """Buy or sell `shares` of a listed company (37.3)."""

    actor_id: int
    company_id: int
    side: Literal["buy", "sell"]
    shares: int
    kind: Literal["trade_shares"] = "trade_shares"


@dataclass(frozen=True, slots=True)
class FormFamilyOffice:
    actor_id: int
    mandate: str  # conservative, balanced, aggressive
    kind: Literal["form_family_office"] = "form_family_office"


@dataclass(frozen=True, slots=True)
class MoveFamilyOffice:
    """Personal cash into the family office (positive) or out of it (negative) (37.4)."""

    actor_id: int
    cents: int
    kind: Literal["move_family_office"] = "move_family_office"


@dataclass(frozen=True, slots=True)
class SetOfficeMandate:
    actor_id: int
    mandate: str
    kind: Literal["set_office_mandate"] = "set_office_mandate"


type InvestingAction = (
    JoinRound | BackStartup | TradeShares | FormFamilyOffice | MoveFamilyOffice | SetOfficeMandate
)

INVESTING_ACTION_TYPES: dict[str, type[InvestingAction]] = {
    "join_round": JoinRound,
    "back_startup": BackStartup,
    "trade_shares": TradeShares,
    "form_family_office": FormFamilyOffice,
    "move_family_office": MoveFamilyOffice,
    "set_office_mandate": SetOfficeMandate,
}


def apply_investing(
    state: GameState,
    action: InvestingAction,
    rng: RngFactory,
    draws: Callable[[], np.random.Generator],
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    _founder(state, action.actor_id)
    me = action.actor_id
    match action:
        case JoinRound():
            state = spend_energy(state, me, action.kind, balance, cost=balance.angel.energy)
            state, entries, logs = angel.join_round(
                state, me, action.company_id, action.cents, rng, balance, data
            )
            return Outcome(state, entries, logs)
        case BackStartup():
            state = spend_energy(state, me, action.kind, balance, cost=balance.angel.back_energy)
            state, entries, logs = angel.back_startup(
                state,
                me,
                action.founder_id,
                action.category,
                action.cents,
                draws(),
                rng,
                balances,
                balance,
                data,
            )
            return Outcome(state, entries, logs)
        case TradeShares():
            cost = balance.personal.trade_energy
            state = spend_energy(state, me, action.kind, balance, cost=cost)
            state, entries, logs = shares.trade(
                state, me, action.company_id, action.side, action.shares, balances, balance, data
            )
            return Outcome(state, entries, logs)
        case FormFamilyOffice():
            cost = balance.family_office.energy
            state = spend_energy(state, me, action.kind, balance, cost=cost)
            state, log = family_office.form(state, me, action.mandate, rng, balances, balance, data)
            return Outcome(state, (), (log,))
        case MoveFamilyOffice():
            cost = balance.family_office.move_energy
            state = spend_energy(state, me, action.kind, balance, cost=cost)
            state, log = family_office.move(state, me, action.cents)
            return Outcome(state, (), (log,))
        case SetOfficeMandate():
            cost = balance.family_office.move_energy
            state = spend_energy(state, me, action.kind, balance, cost=cost)
            return Outcome(family_office.set_mandate(state, me, action.mandate))
