"""Scale-up views (M8, formulas.md 18.8): divisions, support coverage, cross-division
products, executive seats with fit and estimated effects, and division statements.

Seat fit and estimates come from the company's displayed ranges (their midpoints), never
from true skills: s and e stay inside the sim.
"""

from __future__ import annotations

from collections.abc import Sequence

from tst.api.finance_views import _label
from tst.api.schemas.saves import SupportTileOut
from tst.api.schemas.scaleup import (
    AppointCandidateOut,
    CrossDivisionOut,
    DivisionColumnOut,
    DivisionOut,
    DivisionPeriodOut,
    DivisionStatementsOut,
    ScaleupOut,
    SeatCandidatesOut,
    SeatOut,
    SupportPoolOut,
)
from tst.api.views import person_name, role_label
from tst.loader import LoadedData
from tst.sim.actions.scaleup import appoint_problem
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import AccountType, Balance
from tst.sim.finance import statements as fs
from tst.sim.finance.divisions import DivisionLines, DivisionStatement, division_report
from tst.sim.hiring.formulas import energy_cost
from tst.sim.org import executives as ex
from tst.sim.org.divisions import (
    company_divisions,
    division_headcounts,
    division_of_unit,
    is_scaleup,
    product_division_spread,
    support_pools,
)
from tst.sim.org.formulas import seat_effect, support_factor, support_morale
from tst.sim.org.models import SEATS
from tst.sim.org.rules import org_view
from tst.sim.snapshot import DivisionMonth
from tst.sim.state import GameState

PCT = 100
NOTE = "Fit and effects are estimates from what you know about each person."
EFFECT_LABELS = {
    "coo": "layer tax and support shortfall",
    "cfo": "investors' valuation and board confidence",
    "cto": "builder output and the quality cap",
    "cpo": "features gained (and lower churn)",
    "cmo": "marketing points (and brand and awareness)",
    "cro": "seller capacity (and pricing power in sales-led segments)",
}
FIT_WORDS = ("weak fit", "fair fit", "strong fit")


def estimated_score(
    state: GameState, company_id: int, person_id: int, seat: str, b: Balance
) -> float:
    """s from the displayed ranges' midpoints (18.8)."""
    return ex.displayed_score(state, company_id, person_id, seat, b)


def fit_word(score: float, b: Balance) -> str:
    bands = b.exec_seats.fit_bands
    if score < bands.lo:
        return FIT_WORDS[0]
    return FIT_WORDS[2] if score >= bands.hi else FIT_WORDS[1]


def effect_pct(seat: str, e: float, b: Balance) -> float:
    """The seat's change in percent for an effect strength e (18.3). For the COO: the change
    in the layer tax and support shortfall (k_COO - 1, as a percentage)."""
    coefficient = b.exec_seats.seats[seat].effect
    if seat == ex.COO:
        return round(-coefficient * e * PCT, 1)
    return round(coefficient * e * PCT, 1)


def _seat_out(state: GameState, company_id: int, seat: str, data: LoadedData) -> SeatOut:
    b = data.balance
    holder = state.seat_holder(company_id, seat)
    in_play = ex.seats_in_play(state, company_id, b)
    fit = est = None
    name = None
    if holder is not None and state.employment_of(holder) is not None:
        score = estimated_score(state, company_id, holder, seat, b)
        fit = fit_word(score, b)
        est = effect_pct(seat, seat_effect(score, b.exec_seats), b)
        name = person_name(state.person(holder))
    else:
        holder = None
    return SeatOut(
        seat=seat,
        label=b.exec_seats.seats[seat].label,
        effect_label=EFFECT_LABELS[seat],
        holder_id=holder,
        holder_name=name,
        fit=fit,
        estimated_effect_pct=est,
        vacancy_penalty_pct=(
            effect_pct(seat, b.exec_seats.vacant_effect, b) if in_play and holder is None else None
        ),
    )


