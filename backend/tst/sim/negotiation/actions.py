"""The immediate actions a negotiation ends with (docs/formulas.md 58.4; ADR-0014). Most deal
kinds agree through their existing action with the agreed terms (tst.sim.negotiation.deals);
these are the four that had no action taking terms:

- `AgreeRetention`: a key person stays for the agreed salary; the rival's approach is turned
  down now (the raise is `give_raise`, its rules and morale unchanged).
- `AgreeContractValue`: a government contract won this month starts at the agreed value.
- `AgreeSettlement`: the regulator's settlement is chosen (the event's own `settle` answer) and
  its fine becomes the agreed one (the difference posted as a separate line).
- `WalkAway`: the counterpart walked away (58.4): the deal is lost the way that deal is lost.

Each is set only by the negotiation service, which has checked the terms against the
counterpart's zone; replays apply them from the decision log like any action."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.events import ChooseEvent, choose_event
from tst.sim.actions.hiring import Outcome, acting_company
from tst.sim.actions.org import GiveRaise, give_raise
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import NegotiationRuleError
from tst.sim.government.models import Contract
from tst.sim.ledger import CASH, FINES, LedgerBalances, LedgerEntry
from tst.sim.log import inbox_item
from tst.sim.negotiation.config import DealKind
from tst.sim.rivals.models import PoachApproach
from tst.sim.state import (
    GameState,
    target_file,
    with_approach,
    with_candidate,
    with_employment,
    with_target_file,
)

SETTLE: Final = "settle"  # tunable-exempt: the regulation step a settlement answer runs
CONTEST: Final = ("contest", "cooperate")  # tunable-exempt: the steps that refuse to settle


@dataclass(frozen=True, slots=True)
class AgreeRetention:
    actor_id: int
    approach_id: int
    salary_cents: int
    kind: Literal["negotiation_retention"] = "negotiation_retention"


@dataclass(frozen=True, slots=True)
class AgreeContractValue:
    actor_id: int
    contract_id: int
    value_cents: int
    kind: Literal["negotiation_contract"] = "negotiation_contract"


@dataclass(frozen=True, slots=True)
class AgreeSettlement:
    actor_id: int
    event_id: int
    fine_cents: int
    kind: Literal["negotiation_settlement"] = "negotiation_settlement"


@dataclass(frozen=True, slots=True)
class WalkAway:
    actor_id: int
    deal_kind: DealKind
    deal_id: int  # the target, candidate, approach, contract, event or asset (0 for a quote)
    cooldown_months: int
    kind: Literal["negotiation_walk_away"] = "negotiation_walk_away"


type NegotiationAction = AgreeRetention | AgreeContractValue | AgreeSettlement | WalkAway
ACTION_TYPES: Final[dict[str, type]] = {
    "negotiation_retention": AgreeRetention,
    "negotiation_contract": AgreeContractValue,
    "negotiation_settlement": AgreeSettlement,
    "negotiation_walk_away": WalkAway,
}


def pending_approach(state: GameState, approach_id: int) -> PoachApproach:
    approach = next((a for a in state.approaches if a.id == approach_id), None)
    if approach is None or approach.status != "pending":
        raise NegotiationRuleError(f"no open approach {approach_id}")
    employment = state.employment_of(approach.person_id)
    if employment is None or employment.company_id != state.player.id:
        raise NegotiationRuleError("that person no longer works for you")
    return approach


def new_contract(state: GameState, contract_id: int) -> Contract:
    """A government contract won this month and not started: its final terms are open."""
    c = next((x for x in state.gov_contracts if x.id == contract_id), None)
    if c is None or c.company_id != state.player.id or c.status != "active":
        raise NegotiationRuleError(f"no contract {contract_id} to settle terms on")
    if c.start_turn <= state.turn:
        raise NegotiationRuleError("its terms were settled when delivery began")
    return c


def choice_for(state: GameState, event_id: int, steps: tuple[str, ...]) -> str:
    """The event's answer that runs one of these regulation steps."""
    event = state.event(event_id)
    if event is None or event.status != "open":
        raise NegotiationRuleError(f"no open event {event_id}")
    for c in event.choices:
        if any(e.type == "regulation_step" and e.stat in steps for e in c.effects):
            return c.key
    raise NegotiationRuleError("that event has no such answer")


