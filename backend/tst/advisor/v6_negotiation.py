"""Explain for M47's numbers (docs/formulas.md 58.2): a negotiation's revealed range. Built from
the public view only (tst.conversations.view, 58.6): the range's ends, the rounds played and
what narrows it, never the reservation value, the counterpart's openness or a draw."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.advisor.v3 import _bad, _id, _none
from tst.conversations import store
from tst.conversations.view import public
from tst.db.models import ConversationRow

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def negotiation_range(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    if not entity:
        return _none(b, m, "negotiation")
    row = b.session.get(ConversationRow, _id(entity, "negotiation"))
    if row is None:
        raise _bad(f"no negotiation {entity}")
    v = public(store.load(row.state), b.data.balance.negotiation)
    items: list[Item] = []
    for term, r in zip(v.terms, v.ranges, strict=True):
        cents = term.unit == "cents"
        scale = 1 if cents else 0.01  # basis points shown as percent
        items.append(Item(f"{term.label}: low end", r.lo * scale, "cents" if cents else "percent"))
        items.append(Item(f"{term.label}: high end", r.hi * scale, "cents" if cents else "percent"))
    items.append(Item("Rounds played", len(v.rounds), "count"))
    note = (
        f"{v.counterpart_name}'s walk-away point lies in this range. It starts wide and narrows "
        "each round, faster with a counterpart who is open and for a better negotiator "
        "(negotiation, communication and strategy). It is never exact, and it is shown rounded "
        "in their favour: offering at its edge is a risk, and a threat to walk with an offer "
        "beyond their limit ends the talks."
    )
    shown = "; ".join(r.shown for r in v.ranges)
    return b._out(m, entity, None, items, f"{shown}. {note}", (), [], v.subject)
