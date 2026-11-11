"""Explain on v3's numbers (M23c sub-task 7, M25's follow-up): a project's NPV, a mine's cost a
tonne, a fab's cost per good die and a refinery's cost a unit. Every value is one the screens
already show (the study's ranges, the mine's and plant's public months); nothing reads a
hidden overrun, grade or yield."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from tst.advisor.model import Driver, Explanation, Item, MetricDef, Point

if TYPE_CHECKING:  # build imports this module: its error class is read at call time
    from tst.advisor.build import Builder

CENTS: Final = 100  # tunable-exempt: unit conversion


def _bad(message: str) -> Exception:
    from tst.advisor.build import InvalidEntityError

    return InvalidEntityError(message)


def _id(entity: str | None, what: str) -> int:
    try:
        return int(entity or "")
    except ValueError as exc:
        raise _bad(f"a {what} metric needs a {what} id") from exc


def _group(b: Builder) -> set[int]:
    from tst.sim.exploration import pipeline as xp

    return {c.id for c in xp.explorers(b.state)}


def mine_npv(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A project's NPV range from its latest study (34.3)."""
    from tst.sim.exploration import pipeline as xp

    pid = _id(entity, "project")
    project = next((p for p in b.state.projects if p.id == pid), None)
    if project is None or project.company_id not in _group(b):
        raise _bad(f"no project {pid} of your group")
    if project.npv_mid_cents is None:
        return b._out(
            m,
            entity,
            None,
            (),
            "No feasibility study yet: a scoping study gives the first NPV.",
            (),
            (),
            xp.label_of(project),
        )
    items = [
        Item(
            "NPV if every range lands at its worst end", float(project.npv_lo_cents or 0), "cents"
        ),
        Item("NPV from the middle of every range", float(project.npv_mid_cents), "cents"),
        Item("NPV if every range lands at its best end", float(project.npv_hi_cents or 0), "cents"),
    ]
    if project.capex_center is not None:
        items.append(Item("Capex estimate (mid)", float(project.capex_center) * CENTS, "cents"))
    level = (project.level or "").replace("_", "-")
    note = (
        f"The {level} study's NPV: each year's cash from the estimated tonnage, grade and "
        "recovery at the price deck, less the capex and operating cost ranges, discounted to "
        "today. The range narrows with a better resource category and a later study; the "
        "deposit's truth is never shown."
    )
    drivers = [
        Driver(
            "Range low to high",
            effect=float((project.npv_hi_cents or 0) - (project.npv_lo_cents or 0)),
            kind="level",
        ),
    ]
    return b._out(
        m, entity, float(project.npv_mid_cents), items, note, (), drivers, xp.label_of(project)
    )


def mine_cost(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A mine's all-in sustaining cost a tonne, month by month (35.3)."""
    from tst.sim.mining.actions import mine_name

    mid = _id(entity, "mine")
    mine = b.state.mine(mid)
    if mine is None or mine.company_id not in _group(b):
        raise _bad(f"no mine {mid} of your group")
    name = mine_name(mine, b.data.game_data)
    months = [h for h in mine.history if h.turn >= b.since]
    if not months:
        return b._out(m, entity, None, (), "No production month yet.", (), (), name)
    last = months[-1]
    items = (
        Item("All-in sustaining cost a tonne", last.cost_usd_t * CENTS, "cents"),
        Item("Price a tonne (spot)", last.price_usd_t * CENTS, "cents"),
        Item("Margin a tonne", (last.price_usd_t - last.cost_usd_t) * CENTS, "cents"),
        Item("Output last month (t)", last.output_t, "count"),
    )
    trend = tuple(Point(h.turn, h.cost_usd_t * CENTS) for h in months)
    drivers = []
    if len(months) >= 2:
        prev = months[-2]
        drivers.append(
            Driver(
                "Reconciled grade",
                change=(last.grade - prev.grade) * CENTS,
                unit="percent",
            )
        )
        drivers.append(Driver("Output", change=last.output_t - prev.output_t, unit="count"))
    note = (
        "Mining, processing, royalties and sustaining capital over the month's product. A lower "
        "reconciled grade or a smaller output spreads the same costs over fewer tonnes."
    )
    return b._out(m, entity, last.cost_usd_t * CENTS, items, note, trend, drivers, name)


def fab_die_cost(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A fab's cost a wafer start and per good die (38.2)."""
    from tst.api.fab_views import _die
    from tst.sim.fabs.market import fab_of

    fid = _id(entity, "fab")
    fab = fab_of(b.state, fid)
    if fab is None or fab.company_id not in _group(b):
        raise _bad(f"no fab {fid} of your group")
    month = fab.month
    subject = f"Fab #{fid}"
    if month is None or month.run <= 0:
        return b._out(m, entity, None, (), "No production month yet.", (), (), subject)
    own, _ = _die(b.state, fab, month, b.data)
    run = month.run
    items = (
        Item("Depreciation a start", month.depreciation_cents / run, "cents"),
        Item("Fixed costs a start", month.fixed_cents / run, "cents"),
        Item("Materials a start", month.materials_cents / run, "cents"),
        Item("Power a start", month.power_cents / run, "cents"),
        Item("Engineers a start", month.staff_cents / run, "cents"),
        Item("Cost a start", month.cost_per_start_cents, "cents"),
    )
    trend = tuple(Point(t, c) for t, _y, _u, c, _mk in fab.history if t >= b.since)
    drivers = [
        Driver("Utilization", change=month.utilization * CENTS, unit="percent", kind="level"),
        Driver("Fab yield", change=month.yield_ * CENTS, unit="percent", kind="level"),
    ]
    note = (
        "A start's full cost (depreciation, fixed costs, materials, power, engineers) over the "
        "good dies on it at the fab's yield; an idle start's share of the fixed costs falls on "
        "the rest, so utilization and yield drive the cost per good die."
    )
    return b._out(m, entity, own, items, note, trend, drivers, subject, "Cost a wafer start")


def refinery_cost(b: Builder, m: MetricDef, entity: str | None) -> Explanation:
    """A refinery's cost a unit of output last month (36.1)."""
    from tst.sim.refining.plants import refinery_of

    fid = _id(entity, "refinery")
    ref = refinery_of(b.state, fid)
    if ref is None or ref.company_id not in _group(b):
        raise _bad(f"no refinery {fid} of your group")
    subject = f"Refinery #{fid}"
    month = ref.month
    if month is None or month.output <= 0:
        return b._out(m, entity, None, (), "No production month yet.", (), (), subject)
    made = month.output
    items = (
        Item("Input a unit", month.input_cents / made, "cents"),
        Item("Power a unit", month.power_cents / made, "cents"),
        Item("Other costs a unit", month.other_cents / made, "cents"),
        Item("Fixed costs a unit", month.fixed_cents / made, "cents"),
        Item("Depreciation a unit", month.depreciation_cents / made, "cents"),
        Item("Staff a unit", month.staff_cents / made, "cents"),
    )
    value = month.unit_cost_cents
    trend = tuple(Point(t, unit) for t, _out, unit, _mk in ref.history if t >= b.since)
    note = (
        "The month's input, power, other, fixed, depreciation and staff costs over its output; a "
        "plant running below capacity spreads its fixed costs over fewer units."
    )
    return b._out(m, entity, value, items, note, trend, [], subject)