def scaleup_out(
    state: GameState, data: LoadedData, last_profit: dict[int, int] | None = None
) -> ScaleupOut:
    b = data.balance
    company = state.player
    view = org_view(state, company.id)
    heads = division_headcounts(view)
    divisions = company_divisions(state, company.id)
    k = ex.k_coo(state, company.id, b)
    out_divisions = []
    for d in divisions:
        products = [p for p in state.company_products(company.id) if p.division_id == d.id]
        leader = d.leader_id
        deep = any(
            u.kind == "team"
            and u.parent_id is not None
            and u.parent_id in view.units
            and view.units[u.parent_id].parent_id == d.id
            for u in view.units.values()
        )
        if d.embedded:
            note = f"Embedded services: output and capacity x{b.org.embedded_bonus:.2f}"
        elif deep:
            note = f"Teams at depth 3 pay the layer tax: output -{b.org.layer_tax * k * PCT:.1f}%"
        else:
            note = "Central services: it takes a share of corporate costs by headcount"
        out_divisions.append(
            DivisionOut(
                unit_id=d.id,
                name=d.name,
                president_id=leader,
                president_name=person_name(state.person(leader)) if leader else None,
                services=d.services or "central",
                headcount=heads.get(d.id, 0),
                unit_ids=[
                    u.id
                    for u in view.units.values()
                    if u.id != d.id and division_of_unit(view.units, u.id) == d.id
                ],
                product_ids=[p.id for p in products],
                product_names=[p.name for p in products],
                operating_profit_cents=(last_profit or {}).get(d.id),
                effect_note=note,
            )
        )
    support = []
    if is_scaleup(company, b):
        for key, pool in support_pools(state, view, b, data.game_data).items():
            unit = state.unit(key) if key is not None else None
            factor = support_factor(pool.coverage, k, b.org)
            support.append(
                SupportPoolOut(
                    key="central" if key is None else str(key),
                    label="Corporate and central divisions" if unit is None else unit.name,
                    headcount=pool.headcount,
                    support_staff=pool.support,
                    needed=pool.need,
                    covered=pool.coverage >= 1,
                    output_effect_pct=round((factor - 1) * PCT, 1),
                    morale_effect=round(support_morale(pool.coverage, b.org), 1),
                )
            )
    names = {d.id: d.name for d in divisions}
    cross = []
    for product in state.company_products(company.id):
        if product.status == "retired" or product.is_static:
            continue
        spread = product_division_spread(state, view, product)
        if len(spread) > 1:
            cross.append(
                CrossDivisionOut(
                    product_id=product.id,
                    product_name=product.name,
                    division_names=sorted(
                        names.get(d, "Corporate") if d else "Corporate" for d in spread
                    ),
                    output_effect_pct=round((b.org.cross_division_factor - 1) * PCT, 1),
                    fix="Move every unit working on it into one division (or corporate)",
                )
            )
    return ScaleupOut(
        stage=company.stage,
        in_play=is_scaleup(company, b),
        unlock_stage=b.org.division_stage,
        max_divisions=b.org.max_divisions,
        divisions=out_divisions,
        support=support,
        support_rule=(
            f"One support person per {b.org.support_ratio:.0f} staff: finance, recruiting or "
            "operations roles, and executives"
        ),
        cross_division=cross,
        seats=[_seat_out(state, company.id, seat, data) for seat in SEATS],
        note=NOTE,
    )


def seat_candidates_out(state: GameState, seat: str, data: LoadedData) -> SeatCandidatesOut:
    b = data.balance
    company = state.player.id
    out = []
    for e in sorted(state.staff(company), key=lambda e: e.person_id):
        person = state.person(e.person_id)
        if person.is_founder:
            continue
        score = estimated_score(state, company, person.id, seat, b)
        out.append(
            AppointCandidateOut(
                person_id=person.id,
                name=person_name(person),
                role=role_label(e.role, data) or e.role,
                level=e.level,
                fit=fit_word(score, b),
                estimated_effect_pct=effect_pct(seat, seat_effect(score, b.exec_seats), b),
                problem=appoint_problem(state, company, seat, person.id, b),
            )
        )
    out.sort(key=lambda c: (c.problem is not None, -c.estimated_effect_pct, c.person_id))
    return SeatCandidatesOut(
        seat=_seat_out(state, company, seat, data),
        candidates=out,
        energy_cost=energy_cost("appoint_executive", b),
        note=(
            "Appointing makes them exec level, with the exec market rate (so raise them too), "
            f"and +{b.exec_seats.appoint_morale:.0f} morale. {NOTE}"
        ),
    )


