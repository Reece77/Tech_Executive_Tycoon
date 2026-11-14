"""The player's automation actions (docs/formulas.md 40.1-40.2, 40.8; ADR-0014).

Giving, changing or taking back an area is immediate and costs automation.change_energy; its
settings (limit, priority, routine events, bold claims) are free. Giving an existing seat area
to its seat holder also gives the seat its authority (24.1): the two are one setting. Taking an
area back within automation.take_back_months of giving it costs a high-ego owner morale once.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.automation import owners
from tst.sim.automation.config import AREA_SEAT_RULE
from tst.sim.automation.models import AreaOwner
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError, OrgRuleError
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import inbox_item
from tst.sim.org.models import Authority
from tst.sim.scale import clamp_morale
from tst.sim.state import (
    GameState,
    with_area_owner,
    with_authority,
    with_person_state,
    without_area_owner,
)

ENERGY_KEY: Final = "set_area_owner"


@dataclass(frozen=True, slots=True)
class SetAreaOwner:
    """Give an area to a person, or move it to another (40.1). `limit_cents` None: the default
    (40.2); `priority` None: after the person's other areas."""

    actor_id: int
    area: str
    person_id: int
    limit_cents: int | None = None
    priority: int | None = None
    kind: Literal["set_area_owner"] = "set_area_owner"


@dataclass(frozen=True, slots=True)
class TakeBackArea:
    """Manage an area yourself again (40.1)."""

    actor_id: int
    area: str
    kind: Literal["take_back_area"] = "take_back_area"


@dataclass(frozen=True, slots=True)
class SetAreaSettings:
    """An owned area's settings (40.2, 40.3, 40.5, 40.6); None keeps a value. Free."""

    actor_id: int
    area: str
    limit_cents: int | None = None
    priority: int | None = None
    answer_events: bool | None = None
    allow_bold: bool | None = None
    kind: Literal["set_area_settings"] = "set_area_settings"


type AutomationAction = SetAreaOwner | TakeBackArea | SetAreaSettings

ACTION_TYPES: dict[str, type] = {
    "set_area_owner": SetAreaOwner,
    "take_back_area": TakeBackArea,
    "set_area_settings": SetAreaSettings,
}


def _check_area(area: str, b: Balance) -> None:
    if area not in b.automation.areas:
        raise InvalidActionError(f"no area {area!r}")


def _founder_only(state: GameState, actor_id: int) -> int:
    company = acting_company(state, actor_id)
    if not state.person(actor_id).is_founder:
        raise OrgRuleError("only the founder hands out areas")
    return company


def _anchors(state: GameState, company: int) -> tuple[tuple[int, str, int], ...]:
    """Every priced segment's price now: pricing moves only within its band of these (40.6)."""
    out = []
    for product in state.company_products(company):
        for seg in state.segments_of(product.id):
            if seg.price_cents is not None:
                out.append((product.id, seg.segment, seg.price_cents))
    return tuple(sorted(out))


def _give_seat(
    state: GameState, company: int, area: str, person_id: int, b: Balance, data: GameData
) -> GameState:
    """Existing seat areas given to the seat holder: the seat's authority is the same setting
    (40.1). Pricing keeps anchors for every price, self-serve and devices too (40.6)."""
    from tst.sim.actions.authority import guardrails_for, sales_anchors

    seat = AREA_SEAT_RULE.get(area)
    if area == "pricing":
        current = state.authority(company, "cro")
        known = {(p, s) for p, s, _ in current.price_anchors} if current is not None else set()
        extra = tuple(a for a in _anchors(state, company) if (a[0], a[1]) not in known)
        if current is None:
            rails = guardrails_for(None, "cro", (), state, company, b, data)
            current = Authority(
                company, "cro", False, rails, state.turn, sales_anchors(state, company, data)
            )
        state = with_authority(
            state, replace(current, price_anchors=tuple(sorted((*current.price_anchors, *extra))))
        )
    if seat is None or state.seat_holder(company, seat) != person_id:
        return state
    current = state.authority(company, seat)
    if current is not None and current.enabled:
        return state
    rails = guardrails_for(current, seat, (), state, company, b, data)
    anchors = current.price_anchors if current is not None else ()
    if seat == "cro":
        known = {(p, s) for p, s, _ in anchors}
        anchors = tuple(
            sorted(
                (
                    *anchors,
                    *(a for a in sales_anchors(state, company, data) if (a[0], a[1]) not in known),
                )
            )
        )
    return with_authority(state, Authority(company, seat, True, rails, state.turn, anchors))


