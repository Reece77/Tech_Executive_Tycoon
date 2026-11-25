"""Explain for M53's numbers (docs/formulas.md 62): a network's payback in a region. Public figures
only (62.5): the player's own builds, books and months; never a rival's auction value or a seeded
auction, ban or growth rate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.advisor.v3 import _bad, _none
from tst.api.telecom_views import payback_out
from tst.sim.geopolitics import world

if TYPE_CHECKING:
    from tst.advisor.build import Builder

YEAR_MONTHS = 12  # tunable-exempt: calendar


def network_payback(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A region's network: its lines' revenue less hosting, against its sites', radios', fibre's
    and cables' capex and running costs and the spectrum bought there (62.5 target 3)."""
    if not entity:
        return _none(b, m, "region")
    d = b.data.game_data
    if entity not in d.region_keys:
        raise _bad(f"no region {entity!r}")
    group = sorted(c.id for c in world.group(b.state))
    rows = [x for c in group if (x := payback_out(b.state, c, entity, d)) is not None]
    label = d.region(entity).label
    if not rows:
        return b._out(m, entity, None, [], "You have no network here yet.", (), [], label)
    months = [x for x in b.state.telecom.months if x.company_id in group and x.region == entity][
        -YEAR_MONTHS:
    ]
    cash = sum(r.cash_cents for r in rows)
    capex = sum(r.capex_cents for r in rows)
    items = [
        Item(
            "Revenue less subscribers' costs, last 12 months",
            sum(x.revenue_cents for x in months),
            "cents",
        ),
        Item(
            "Capex, running costs and spectrum, last 12 months",
            -sum(x.spend_cents for x in months),
            "cents",
        ),
        Item("Capex paid on its network, all time", capex, "cents"),
    ]
    paid = next((r.paid_back for r in rows if r.paid_back), None)
    to_go = next((r.months_to_payback for r in rows if r.months_to_payback is not None), None)
    if paid:
        note = f"Paid back in {paid}."
    elif to_go is not None:
        note = f"At the last year's rate it pays back in {to_go:,.0f} months."
    else:
        note = "Not earning yet: a network pays back only once its subscribers outrun its costs."
    return b._out(m, entity, cash, items, note, (), [], f"{label} network")
