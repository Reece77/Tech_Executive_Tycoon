"""Explain for the family (M36, formulas.md 45.4, 45.6): an heir's readiness from its
displayed parts, and the estate-tax quote. Public rules and displayed values only."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Driver, Explanation, Item, MetricDef
from tst.sim.family import estate, rules
from tst.sim.state import family_member

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def heir_readiness(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    from tst.advisor.build import InvalidEntityError
    from tst.api.family_views import _readiness

    state = b.state
    try:
        pid = int(entity or "")
    except ValueError as exc:
        raise InvalidEntityError("give a family member's person id") from exc
    member = family_member(state, pid)
    if state.family is None or member is None:
        raise InvalidEntityError(f"person {pid} is not in your family")
    r = _readiness(state, member, b.data)
    if r is None:
        raise InvalidEntityError(f"person {pid} is not one of your children")
    items = [
        Item("CEO-seat fit from what you know of them", r.fit, "points"),
        Item("Years in the group", r.years * b.data.balance.family.ready.per_year, "points"),
        Item("Executive seats held", r.seats * b.data.balance.family.ready.per_seat, "points"),
        Item("The board's confidence", r.board, "points"),
    ]
    bands = b.data.balance.family.ready.bands
    note = (
        f"Readiness is {r.band.replace('_', ' ')}: developing from {bands[0]:.0f} points, "
        f"ready from {bands[1]:.0f}, strong from {bands[2]:.0f}. The fit comes from the ranges "
        "you see, never their true ability; time in the group, seats and mentoring raise it."
    )
    drivers = [Driver(i.label, effect=i.amount, kind="level") for i in items]
    return b._out(m, entity, r.points, items, note, (), drivers, rules.full_name(state.person(pid)))


def estate_tax(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    from tst.db import repository

    state = b.state
    if state.family is None:
        return b._out(m, entity, None, (), "No family: there is no estate plan.", (), ())
    balances = repository.ledger_balances(b.session)
    q = estate.quote(state, state.family.head_id, balances, b.data.balance, b.data.game_data)
    items = [
        Item("Your shares at the share price", float(q.shares_cents), "cents"),
        Item("Personal cash", float(q.cash_cents), "cents"),
        Item("Investments", float(q.other_cents), "cents"),
        Item("Exemption left", float(-(q.exemption_cents - q.used_exemption_cents)), "cents"),
        Item("Taxable estate", float(q.taxable_cents), "cents"),
    ]
    note = (
        f"{q.rate:.0%} of the estate above the exemption ({q.region.replace('_', ' ')}). It is "
        f"paid from cash first, then by selling {q.shares_to_sell:,} shares, taking the family "
        f"from {q.family_bp_now / 100:.1f}% to {q.family_bp_after / 100:.1f}%. Shares in a "
        "trust, gifted or given to the foundation are outside the estate."
    )
    drivers = [Driver(i.label, effect=i.amount, kind="level") for i in items[:4]]
    return b._out(m, entity, float(q.tax_cents), items, note, (), drivers, "The estate")
