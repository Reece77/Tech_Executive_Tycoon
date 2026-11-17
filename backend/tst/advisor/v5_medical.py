"""Explain for M41's numbers (docs/formulas.md 50): a filing's review range and a study's cost.
Public facts only (50.7): the route's window by date, the data's request-for-information months
and fee, and a study's design; never a drawn month, a request before it comes, or a chance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.sim.medical import data as md
from tst.sim.medical import routes

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def medical_review(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A device's review range at a regulator (entity "product_id:regulator")."""
    d, bal = b.data.game_data, b.data.balance
    pid_s, _, reg = (entity or "").partition(":")
    product = b.state.product(int(pid_s)) if pid_s.isdigit() else None
    use = md.use_of(b.state, product, d) if product is not None else None
    if not md.enabled(d) or product is None or use is None or not reg:
        return b._out(m, entity, None, (), "Choose a medical device and a regulator.", (), [])
    route = md.route_for(b.state, use, reg, b.state.turn, d)
    design = md.design_of(b.state, product.id)
    pccp = bool(design and design.pccp)
    lo, hi = md.window(b.state, use, route, b.state.turn, d)
    items = [Item(f"{route.label}: review, {lo}-{hi} months", float(hi), "months")]
    if route.more_info.chance > 0:
        mlo, mhi = route.more_info.months
        items.append(
            Item(f"a request for more information, {mlo}-{mhi} months", float(mhi), "months")
        )
    if pccp:
        items.append(
            Item("the change control plan", float(bal.medical.review.pccp_months), "months")
        )
    shown = routes.shown_range(b.state, use, route, pccp, bal, d)
    note = (
        f"The range is the route's review window this year (medical.yaml, from the regulator's "
        f"goals and observed totals) plus a request's months: about {route.more_info.chance:.0%} "
        f"of {route.label} files get one. The decision's month is drawn when filed and never "
        f"shown; approval reads the device's quality and its evidence. Fee "
        f"${route.fee_cents / 100:,.0f}."
    )
    return b._out(m, entity, float(shown[1]), items, note, (), [], subject=product.name)


def study_cost(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A study's cost from its design (entity: the study id)."""
    d = b.data.game_data
    study = next((s for s in b.state.med_studies if str(s.id) == (entity or "")), None)
    if not md.enabled(d) or study is None:
        return b._out(m, entity, None, (), "No such study.", (), [])
    product = b.state.product(study.product_id)
    category = product.category if product is not None else ""
    per = md.file(d).studies.cost_per_patient_cents.get(category, 0)
    months = max(1, study.due_turn - study.start_turn)
    items = [
        Item(
            f"{study.patients} patients x ${per / 100:,.0f} a patient",
            float(study.cost_cents),
            "cents",
        ),
        Item("spent so far", float(study.spent_cents), "cents"),
    ]
    note = (
        f"A {study.kind.replace('_', '-')} study's cost is its enrolment x the sub-category's cost "
        "a patient (medical.yaml: device trials run about $15,000-75,000 a patient), spent evenly "
        f"over its {months} months to the readout (6500 research). A failed study adds a redesign."
    )
    subject = product.name if product is not None else None
    return b._out(m, entity, float(study.cost_cents), items, note, (), [], subject=subject)
