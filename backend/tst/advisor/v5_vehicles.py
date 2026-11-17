"""Explain for M38's numbers (docs/formulas.md 49): a car's unit cost and the battery price.
Public figures only (49.7): this month's market prices, the design's own lines and the plant's
own cost; never a cell plant's hidden overrun, an incident draw or a seeded future price."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.advisor.v3 import _bad, _id, _none
from tst.sim.geopolitics import world
from tst.sim.vehicles import cells
from tst.sim.vehicles import spec as vs
from tst.sim.vehicles.data import file, is_vehicle, year_at

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def car_unit_cost(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A car's bill of materials and assembly at this month's prices (49.1)."""
    if not entity:
        return _none(b, m, "product")
    pid = _id(entity, "product")
    p = b.state.product(pid)
    group = {c.id for c in world.group(b.state)}
    bal, d = b.data.balance, b.data.game_data
    if p is None or p.company_id not in group:
        raise _bad(f"no product {pid} of your group")
    if not is_vehicle(p, bal):
        return b._out(m, entity, None, [], "Only a car line has a car's unit cost.", (), [], p.name)
    spec = vs.spec_of(b.state, p, d)
    capable = vs.capable_level(b.state, spec, p.company_id, bal)
    cost = vs.unit_cost(b.state, p, bal, d, capable)
    months = [x for x in b.state.vehicle_months if x.product_id == pid]
    last = months[-1] if months else None
    battery = last.battery_cents if last is not None else cost.battery
    assembly = last.assembly_cents if last is not None else 0.0
    items = [
        Item(
            f"Pack: {spec.pack_kwh:g} kWh of {spec.chemistry.upper()} cells and integration",
            battery,
            "cents",
        ),
        Item("Motors, inverter and onboard charger", cost.drive, "cents"),
        Item(f"Chips for {bal.vehicles.levels[capable].label}", cost.chips, "cents"),
        Item("Body, chassis and interior (the vehicle components index)", cost.body, "cents"),
        Item("Assembly (plant's cost a car run, or the contract fee)", assembly, "cents"),
    ]
    own = last.own_kwh if last is not None else 0.0
    note = (
        "Cells are bought at this month's market price x the chemistry's and the supplier's "
        "factors; integration is the rest of a pack's price."
        + (
            f" Last month {own:,.0f} kWh came from your own cell plants at their cost."
            if own > 0
            else ""
        )
    )
    total = sum(i.amount for i in items)
    return b._out(m, entity, total, items, note, (), [], p.name)


def battery_price(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """This month's cell price a kWh (49.2): the history's BNEF pack price x the cells' share to
    2025; from 2026 the market's path around the learning curve."""
    bal, d = b.data.balance, b.data.game_data
    v = file(d)
    price = cells.market_cents(b.state, bal, d)
    year = year_at(min(b.state.turn, bal.vehicles.start_turn - 1))
    share = v.battery.cell_share_at(year)
    items = [
        Item("Cells a kWh (the market)", price, "cents"),
        Item("Pack integration a kWh", price / share - price if share else 0.0, "cents"),
    ]
    if b.state.turn < bal.vehicles.start_turn:
        note = (
            "To December 2025 the price is BloombergNEF's volume-weighted pack price x the cells' "
            f"share of a pack ({share:.0%}), in 2010 dollars."
        )
    else:
        note = (
            "From 2026 the price moves around a learning curve: it falls with the world's "
            "cumulative EV cells and moves with lithium, nickel and cobalt; shortages lift it."
        )
    return b._out(m, entity, price, items, note, (), [], "Battery cells")
