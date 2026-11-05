"""Press actions (docs/formulas.md 29.2, M14b): a public promise, made by the founder in a
press moment answered this month. Immediate action (ADR-0014), energy promise.energy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.log import inbox_item
from tst.sim.press import promises
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class MakePromise:
    actor_id: int
    promise: str  # ship, beat, research, no_layoffs, no_price_rise
    product_id: int | None = None
    rival_product_id: int | None = None
    domain: str | None = None
    level: int | None = None
    months: int | None = None
    kind: Literal["make_promise"] = "make_promise"


type PressAction = MakePromise


def make_promise(
    state: GameState, action: MakePromise, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    founder = state.founder_of(company)
    if founder is None or founder.id != action.actor_id:
        raise InvalidActionError("only the founder speaks for the company")
    state, promise = promises.make(
        state,
        company,
        action.promise,
        balance,
        data,
        product_id=action.product_id,
        rival_product_id=action.rival_product_id,
        domain=action.domain,
        level=action.level,
        months=action.months,
    )
    state = spend_energy(
        state, action.actor_id, "make_promise", balance, cost=balance.promise.energy
    )
    words = promises.promise_words(state, promise, data)
    return Outcome(state, (), (inbox_item(state.turn, company, "promise_made", promise=words),))