def _retain(state: GameState, action: AgreeRetention, balance: Balance) -> Outcome:
    approach = pending_approach(state, action.approach_id)
    out = give_raise(
        state, GiveRaise(action.actor_id, approach.person_id, action.salary_cents), balance
    )
    state = with_approach(
        out.state, replace(approach, status="declined", resolved_turn=out.state.turn)
    )
    person = state.person(approach.person_id)
    log = inbox_item(
        state.turn,
        state.player.id,
        "poach_declined",
        link_kind="person",
        link_id=person.id,
        name=f"{person.first_name} {person.last_name}",
        rival=state.company(approach.rival_id).name,
    )
    return Outcome(state, out.entries, (*out.log, log))


def _contract(state: GameState, action: AgreeContractValue) -> Outcome:
    c = new_contract(state, action.contract_id)
    if action.value_cents <= 0:
        raise NegotiationRuleError("a contract needs a positive value")
    contracts = tuple(
        replace(x, value_cents=action.value_cents) if x.id == c.id else x
        for x in state.gov_contracts
    )
    return Outcome(replace(state, gov_contracts=contracts))


def _settle(
    state: GameState,
    action: AgreeSettlement,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    from tst.sim.regulation.answers import case_for
    from tst.sim.regulation.cases import with_case

    event = state.event(action.event_id)
    if event is None:
        raise NegotiationRuleError(f"no open event {action.event_id}")
    case = case_for(state, event)
    if case is None:
        raise NegotiationRuleError("that event has no open case")
    choice = choice_for(state, action.event_id, (SETTLE,))
    out = choose_event(
        state, ChooseEvent(action.actor_id, action.event_id, choice), balance, data, balances
    )
    settled = next((c for c in out.state.reg_cases if c.id == case.id), None)
    if settled is None or action.fine_cents <= 0:
        return out
    diff = action.fine_cents - settled.fine_cents
    if diff == 0:
        return out
    reg = settled.regulator.replace("_", " ")
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=settled.company_id,
        memo=f"Settlement as negotiated: {reg} case {settled.id}",
        debit=FINES if diff > 0 else CASH,
        credit=CASH if diff > 0 else FINES,
        amount=abs(diff),
    )
    state = with_case(out.state, replace(settled, fine_cents=action.fine_cents))
    return Outcome(state, (*out.entries, entry), out.log)


def _walk(
    state: GameState,
    action: WalkAway,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    """The deal is lost (58.4), each kind the way it is lost without talks."""
    kind = action.deal_kind
    turn = state.turn
    if kind == "acquisition":
        from tst.sim.mna.deals import file_of

        found = target_file(state, state.player.id, action.deal_id) or file_of(
            state, state.player.id, action.deal_id, balance
        )
        until = turn + action.cooldown_months
        state = with_target_file(state, replace(found, blocked_until=until))
    elif kind == "hire":
        candidate = state.candidate(action.deal_id)
        if candidate is not None and candidate.status == "open":
            state = with_candidate(state, replace(candidate, status="declined", resolved_turn=turn))
    elif kind == "retention":
        approach = pending_approach(state, action.deal_id)
        employment = state.employment_of(approach.person_id)
        assert employment is not None
        state = with_approach(state, replace(approach, status="accepted", resolved_turn=turn))
        state = with_employment(
            state,
            replace(employment, status="notice", end_turn=turn + 1, end_reason="poached"),
        )
    elif kind == "government":
        contracts = tuple(
            replace(x, status="terminated", end_turn=turn) if x.id == action.deal_id else x
            for x in state.gov_contracts
        )
        state = replace(state, gov_contracts=contracts)
    elif kind == "settlement":
        choice = choice_for(state, action.deal_id, CONTEST)
        return choose_event(
            state, ChooseEvent(action.actor_id, action.deal_id, choice), balance, data, balances
        )
    elif kind == "licence_in":
        assets = tuple(
            replace(a, until_turn=turn) if a.id == action.deal_id else a
            for a in state.pharma_assets
        )
        state = replace(state, pharma_assets=assets)
    return Outcome(state)


def apply_negotiation(
    state: GameState,
    action: NegotiationAction,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    acting_company(state, action.actor_id)
    match action:
        case AgreeRetention():
            return _retain(state, action, balance)
        case AgreeContractValue():
            return _contract(state, action)
        case AgreeSettlement():
            return _settle(state, action, balance, data, balances)
        case WalkAway():
            return _walk(state, action, balance, data, balances)
