"""Explain for M34's numbers (docs/formulas.md 48): the group's regulatory fines, case by case,
and its position against each regime's designation thresholds. Public facts only (48.6): the
fines posted and the thresholds in regulation.yaml; never a case's chance or a drawn month."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.sim.regulation import data as rdata
from tst.sim.regulation.designate import ratio
from tst.sim.regulation.measure import view
from tst.sim.state import owner_of

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def regulation_fines(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """The group's fines and settlements by case (48.3), as posted."""
    d, bal = b.data.game_data, b.data.balance
    if not rdata.enabled(d):
        return b._out(m, entity, None, (), "No regulation in this game.", (), [])
    me = owner_of(b.state, b.state.player.id)
    rf = rdata.file(d)
    items = [
        Item(
            f"{rf.regulator(c.regulator).name}, case {c.id} ({c.outcome})",
            c.fine_cents if c.outcome != "annulled" else 0,
            "cents",
        )
        for c in b.state.reg_cases
        if c.company_id == me and c.fine_cents > 0
    ]
    lo, hi = bal.regulation.fine.share
    note = (
        f"A fine is {lo:.1%}-{hi:.0%} of the group's turnover over the last year, by the case's "
        f"gravity, x{bal.regulation.fine.noncompliance_mult:g} while a duty is broken, capped at "
        f"the regime's maximum (the DMA's 10%; 20% for a repeat within 10 years). Settling after "
        f"the charges pays {bal.regulation.fine.settle_share:.0%} of a typical fine; a won appeal "
        "returns it. Periodic penalties after a structural order's deadline post here too."
    )
    return b._out(m, entity, sum(i.amount for i in items), items, note, (), [])


def designation_thresholds(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """The group's ratio against each regime's thresholds (48.1): 1 or more meets them."""
    d, bal = b.data.game_data, b.data.balance
    if not rdata.enabled(d):
        return b._out(m, entity, None, (), "No regulation in this game.", (), [])
    me = owner_of(b.state, b.state.player.id)
    v = view(b.state, bal, d)
    regimes = [g for g in rdata.file(d).regimes if entity in (None, "", g.key)]
    items = [
        Item(g.name, round(min(ratio(b.state, g, me, v, None, bal, d), 10.0) * 100, 1), "percent")
        for g in regimes
    ]
    note = (
        "Each December the test reads the largest share of the regulator's region's users on a "
        "platform the group owns against the regime's users threshold (the DMA's 45 million is "
        "10% of the EU), and its turnover there against the money threshold (the DMA's EUR 7.5 "
        f"billion). The smaller ratio counts: from {bal.regulation.warn_ratio:.0%} a warning, at "
        "100% a year after one a designation."
    )
    value = max((i.amount for i in items), default=0.0)
    return b._out(m, entity, value, items, note, (), [])
