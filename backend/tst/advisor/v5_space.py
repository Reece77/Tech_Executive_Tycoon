"""Explain for M40's numbers (docs/formulas.md 56): a launch's price (its vehicle's cost a flight)
and a constellation's payback. Public figures only (56.5): the player's own designs, books and
months; never a failure draw, a licence decision or a seeded rule."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.advisor.v3 import _bad, _id, _none
from tst.api.space_views import flight_cost_out, payback_out
from tst.sim.geopolitics import world
from tst.sim.space.data import is_launch

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def launch_price(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A vehicle line's flight: build share, refurbishment and operations (56.1)."""
    if not entity:
        return _none(b, m, "product")
    pid = _id(entity, "product")
    p = b.state.product(pid)
    group = {c.id for c in world.group(b.state)}
    bal = b.data.balance
    if p is None or p.company_id not in group:
        raise _bad(f"no product {pid} of your group")
    if not is_launch(p, bal):
        return b._out(
            m, entity, None, [], "Only a launch vehicle line has a launch cost.", (), [], p.name
        )
    cost = flight_cost_out(b.state, p, bal)
    if cost is None:
        return b._out(m, entity, None, [], "Set a design first.", (), [], p.name)
    expendable = cost.build_cents * (1 - cost.reused_share)
    reused = cost.build_cents * cost.reused_share / cost.flights_per_vehicle
    refurb = cost.build_cents * cost.reused_share * cost.refurb_share
    items = [
        Item("The part thrown away each flight", expendable, "cents"),
        Item(f"The reused part over its {cost.flights_per_vehicle} flights", reused, "cents"),
        Item("Refurbishment", refurb, "cents"),
        Item("Range, propellant and operations", cost.operations_cents, "cents"),
    ]
    price = next(
        (s.price_cents for s in b.state.segments_of(p.id) if s.segment == "satellite_operators"),
        None,
    )
    note = (
        f"Flown {cost.level.replace('_', ' ')}: {cost.payload_kg:,.0f} kg to low Earth orbit at"
        f" {cost.cost_per_kg_cents / 100:,.0f} dollars a kg, against"
        f" {cost.expendable_per_kg_cents / 100:,.0f} expendable."
        + (f" You charge {price / 100:,.0f} dollars a launch." if price else "")
    )
    return b._out(m, entity, cost.flight_cents, items, note, (), [], p.name)


def constellation_payback(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A constellation's cumulative cash flow and months to payback at the last year's rate."""
    if not entity:
        return _none(b, m, "constellation")
    cid = _id(entity, "constellation")
    c = b.state.space.constellation(cid)
    group = {x.id for x in world.group(b.state)}
    if c is None or c.company_id not in group:
        raise _bad(f"no constellation {cid} of your group")
    pb = payback_out(b.state, c)
    months = [x for x in b.state.space.months if x.constellation_id == c.id][-12:]
    items = [
        Item(
            "Revenue and insurance, last 12 months", sum(x.revenue_cents for x in months), "cents"
        ),
        Item(
            "Satellites, launches, ground stations, disposal, last 12 months",
            -sum(x.spend_cents for x in months),
            "cents",
        ),
        Item("Satellites and launches capitalized", pb.capex_cents, "cents"),
    ]
    if pb.paid_back:
        note = f"Paid back in {pb.paid_back}."
    elif pb.months_to_payback is not None:
        note = f"At the last year's rate it pays back in {pb.months_to_payback:,.0f} months."
    else:
        note = "Not earning yet: it pays back only once its subscribers outrun its replacements."
    return b._out(m, entity, pb.cash_cents, items, note, (), [], c.name)
