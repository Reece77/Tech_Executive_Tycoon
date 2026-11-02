"""Executive authority (docs/formulas.md 24.1, M10c): the player gives a filled seat
authority over its function, with guardrails, or withdraws it; and answers an executive's
proposal. Immediate actions (ADR-0014): energy exec_authority.change_energy to change
authority; a proposal's own action costs what it costs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import AUTHORITY_SEATS, Balance, GameData
from tst.sim.errors import InvalidActionError, OrgRuleError
from tst.sim.org.executives import seats_in_play
from tst.sim.org.models import Authority, GuardValue, Proposal, ProposalStatus
from tst.sim.state import GameState, with_authority, with_proposal

PROTECTED_UNITS = "protected_units"  # the CTO's guardrail that is a list of unit ids
FRACTIONAL = frozenset({"coverage_target"})  # guardrails that may be fractions


@dataclass(frozen=True, slots=True)
class SetAuthority:
    actor_id: int
    seat: str
    enabled: bool
    # Guardrails to change, (key, value); the rest keep their current or default values.
    guardrails: tuple[tuple[str, GuardValue], ...] = ()
    kind: Literal["set_authority"] = "set_authority"


def _value(key: str, value: object, state: GameState, company: int) -> GuardValue:
    if key == PROTECTED_UNITS:
        if not isinstance(value, (list, tuple)):
            raise InvalidActionError("protected_units is a list of unit ids")
        units = {u.id for u in state.active_units(company)}
        ids = tuple(sorted({int(v) for v in value}))
        if not set(ids) <= units:
            raise OrgRuleError("protected units must be active units of the company")
        return ids
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise InvalidActionError(f"{key} must be a number, zero or more")
    return float(value) if key in FRACTIONAL else int(value)


def guardrails_for(
    current: Authority | None,
    seat: str,
    changes: tuple[tuple[str, GuardValue], ...],
    state: GameState,
    company: int,
    balance: Balance,
) -> tuple[tuple[str, GuardValue], ...]:
    """Defaults, then the seat's current guardrails, then the changes; unknown keys refused."""
    defaults = balance.exec_authority.defaults[seat]
    merged: dict[str, GuardValue] = {
        k: tuple(v) if isinstance(v, list) else v for k, v in defaults.items()
    }
    if current is not None:
        merged |= dict(current.guardrails)
    for key, value in changes:
        if key not in defaults:
            raise InvalidActionError(f"the {seat.upper()} has no guardrail {key!r}")
        merged[key] = _value(key, value, state, company)
    return tuple(sorted(merged.items()))


def sales_anchors(
    state: GameState, company: int, data: GameData
) -> tuple[tuple[int, str, int], ...]:
    """The player's sales-led prices now: the CRO moves them only within its band (24.1)."""
    out = []
    for product in state.company_products(company):
        for seg in state.segments_of(product.id):
            if data.segment(seg.segment).reach == "sales" and seg.price_cents is not None:
                out.append((product.id, seg.segment, seg.price_cents))
    return tuple(sorted(out))


def set_authority(
    state: GameState, action: SetAuthority, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    if action.seat not in AUTHORITY_SEATS:
        raise InvalidActionError(f"a {action.seat!r} seat takes no authority")
    if action.enabled:
        if not seats_in_play(state, company, balance):
            raise OrgRuleError(f"executive seats come at stage {balance.exec_seats.stage}")
        holder = state.seat_holder(company, action.seat)
        if holder is None or state.employment_of(holder) is None:
            raise OrgRuleError(f"appoint a {action.seat.upper()} before giving them authority")
    current = state.authority(company, action.seat)
    guardrails = guardrails_for(current, action.seat, action.guardrails, state, company, balance)
    if current is not None and (current.enabled, current.guardrails) == (
        action.enabled,
        guardrails,
    ):
        raise InvalidActionError("nothing changes")
    if current is None and not action.enabled:
        raise InvalidActionError("that seat has no authority to withdraw")
    state = spend_energy(
        state,
        action.actor_id,
        "set_authority",
        balance,
        cost=balance.exec_authority.change_energy,
    )
    since = (
        current.since_turn
        if current is not None and current.enabled and action.enabled
        else state.turn
    )
    anchors = current.price_anchors if current is not None else ()
    if action.seat == "cro" and action.enabled and (current is None or not current.enabled):
        anchors = sales_anchors(state, company, data)  # the player's last prices (24.1)
    record = Authority(company, action.seat, action.enabled, guardrails, since, anchors)
    return Outcome(with_authority(state, record))


def default_authority(state: GameState, company: int, seat: str, balance: Balance) -> Authority:
    """What a seat's authority would be if given now with the default guardrails."""
    current = state.authority(company, seat)
    if current is not None:
        return current
    return replace(
        Authority(company, seat, False, (), state.turn),
        guardrails=guardrails_for(None, seat, (), state, company, balance),
    )


@dataclass(frozen=True, slots=True)
class AnswerProposal:
    """Approve or decline an executive's proposal (24.1). Approving takes the proposed action
    with the player as actor: a round, a loan or a lease, at its own energy and rules."""

    actor_id: int
    proposal_id: int
    approve: bool
    kind: Literal["answer_proposal"] = "answer_proposal"


def proposal_action(proposal: Proposal, actor_id: int) -> object:
    """The action a proposal stands for."""
    from tst.sim.actions.finance import StartRound, TakeLoan
    from tst.sim.actions.geo import LeaseOffice

    p = dict(proposal.params)
    if proposal.kind == "round":
        return StartRound(actor_id, str(p["series"]), int(p["target_cents"]))
    if proposal.kind == "loan":
        return TakeLoan(actor_id, str(p["loan_kind"]), int(p["amount_cents"]))
    return LeaseOffice(actor_id, str(p["city"]), int(p["seats"]))


def pending_proposal(state: GameState, company: int, proposal_id: int) -> Proposal:
    proposal = next((p for p in state.proposals if p.id == proposal_id), None)
    if proposal is None or proposal.company_id != company:
        raise InvalidActionError(f"no proposal {proposal_id}")
    if proposal.status != "pending":
        raise InvalidActionError("that proposal has been answered")
    return proposal


def close_proposal(state: GameState, proposal: Proposal, status: ProposalStatus) -> GameState:
    return with_proposal(state, replace(proposal, status=status, resolved_turn=state.turn))
