"""Explain for M42's numbers (docs/formulas.md 55): a programme's chance to approval and expected
value (rNPV), and its next trial's cost. Public facts only (55.7): the efficacy estimate's range,
the shown chances, the stages' designs and the data; never a molecule's hidden values or a draw."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tst.advisor.model import Explanation, Item, MetricDef
from tst.sim.pharma import data as pd
from tst.sim.pharma import pipeline, value
from tst.sim.pharma.config import TRIALS, Design
from tst.sim.pharma.models import Programme

if TYPE_CHECKING:
    from tst.advisor.build import Builder


def _programme(b: Builder, entity: str | None) -> Programme | None:
    return next((p for p in b.state.pharma_programmes if str(p.id) == (entity or "")), None)


def pharma_value(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A programme's chance to approval and rNPV (entity: the programme id)."""
    d, bal = b.data.game_data, b.data.balance
    p = _programme(b, entity)
    if not pd.enabled(d) or p is None:
        return b._out(m, entity, None, (), "Choose a programme.", (), [])
    v = value.explain(p, bal, d, b.state)
    lo, hi = pipeline.estimate_range(p, bal)
    items = [
        Item(
            f"efficacy estimate {lo:.2f}-{hi:.2f} (standard of care "
            f"{pd.indication(d, p.indication).soc:.2f})",
            hi * 100,
            "points",
        ),
        Item(
            f"chance to approval, {v.chance_lo:.0%}-{v.chance_hi:.0%}", v.chance_hi * 100, "percent"
        ),
        Item("peak sales a year, low", float(v.peak_lo_cents), "cents"),
        Item("peak sales a year, high", float(v.peak_hi_cents), "cents"),
        Item("trials still to run", float(-v.cost_left_cents), "cents"),
        Item("rNPV, low", float(v.rnpv_lo_cents), "cents"),
    ]
    note = (
        "Each remaining stage's chance is its area's published rate (BIO 2021) moved by the "
        "efficacy and safety estimates and the design; the product with the submission's is the "
        "chance to approval. Sales are the indication's treated patients at the estimate's share "
        "against the standard of care, ramping over the launch years, at the reference price less "
        f"contract manufacturing, discounted at {bal.pharma.discount_rate:.1%} a year. The "
        "molecule's true efficacy is never known: the range narrows with each readout."
    )
    return b._out(m, entity, float(v.rnpv_hi_cents), items, note, (), [], subject=p.name)


def trial_cost(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A programme's current or next stage's cost from its design (entity: the programme id)."""
    d, bal = b.data.game_data, b.data.balance
    p = _programme(b, entity)
    if not pd.enabled(d) or p is None:
        return b._out(m, entity, None, (), "Choose a programme.", (), [])
    stage = pipeline.next_trial(p) if p.status == "ready" else p.stage
    if stage is None:
        return b._out(m, entity, None, (), f"{p.name} has no trial to run.", (), [])
    design: Design = "standard" if p.status == "ready" else p.design
    months = pipeline.stage_months(p, stage, design, bal, d)
    n = pipeline.stage_patients(stage, design, d) if stage in TRIALS else 0
    cost = pipeline.stage_cost_cents(p, stage, n, months, bal, d)
    sd = pd.file(d).stages.of(stage)
    area, mod = pd.area(d, p.area), pd.modality(d, p.modality)
    items = [
        Item(
            f"{n} patients x ${sd.cost_per_patient:,.0f} x {area.cost_mult:g} ({area.label}) "
            f"x {mod.cost_mult:g} ({mod.label})",
            float(cost),
            "cents",
        ),
        Item(f"{months} months", float(months), "months"),
    ]
    note = (
        "A trial costs its patients x the stage's cost a patient (Moore et al. 2020; Martin et al. "
        "2017) x the area's and modality's factors, plus a fixed part, at the game's scale "
        f"(x{bal.pharma.scale}), spent evenly to the readout (6500 research)."
    )
    return b._out(m, entity, float(cost), items, note, (), [], subject=p.name)
