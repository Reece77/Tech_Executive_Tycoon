"""The founder's own actions (docs/formulas.md 32.2-32.5, M24): sell some of their shares
once listed, create a foundation, give to it, and set a region's monthly lobbying. Immediate
actions (ADR-0014); only the founder takes them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.founder import foundation, influence, personal
from tst.sim.state import GameState, listed_id


@dataclass(frozen=True, slots=True)
class SellFounderShares:
    """The founder sells `shares` of their own into the public float (32.2)."""

    actor_id: int
    shares: int
    kind: Literal["sell_founder_shares"] = "sell_founder_shares"


@dataclass(frozen=True, slots=True)
class CreateFoundation:
    actor_id: int
    cause: str  # education, climate, health, local
    name: str = ""
    city: str | None = None  # local communities: a cities.yaml key (default: the HQ city)
    kind: Literal["create_foundation"] = "create_foundation"


@dataclass(frozen=True, slots=True)
class GiveToFoundation:
    actor_id: int
    amount_cents: int
    kind: Literal["give_to_foundation"] = "give_to_foundation"


@dataclass(frozen=True, slots=True)
class SetLobbying:
    """A region's monthly lobbying spend, in whole dollars (0 stops it) (32.5)."""

    actor_id: int
    region: str
    monthly_dollars: int
    kind: Literal["set_lobbying"] = "set_lobbying"


type FounderAction = SellFounderShares | CreateFoundation | GiveToFoundation | SetLobbying


def _founder(state: GameState, actor_id: int) -> int:
    company = acting_company(state, actor_id)
    founder = state.founder_of(company)
    if founder is None or founder.id != actor_id:
        raise InvalidActionError("only the founder can do that")
    return company


def apply_founder(
    state: GameState, action: FounderAction, balance: Balance, data: GameData
) -> Outcome:
    company = _founder(state, action.actor_id)
    match action:
        case SellFounderShares():
            state = spend_energy(
                state,
                action.actor_id,
                action.kind,
                balance,
                cost=balance.public.capital.secondary_energy,
            )
            # M16 (31.2): with a holding company, the founder's shares are the holding's
            listed = listed_id(state) if company == state.player.id else company
            state, _, log = personal.sell_shares(
                state, listed, action.actor_id, action.shares, balance
            )
            return Outcome(state, (), (log,))
        case CreateFoundation():
            state, log = foundation.create(
                state, action.actor_id, action.name, action.cause, action.city, balance, data
            )
            state = spend_energy(
                state, action.actor_id, action.kind, balance, cost=balance.foundation.energy
            )
            return Outcome(state, (), (log,))
        case GiveToFoundation():
            state, log = foundation.give(state, action.actor_id, action.amount_cents)
            return Outcome(state, (), (log,))
        case SetLobbying():
            state, log = influence.set_lobbying(
                state, company, action.region, action.monthly_dollars, balance, data
            )
            state = spend_energy(
                state, action.actor_id, action.kind, balance, cost=balance.influence.energy
            )
            return Outcome(state, (), (log,))
