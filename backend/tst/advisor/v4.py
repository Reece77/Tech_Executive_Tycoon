"""Explain for v4's platform numbers (M31, docs/formulas.md 44): a product's platform fees this
month and a device line's catalogue effect. Public facts only (44.10): the schedules, users and
catalogue indexes the Platforms screen shows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.advisor.v3 import _bad, _id, _none
from tst.sim.geopolitics import world
from tst.sim.platforms import data as pdata
from tst.sim.platforms.fees import fees_due
from tst.sim.platforms.phase import device_catalogue_points

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def _product(b: Builder, entity: str | None) -> int:
    pid = _id(entity, "product")
    product = b.state.product(pid)
    if product is None or product.company_id not in {c.id for c in world.group(b.state)}:
        raise _bad(f"no product {pid} of your group")
    return pid


def platform_fees(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """This month's store fees on an app (44.4): by platform and region."""
    if not entity:
        return _none(b, m, "product")
    pid = _product(b, entity)
    product = b.state.product(pid)
    assert product is not None
    bal, d = b.data.balance, b.data.game_data
    labels = {r.key: r.label for r in d.regions}
    due = fees_due(b.state, bal, d) if b.state.turn >= bal.platforms.fees_turn else {}
    items = []
    for (q, plat, _owner, region), cents in sorted(due.items()):
        if q != pid:
            continue
        p = b.state.platform(plat)
        name = p.store if p is not None else "?"
        items.append(Item(f"{name}, {labels.get(region, region)}", cents, "cents"))
    app = bal.platforms.app_categories.get(product.category)
    share = f"{app.paid_share:.0%}" if app is not None else "none"
    note = (
        f"Each store's effective fee x the {share} of revenue paid through stores x the store's "
        "share of the region's users. Subscriptions after a year, small sellers and regulated "
        "payment paths pay less; a removed app pays nothing there."
    )
    if b.state.turn < bal.platforms.fees_turn:
        note = "Platform fees post from " + bal.platforms.fees_from + ". " + note
    value = sum(i.amount for i in items)
    return b._out(m, entity, value, items, note, (), [], product.name)


def catalogue_effect(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A device line's feature points from its platform's catalogue (44.3), by region."""
    if not entity:
        return _none(b, m, "product")
    pid = _product(b, entity)
    product = b.state.product(pid)
    assert product is not None
    d = b.data.game_data
    if not pdata.enabled(d) or pdata.in_history(b.state.turn, d):
        return b._out(
            m,
            entity,
            None,
            (),
            "The catalogue acts on devices from January 2026.",
            (),
            (),
            product.name,
        )
    labels = {r.key: r.label for r in d.regions}
    items = [
        Item(labels.get(r, r), device_catalogue_points(b.state, pid, r, b.data.balance), "points")
        for r in d.region_keys
    ]
    pb = b.data.balance.platforms
    note = (
        f"{pb.catalogue_points:g} feature points x (the platform's catalogue / the region's leader "
        f"- 1), never below -{pb.catalogue_floor:g}: a thin catalogue makes its devices less "
        "attractive."
    )
    value = min((i.amount for i in items), default=0.0)
    return b._out(m, entity, value, items, note, (), [], product.name)
