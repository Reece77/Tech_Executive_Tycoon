"""The Chair's rules for the CEO (docs/formulas.md 25.6, M13): appointing one, reversing a
decision, and the CEO's price anchors. No imports of the actions package at module level, so
the actions can use these."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import OrgRuleError
from tst.sim.markets_public.config import CEO_SCOPES
from tst.sim.markets_public.models import Ceo
from tst.sim.org.executives import level_allowed
from tst.sim.state import GameState, ceo_of, with_ceo

if TYPE_CHECKING:
    from tst.sim.actions import Action

type Undo = tuple[tuple[str, int | str], ...]


def sales_anchors(
    state: GameState, company_id: int, data: GameData
) -> tuple[tuple[int, str, int], ...]:
    from tst.sim.actions.authority import sales_anchors as anchors

    return anchors(state, company_id, data)


# --- The Chair's actions (25.6) ------------------------------------------------------------------


def appoint(
    state: GameState, company_id: int, person_id: int, balance: Balance, data: GameData
) -> GameState:
    """The rules of appointing a CEO (energy is spent by the action)."""
    company = state.company(company_id)
    if company.stage < balance.ceo.min_stage:
        raise OrgRuleError("a CEO is appointed once the company is public (stage 4)")
    if ceo_of(state, company_id) is not None:
        raise OrgRuleError("the company already has a CEO")
    e = state.employment_of(person_id)
    if e is None or e.company_id != company_id or e.status != "active":
        raise OrgRuleError(f"person {person_id} is not on staff")
    if state.person(person_id).is_founder:
        raise OrgRuleError("the founder steps up to Chair; appoint someone else as CEO")
    if not level_allowed(e.level, balance):
        raise OrgRuleError("a CEO must be at executive level (senior or above)")
    cid, ids = state.next_ids.take("ceo")
    ceo = Ceo(
        id=cid,
        company_id=company_id,
        person_id=person_id,
        since_turn=state.turn,
        scopes=CEO_SCOPES,
        price_anchors=sales_anchors(state, company_id, data),
    )
    return with_ceo(replace(state, next_ids=ids), ceo)


def undo_action(undo: Undo, actor_id: int) -> Action:
    """The action an override applies (25.6)."""
    from tst.sim.actions import ACTION_TYPES

    fields = dict(undo)
    kind = str(fields.pop("kind"))
    if kind == "move_person" and fields.get("unit_id") == "root":
        fields["unit_id"] = None  # type: ignore[assignment]
    action: Action = ACTION_TYPES[kind](actor_id=actor_id, **fields)
    return action


def follow_chair_price(state: GameState, company_id: int, undo: Undo) -> GameState:
    """After an override of a price, the CEO's anchor is the Chair's price."""
    ceo = ceo_of(state, company_id)
    fields = dict(undo)
    if ceo is None or fields.get("kind") != "set_price":
        return state
    key = (int(fields["product_id"]), str(fields["segment"]))
    anchors = {(p, s): c for p, s, c in ceo.price_anchors}
    anchors[key] = int(fields["price_cents"])
    return with_ceo(
        state,
        replace(ceo, price_anchors=tuple(sorted((p, s, c) for (p, s), c in anchors.items()))),
    )