def set_area_owner(
    state: GameState,
    action: SetAreaOwner,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    _check_area(action.area, balance)
    company = _founder_only(state, action.actor_id)
    if state.person(action.person_id).is_founder:
        raise OrgRuleError("the founder is the player: manage the area yourself instead")
    kind = owners.owner_kind(state, company, action.area, action.person_id, balance)
    if kind is None:
        fix = owners.cant_automate(state, company, action.area, balance, data)
        raise OrgRuleError(
            f"{state.person(action.person_id).first_name} cannot run "
            f"{owners.area_def(balance, action.area).label}" + (f": {fix}" if fix else "")
        )
    if action.limit_cents is not None and action.limit_cents < 0:
        raise InvalidActionError("a money limit cannot be negative")
    current = state.area_owner(company, action.area)
    if current is not None and current.person_id == action.person_id:
        raise InvalidActionError("nothing changes")
    state = spend_energy(
        state, action.actor_id, ENERGY_KEY, balance, cost=balance.automation.change_energy
    )
    cash = account_balance(balances, company, CASH)
    limit = (
        action.limit_cents
        if action.limit_cents is not None
        else owners.default_limit(cash, balance)
    )
    theirs = [o.priority for o in state.owners_of(company) if o.person_id == action.person_id]
    priority = action.priority if action.priority is not None else max(theirs, default=-1) + 1
    owner = AreaOwner(company, action.area, action.person_id, limit, priority, state.turn)
    state = with_area_owner(state, owner)
    state = _give_seat(state, company, action.area, action.person_id, balance, data)
    return Outcome(state)


def take_back_area(state: GameState, action: TakeBackArea, balance: Balance) -> Outcome:
    _check_area(action.area, balance)
    company = _founder_only(state, action.actor_id)
    current = state.area_owner(company, action.area)
    if current is None:
        raise InvalidActionError("you already manage that area")
    ab = balance.automation
    state = spend_energy(state, action.actor_id, ENERGY_KEY, balance, cost=ab.change_energy)
    state = without_area_owner(state, company, action.area)
    seat = AREA_SEAT_RULE.get(action.area)
    if seat is not None:  # the seat's authority goes with its area (40.1)
        a = state.authority(company, seat)
        if a is not None and a.enabled and state.seat_holder(company, seat) == current.person_id:
            state = with_authority(state, replace(a, enabled=False))
    person = state.person(current.person_id)
    sting = ""
    recent = state.turn - current.since_turn < ab.take_back_months
    if recent and person.personality["ego"] >= ab.take_back_ego:
        ps = state.person_state(current.person_id)
        if ps.morale is not None:
            state = with_person_state(
                state, replace(ps, morale=clamp_morale(ps.morale - ab.take_back_morale))
            )
            sting = f" {person.first_name} took it badly: it was given only recently."
    log = inbox_item(
        state.turn,
        company,
        "area_taken_back",
        link_kind="automation",
        area=owners.area_def(balance, action.area).label,
        name=f"{person.first_name} {person.last_name}",
        sting=sting,
    )
    return Outcome(state, (), (log,))


def set_area_settings(state: GameState, action: SetAreaSettings, balance: Balance) -> Outcome:
    _check_area(action.area, balance)
    company = _founder_only(state, action.actor_id)
    current = state.area_owner(company, action.area)
    if current is None:
        raise InvalidActionError("give the area to someone first")
    if action.limit_cents is not None and action.limit_cents < 0:
        raise InvalidActionError("a money limit cannot be negative")
    new = replace(
        current,
        limit_cents=current.limit_cents if action.limit_cents is None else action.limit_cents,
        priority=current.priority if action.priority is None else action.priority,
        answer_events=current.answer_events
        if action.answer_events is None
        else action.answer_events,
        allow_bold=current.allow_bold if action.allow_bold is None else action.allow_bold,
    )
    if new == current:
        raise InvalidActionError("nothing changes")
    return Outcome(with_area_owner(state, new))


def apply_automation(
    state: GameState,
    action: AutomationAction,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    match action:
        case SetAreaOwner():
            return set_area_owner(state, action, balance, data, balances)
        case TakeBackArea():
            return take_back_area(state, action, balance)
        case SetAreaSettings():
            return set_area_settings(state, action, balance)


def drop_seat_rows(state: GameState, company: int, seat: str) -> GameState:
    """SetAuthority withdrawing a seat's authority takes back its existing area too (40.1)."""
    from tst.sim.automation.config import SEAT_AREA

    area = SEAT_AREA.get(seat)
    owner = state.area_owner(company, area) if area is not None else None
    if area is None or owner is None or owner.person_id != state.seat_holder(company, seat):
        return state
    return without_area_owner(state, company, area)
