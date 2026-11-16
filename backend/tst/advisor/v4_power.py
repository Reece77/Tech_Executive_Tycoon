"""Explain for v4's power numbers (M32, docs/formulas.md 46): a region's energy cost last month
and a plant type's levelised cost there. Public figures only (46.9): the grid price, the
settlement's lines and each type's published costs; never a plant's hidden overrun."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.advisor.v3 import _bad, _id, _none
from tst.sim.geopolitics import world
from tst.sim.power import formulas as pf
from tst.sim.power import grid, plants

if TYPE_CHECKING:
    from tst.advisor.build import Builder

CENTS = 100


def energy_cost(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """Last month's energy in a region (46.1-46.2): what the facilities paid at the grid price,
    less the energy own plants and PPAs replaced, plus their costs, less exports."""
    if not entity:
        return _none(b, m, "region")
    d = b.data.game_data
    if entity not in d.region_keys:
        raise _bad(f"no region {entity!r}")
    group = {c.id for c in world.group(b.state)}
    months = [x for x in b.state.power_months if x.company_id in group and x.region == entity]
    last = max((x.turn for x in months), default=None)
    rows = [x for x in months if x.turn == last]
    grid_c = sum(x.grid_cents for x in rows)
    net = sum(x.net_cents for x in rows)
    items = [Item("Energy at the grid price", grid_c, "cents")]
    for p in b.state.plants:
        f = b.state.facility(p.facility_id)
        if f is None or f.region != entity or p.company_id not in group or p.month is None:
            continue
        pm = p.month
        if pm.turn != last:
            continue
        name = plants.plant_name(b.state, p, d)
        items.append(Item(f"{name}: grid energy it replaced", -pm.displaced_cents, "cents"))
        items.append(
            Item(
                f"{name}: fuel, operations, carbon and grid charges",
                pm.fuel_cents + pm.om_cents + pm.grid_charge_cents,
                "cents",
            )
        )
        if pm.export_cents:
            items.append(Item(f"{name}: surplus sold", -pm.export_cents, "cents"))
    for c in b.state.ppas:
        if c.company_id in group and c.region == entity and c.paid_cents:
            items.append(Item(f"PPA {c.id} ({c.producer}): payments", c.paid_cents, "cents"))
    rest = net - sum(i.amount for i in items)
    if abs(rest) >= 1:
        items.append(Item("PPA energy it replaced at the grid price", rest, "cents"))
    price = grid.price_cents(b.state, entity, b.data.balance, d) / CENTS
    note = (
        f"The grid price in {d.region(entity).label} is ${price:,.2f} a MWh this month: the "
        "region's power index (from 2026 with its market's balance factor and the change in "
        "carbon prices since 2025). Own plants and PPAs replace grid energy at that price and "
        "charge their own costs; behind-the-meter plants pay no grid charges."
    )
    return b._out(m, entity, net, items, note, (), [], d.region(entity).label)


def plant_levelised(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A plant's type's levelised cost where it stands (46.6): capital, fixed and variable
    costs a MWh at the published capex (the quote's, never the overrun)."""
    if not entity:
        return _none(b, m, "plant")
    fid = _id(entity, "plant")
    p = plants.plant_of(b.state, fid)
    group = {c.id for c in world.group(b.state)}
    if p is None or p.company_id not in group:
        raise _bad(f"no plant {fid} of your group")
    bal, d = b.data.balance, b.data.game_data
    f = plants.facility_of(b.state, p)
    t = plants.type_def(d, p.type)
    year = grid.year_of(b.state.turn)
    cf = plants.capacity_factor(t, f.region)
    mwh_kw = pf.HOURS_A_YEAR * cf / pf.KW_PER_MW
    capex = plants.capex_kw(b.state, p.type, bal, d)
    rate = bal.power.plants.discount_rate
    capital = capex * pf.crf(rate, t.life_years) / mwh_kw if mwh_kw else 0.0
    fixed = t.fixed_om_at(year) / mwh_kw if mwh_kw else 0.0
    variable = plants.marginal_usd_mwh(b.state, p.type, f.region, bal, d)
    items = [
        Item("Capital a MWh", capital * CENTS, "cents"),
        Item("Fixed operations a MWh", fixed * CENTS, "cents"),
        Item("Fuel, variable operations and carbon a MWh", variable * CENTS, "cents"),
    ]
    note = (
        f"${capex:,.0f} a kW over {t.life_years} years at {rate:.0%}, at a {cf:.0%} capacity "
        f"factor ({mwh_kw:,.2f} MWh a kW a year). Costs are in 2010 dollars, as the game's."
    )
    value = (capital + fixed + variable) * CENTS
    return b._out(m, entity, value, items, note, (), [], plants.plant_name(b.state, p, d))
