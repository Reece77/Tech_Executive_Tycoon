"""The player's currency actions (ADR-0014; docs/formulas.md 64.4, ADR-0025 point 5). They take
effect at once and spend the actor's energy (`finserv.energy.hedge`).

- **BuyForward** (`buy_forward`): a forward selling `notional_cents` of a foreign region's money
  `months` ahead at today's forward index. The company's open forwards in a region may cover at
  most `fx.max_hedge_share` of its next 12 months' net revenue there (`hedges.exposure_cents`).
- **SetHedgeProgramme** (`set_hedge_programme`): a rolling hedge of `share` of each month's net
  foreign revenue, `term_months` ahead; share 0 ends it (open forwards run to settlement).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import FinservRuleError
from tst.sim.fx import hedges
from tst.sim.fx.models import HedgeProgramme
from tst.sim.money import BP_DENOMINATOR, round_half_even
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class BuyForward:
    actor_id: int
    region: str
    notional_cents: int
    months: int
    kind: Literal["buy_forward"] = "buy_forward"


@dataclass(frozen=True, slots=True)
class SetHedgeProgramme:
    actor_id: int
    share: float
    term_months: int = 12
    kind: Literal["set_hedge_programme"] = "set_hedge_programme"


type FxAction = BuyForward | SetHedgeProgramme
ACTION_TYPES: Final[dict[str, type]] = {
    "buy_forward": BuyForward,
    "set_hedge_programme": SetHedgeProgramme,
}


def hedge_room_cents(state: GameState, company_id: int, region: str, balance: Balance) -> int:
    """How much more the company may hedge in a region (positive or 0)."""
    cap = round_half_even(
        hedges.exposure_cents(state, company_id, region)
        * round(balance.fx.max_hedge_share * BP_DENOMINATOR),
        BP_DENOMINATOR,
    )
    return max(0, cap - hedges.open_notional(state, company_id, region))


def buy_forward(state: GameState, action: BuyForward, balance: Balance, data: GameData) -> Outcome:
    company = acting_company(state, action.actor_id)
    room = hedge_room_cents(state, company, action.region, balance)
    if action.notional_cents > room:
        raise FinservRuleError(
            "forwards may cover at most "
            f"{balance.fx.max_hedge_share:.0%} of the next 12 months' net revenue there"
        )
    state = spend_energy(
        state, action.actor_id, "buy_forward", balance, cost=balance.finserv.energy["hedge"]
    )
    state, _ = hedges.buy(
        state, company, action.region, action.notional_cents, action.months, balance, data
    )
    return Outcome(state)


def set_programme(
    state: GameState, action: SetHedgeProgramme, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    if not 0.0 <= action.share <= balance.fx.max_hedge_share:
        raise FinservRuleError(
            f"a programme hedges 0-{balance.fx.max_hedge_share:.0%} of net foreign revenue"
        )
    if action.share > 0:
        hedges.check_term(action.term_months, balance)
    state = spend_energy(
        state,
        action.actor_id,
        "set_hedge_programme",
        balance,
        cost=balance.finserv.energy["hedge"],
    )
    return Outcome(with_programme(state, company, action.share, action.term_months))


def with_programme(
    state: GameState, company_id: int, share: float, term_months: int, *, by_cfo: bool = False
) -> GameState:
    rest = tuple(p for p in state.fx.programmes if p.company_id != company_id)
    if share > 0:
        rest = (*rest, HedgeProgramme(company_id, share, term_months, by_cfo))
    programmes = tuple(sorted(rest, key=lambda p: p.company_id))
    return replace(state, fx=replace(state.fx, programmes=programmes))


def apply_fx(state: GameState, action: FxAction, balance: Balance, data: GameData) -> Outcome:
    if data.fx is None:
        raise FinservRuleError("this game has no currencies")
    match action:
        case BuyForward():
            return buy_forward(state, action, balance, data)
        case SetHedgeProgramme():
            return set_programme(state, action, balance, data)
