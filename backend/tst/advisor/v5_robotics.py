"""Explain for M39's numbers (docs/formulas.md 53): a plant's automation saving and a robotaxi
zone's contribution a ride. Public figures only (53.5): the plant's own costs, the region's
published labour cost and the zone's own month; never an incident or approval draw."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.advisor.v3 import _bad, _id, _none
from tst.sim.geopolitics import world
from tst.sim.robotics import automation
from tst.sim.robotics import robotaxi as rt

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def automation_saving(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A plant's conversion cost a unit without and with its robots (53.1)."""
    if not entity:
        return _none(b, m, "plant")
    fid = _id(entity, "plant")
    f = b.state.facility(fid)
    group = {c.id for c in world.group(b.state)}
    bal, d = b.data.balance, b.data.game_data
    if f is None or f.company_id not in group:
        raise _bad(f"no plant {fid} of your group")
    if f.kind not in bal.robotics.automation.plant_kinds:
        return b._out(
            m, entity, None, [], "Only an assembly or vehicle plant takes robots.", (), [], ""
        )
    a = b.state.plant_automation(fid)
    robots = a.robots if a is not None else 0
    without = automation.unit_cost_report(b.state, f, 0, bal, d)
    with_ = automation.unit_cost_report(b.state, f, robots, bal, d)
    items = [
        Item("Line labour a unit without robots", without["labour"], "cents"),
        Item(f"Labour the {robots:,} robots replace a unit", -with_["saved"], "cents"),
        Item("Robots' depreciation and service a unit at full use", with_["robots"], "cents"),
    ]
    wage = automation.wage_month_cents(b.state, f.region, bal, d)
    note = (
        f"Automation {with_['level']:.0%} of the line's labour. A robot replaces"
        f" {bal.robotics.automation.labour_per_robot:g} worker's labour at this region's wage"
        f" ({wage / 100:,.0f} dollars a month), never more than the plant's own line labour, so"
        " robots pay where labour is dear."
    )
    total = sum(i.amount for i in items[1:])
    return b._out(m, entity, -total, items, note, (), [], f"Plant {fid}")


def ride_contribution(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A zone's last month a ride: the fare less energy, cleaning, insurance, remote assistance
    and the cars' depreciation (53.3)."""
    if not entity:
        return _none(b, m, "zone")
    zid = _id(entity, "zone")
    z = b.state.zone(zid)
    group = {c.id for c in world.group(b.state)}
    bal, d = b.data.balance, b.data.game_data
    if z is None or z.company_id not in group:
        raise _bad(f"no zone {zid} of your group")
    month = z.month
    c = rt.city(d, z.city)
    if month is None or month.rides <= 0:
        be = rt.breakeven_rides(c, bal, rt.car_cents_for_zone(b.state, z, bal, d))
        note = f"No rides last month. A car breaks even at {be:.1f} rides a day at this fare."
        return b._out(m, entity, None, [], note, (), [], c.label)
    n = month.rides
    items = [
        Item("Fare a ride", month.revenue_cents / n, "cents"),
        Item("Energy", -month.energy_cents / n, "cents"),
        Item("Cleaning", -month.cleaning_cents / n, "cents"),
        Item("Insurance", -month.insurance_cents / n, "cents"),
        Item("Remote assistance", -month.remote_cents / n, "cents"),
        Item("Cars' depreciation", -month.depreciation_cents / n, "cents"),
    ]
    days = bal.robotics.robotaxi.days_per_month
    note = (
        f"{n:,.0f} rides on {month.cars:,} cars: {n / max(1, month.cars) / days:.1f} a car a day,"
        f" utilisation {month.utilisation:.0%}. Insurance, remote assistance and depreciation are"
        " a car's month whatever it drives, so the more rides a car, the less each one carries."
    )
    return b._out(m, entity, month.contribution_cents / n, items, note, (), [], c.label)
