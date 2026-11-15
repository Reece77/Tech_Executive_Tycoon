"""The Regulation screen's actions (docs/formulas.md 48.2, 48.4), immediate (ADR-0014).

- `ComplyDuties`: put right every setting a duty forbids on the group's platforms (self-
  preferencing off, the anti-steering rule off) in every regulator's reach.
- `AnswerOrder`: meet a structural order now, by sale or spin-off (the order's event offers the
  same answers; this is for an order whose answer was put off)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import RegulationRuleError
from tst.sim.ledger import LedgerBalances
from tst.sim.regulation import data as rdata
from tst.sim.regulation import structural
from tst.sim.regulation.duties import apply, breaches, duties_of
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class ComplyDuties:
    actor_id: int
    kind: Literal["comply_duties"] = "comply_duties"


@dataclass(frozen=True, slots=True)
class AnswerOrder:
    actor_id: int
    order_id: int
    how: Literal["sell", "spin_off"]
    kind: Literal["answer_order"] = "answer_order"


type RegulationAction = ComplyDuties | AnswerOrder
ACTION_TYPES: Final[dict[str, type]] = {
    "comply_duties": ComplyDuties,
    "answer_order": AnswerOrder,
}


def apply_regulation(
    state: GameState,
    action: RegulationAction,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> Outcome:
    if not rdata.enabled(data):
        raise RegulationRuleError("regulation is not running in this game")
    company_id = acting_company(state, action.actor_id)
    rb = balance.regulation
    match action:
        case ComplyDuties():
            regs = [r for r in rdata.file(data).regulators if breaches(state, company_id, r)]
            if not regs:
                raise RegulationRuleError("no setting breaks a duty")
            state = spend_energy(
                state, action.actor_id, "set_compliance", balance, cost=rb.energy["set_compliance"]
            )
            for reg in regs:
                for d in duties_of(state, company_id, reg.key):
                    if d.from_turn <= state.turn:
                        state = apply(state, d, balance, data)
            return Outcome(state)
        case AnswerOrder():
            o = next((x for x in state.reg_orders if x.id == action.order_id), None)
            if o is None or o.company_id != company_id or o.status != "open":
                raise RegulationRuleError("no open order to answer")
            state = spend_energy(
                state, action.actor_id, "comply_order", balance, cost=rb.energy["comply_order"]
            )
            if action.how == "sell":
                if structural.buyer_of(state, o) is None:
                    raise RegulationRuleError("no rival sells in that market to buy it")
                state, entries, logs = structural.sell(state, o, balance, data)
            else:
                if not structural.can_spin_off(state, o):
                    raise RegulationRuleError(
                        "a spin-off needs the unit in a subsidiary of a listed holding company"
                    )
                state, entries, logs = structural.spin_off(state, o, balances, balance, data)
            return Outcome(replace(state), tuple(entries), tuple(logs))