def _column(st: DivisionStatement) -> DivisionColumnOut:
    margin = st.operating_profit / st.revenue if st.revenue else None
    return DivisionColumnOut(
        division_id=st.division_id,
        name=st.name,
        embedded=st.embedded,
        headcount=st.headcount,
        revenue_cents=st.revenue,
        salaries_benefits_cents=st.salaries_benefits,
        hosting_cents=st.hosting,
        marketing_cents=st.marketing,
        office_cents=st.office,
        tools_ga_cents=st.tools_ga,
        direct_profit_cents=st.direct_profit,
        shared_services_cents=st.shared_services,
        operating_profit_cents=st.operating_profit,
        operating_margin=round(margin, 4) if margin is not None else None,
        revenue_growth_12m=None,
    )


def division_statements_out(
    state: GameState,
    lines: DivisionLines,
    months: Sequence[DivisionMonth],
    period: fs.Period,
    data: LoadedData,
) -> DivisionStatementsOut:
    """Every closed period, newest first: corporate, each division, and the company."""
    types: dict[str, AccountType] = {a.code: a.type for a in data.game_data.accounts}
    lines = list(lines)
    names = {u.id: u.name for u in company_divisions(state, state.player.id)}
    last_closed = state.turn - 1
    periods = []
    if last_closed >= 0:
        for first, last in reversed(fs.period_bounds(period, last_closed)):
            report = division_report(lines, months, types, first, last, names)
            prior = (
                division_report(
                    lines,
                    months,
                    types,
                    max(0, last - 2 * MONTHS_PER_YEAR + 1),
                    last - MONTHS_PER_YEAR,
                )
                if last >= 2 * MONTHS_PER_YEAR - 1
                else None
            )
            year = division_report(lines, months, types, last - MONTHS_PER_YEAR + 1, last)
            prior_rev = {c.division_id: c.revenue for c in prior.columns} if prior else {}
            year_rev = {c.division_id: c.revenue for c in year.columns}
            cols = []
            for c in [*report.columns, report.company]:
                col = _column(c)
                base: int | None
                if prior is not None:
                    if c is report.company:
                        cur, base = year.company.revenue, prior.company.revenue
                    else:
                        cur, base = year_rev.get(c.division_id, 0), prior_rev.get(c.division_id)
                    if base:
                        col.revenue_growth_12m = round((cur - base) / base, 4)
                cols.append(col)
            periods.append(
                DivisionPeriodOut(
                    first_turn=first, last_turn=last, label=_label(period, first), columns=cols
                )
            )
    return DivisionStatementsOut(period=period, periods=periods)


def last_month_profit(
    lines: DivisionLines, months: Sequence[DivisionMonth], state: GameState, data: LoadedData
) -> dict[int, int]:
    """Each division's operating profit in the last closed month (Org cards)."""
    if state.turn < 1:
        return {}
    types: dict[str, AccountType] = {a.code: a.type for a in data.game_data.accounts}
    report = division_report(lines, months, types, state.turn - 1, state.turn - 1)
    return {c.division_id: c.operating_profit for c in report.columns if c.division_id is not None}


def support_tile(state: GameState, data: LoadedData) -> SupportTileOut | None:
    """Support staff against need over every pool, from stage 3 (18.4)."""
    b = data.balance
    if not is_scaleup(state.player, b):
        return None
    view = org_view(state, state.player.id)
    pools = support_pools(state, view, b, data.game_data).values()
    k = ex.k_coo(state, state.player.id, b)
    worst = min(support_factor(p.coverage, k, b.org) for p in pools)
    return SupportTileOut(
        support_staff=sum(p.support for p in pools),
        needed=sum(p.need for p in pools),
        pools_short=sum(1 for p in pools if p.coverage < 1),
        output_effect_pct=round((worst - 1) * PCT, 1),
    )
