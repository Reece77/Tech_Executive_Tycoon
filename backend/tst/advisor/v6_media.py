"""Explain for M55's numbers (docs/formulas.md 65): a title's result and a creative lead's walk.
Public figures only (the brief's hidden-value test): a title's budget, franchise and audience once
released; never a lead's ego, loyalty or true creative and vision, nor an audience before
release."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.advisor.v3 import _bad, _id, _none
from tst.sim import dmath
from tst.sim.media import titles

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def title_result(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A released title's audience against what was expected, and its money (65.2)."""
    if not entity:
        return _none(b, m, "title")
    tid = _id(entity, "title")
    t = b.state.media.title(tid)
    if t is None or t.company_id != b.state.player.id:
        raise _bad(f"no title {tid}")
    if t.stage != "released" or t.audience is None or t.expected is None:
        note = "Not released yet: its audience is drawn at release, from its quality then."
        return b._out(m, entity, None, [], note, (), [], t.name)
    bal = b.data.balance
    kind = bal.media.kind(t.kind)
    budget = float(
        dmath.pow(
            t.budget_cents / titles.typical_budget_cents(kind, bal),  # money-exact: ratio
            bal.media.quality.budget_exponent,
        )
    )
    items = [
        Item("Audience (millions)", t.audience, "count"),
        Item("Expected at release (millions)", t.expected, "count"),
        Item("Revenue booked", t.revenue_cents, "cents"),
        Item("Its share of its service's revenue", t.attributed_cents, "cents"),
        Item("Cost", -t.spent_cents, "cents"),
        Item("Written down or off", -t.written_off_cents, "cents"),
    ]
    ratio = t.audience / t.expected if t.expected else 0.0
    verdict = "a hit" if ratio >= 1 else "below what was expected"
    note = (
        f"It reached {ratio:.0%} of its expected audience: {verdict}. Its quality multiplier was "
        f"{t.quality or 0:.2f}, from its creative lead, team, budget (x {budget:.2f} for its size)"
        + (" and its franchise" if t.sequel_of is not None else "")
        + ". Most titles miss; a few hits earn most of the money."
    )
    return b._out(m, entity, t.audience, items, note, (), [], t.name)


def lead_walk(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """Why a creative lead walked (65.6), from what the player did and could see."""
    if not entity:
        return _none(b, m, "person")
    pid = _id(entity, "person")
    lead = b.state.media.lead(pid)
    if lead is None or lead.walked_turn is None:
        note = "Not a creative lead who walked: a lead walks only after overrules, cuts or moves."
        return b._out(m, entity, None, [], note, (), [], None)
    person = b.state.person(pid)
    name = f"{person.first_name} {person.last_name}"
    mine = [t for t in b.state.media.titles if t.lead_person_id == pid]
    items = [
        Item("Overrules on their titles", sum(t.overrules for t in mine), "count"),
        Item("Budget cuts", sum(t.cuts for t in mine), "count"),
        Item("Moved dates", sum(t.moves for t in mine), "count"),
    ]
    morale = b.state.person_state(pid).morale
    note = (
        "Each overrule, cut or moved date cost them morale, more for a bigger ego; once their "
        f"morale fell under {b.data.balance.media.talent.walk_morale:.0f} each such step could "
        "make them walk, less likely the more loyal they are. They went to the rival with the most "
        "video subscribers, which gets their next title."
    )
    value = round(morale) if morale is not None else None
    return b._out(m, entity, value, items, note, (), [], name)
