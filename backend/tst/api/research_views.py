"""The Research screen and era timeline for the API (M11, formulas.md 21.7).

Display only: every number comes from the sim. A rival's lead is shown only as a range
(`estimates.lead_range`); the player's projects show output and progress estimated from the
skill ranges it sees; eras still to come show thresholds and no historical dates.
"""

from __future__ import annotations

from tst.api.schemas.research import (
    CategoryTechOut,
    DomainOut,
    DomainRivalsOut,
    EraOut,
    LicenseOut,
    ProjectOut,
    ResearchOut,
    RivalLeadOut,
    UnitChoiceOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.org.rules import org_view
from tst.sim.research import estimates, levels, licensing
from tst.sim.research.data import EraDef
from tst.sim.research.formulas import license_price_cents
from tst.sim.research.projects import lab
from tst.sim.state import GameState

PERCENT = 100  # tunable-exempt: fractions shown as percent
PERCENT_BP = 100  # tunable-exempt: basis points in a percent


def _r1(x: float) -> float:
    return round(x, 1)


def domains_out(state: GameState, data: LoadedData) -> list[DomainOut]:
    g, b = data.game_data, data.balance
    cid = state.player.id
    out = []
    for d in levels.domain_keys(g):
        era = estimates.next_era(state, g, d)
        base = levels.baseline(state, g, b, d)
        lead = state.research_lead(cid, d)
        out.append(
            DomainOut(
                key=d,
                label=levels.domain_def(g, d).label,
                baseline=_r1(base),
                lead=_r1(lead),
                level=_r1(base + lead),
                feeds=[g.category(c).label for c in levels.feeds(g, d)],
                next_era=era.label if era else None,
                next_threshold=_r1(levels.threshold(g, b, era)) if era else None,
            )
        )
    return out


def categories_out(state: GameState, data: LoadedData) -> list[CategoryTechOut]:
    g, b = data.game_data, data.balance
    cid = state.player.id
    out = []
    for cat in g.categories:
        f = levels.tech_factor(state, cid, cat.key, b, g)
        out.append(
            CategoryTechOut(
                category=cat.key,
                label=cat.label,
                lead=_r1(f.lead),
                cap_lift_pct=_r1((f.cap_mult - 1) * PERCENT),
                feature_lift_pct=_r1((f.feature_mult - 1) * PERCENT),
                first_mover=f.cap_points > 0,
            )
        )
    return out


def _researchers(state: GameState, data: LoadedData, unit_id: int) -> int:
    view = org_view(state, state.player.id)
    count = 0
    for pid in view.members.get(unit_id, ()):
        e = state.employment_of(pid)
        if state.person(pid).is_founder or (
            e is not None and data.game_data.role(e.role).product_function == "builder"
        ):
            count += 1
    return count


def projects_out(state: GameState, data: LoadedData) -> list[ProjectOut]:
    g, b = data.game_data, data.balance
    cid = state.player.id
    view = org_view(state, cid)
    out = []
    for p in state.active_projects(cid):
        if p.unit_id is None:
            continue
        unit = state.unit(p.unit_id)
        work = lab(state, view, p, b, g)
        shown = estimates.shown_lab(state, cid, work, p.domain, b, g)
        look = estimates.outlook(state, cid, p.domain, shown, b, g)
        era = estimates.next_era(state, g, p.domain)
        early = None
        if era is not None and look.months is not None:
            early = levels.historical_turn(era) - (state.turn + look.months)
        event = None
        if p.last_event is not None and p.last_event_turn is not None:
            word = "Breakthrough" if p.last_event == "breakthrough" else "Dead end"
            event = f"{word}, {format_turn(p.last_event_turn)}"
        out.append(
            ProjectOut(
                project_id=p.id,
                unit_id=p.unit_id,
                unit_name=unit.name if unit else f"Unit {p.unit_id}",
                domain=p.domain,
                domain_label=levels.domain_def(g, p.domain).label,
                researchers=len(work.researchers),
                budget_cents=p.budget_cents,
                needed_cents=work.needed_cents,
                funded_pct=_r1(work.funded * PERCENT),
                gain_per_month=round(look.gain, 2),
                last_month_gain=round(p.recent[-1], 2) if p.recent else None,
                next_era=era.label if era else None,
                months_to_era=look.months,
                months_before_history=early if early is not None and early > 0 else None,
                last_event=event,
                started=format_turn(p.start_turn),
            )
        )
    return out


def units_out(state: GameState, data: LoadedData) -> list[UnitChoiceOut]:
    return [
        UnitChoiceOut(unit_id=u.id, name=u.name, researchers=_researchers(state, data, u.id))
        for u in state.active_units(state.player.id)
        if u.product_id is None and state.unit_project(u.id) is None
    ]


def rivals_out(state: GameState, data: LoadedData) -> list[DomainRivalsOut]:
    """Every rival's lead in each domain as a range, with what licensing would allow; the
    limits are the actions' own public ceilings (the range's low end in, high end out), so
    the player never learns the exact gap (21.7, M12r)."""
    g, b = data.game_data, data.balance
    me = state.player.id
    out = []
    for d in levels.domain_keys(g):
        rows = []
        for c in state.rivals():
            low, high = estimates.lead_range(state, me, c.id, d, b, g)
            why = licensing.refusal(state, g, b, me, c.id, d)
            safe_in = licensing.public_license_in_limit(state, b, g, me, c.id, d)
            safe_out = licensing.public_license_out_limit(state, b, g, me, c.id, d)
            rows.append(
                RivalLeadOut(
                    company_id=c.id,
                    name=c.name,
                    is_startup=c.is_startup,
                    founded=format_turn(c.founded_turn) if c.is_startup else None,
                    low=low,
                    high=high,
                    licensed=any(x.involves(me, c.id) for x in state.licenses),
                    can_license_in=why is None and safe_in > 0,
                    why_not=why,  # None only when the public ceiling is above 0 (M12r)
                    max_points=safe_in if why is None else 0,
                    can_license_out=safe_out > 0,
                    max_out_points=safe_out,
                )
            )
        rows.sort(key=lambda r: (-r.high, r.name))
        out.append(
            DomainRivalsOut(domain=d, domain_label=levels.domain_def(g, d).label, rivals=rows)
        )
    return out


def licenses_out(state: GameState, data: LoadedData) -> list[LicenseOut]:
    g = data.game_data
    me = state.player.id
    out = []
    for x in state.licenses:
        if me not in (x.licensor_id, x.licensee_id):
            continue
        inbound = x.licensee_id == me
        other = x.licensor_id if inbound else x.licensee_id
        left = 0
        if x.royalty_end_turn is not None:
            left = max(0, x.royalty_end_turn - state.turn + 1)
        out.append(
            LicenseOut(
                license_id=x.id,
                direction="in" if inbound else "out",
                company=state.company(other).name,
                domain_label=levels.domain_def(g, x.domain).label,
                points=_r1(x.points),
                price_cents=x.price_cents,
                royalty_pct=x.royalty_bp / PERCENT_BP,
                royalty_months_left=left,
                signed=format_turn(x.turn),
            )
        )
    return out


def _accelerates(data: LoadedData, era: EraDef) -> str:
    g = data.game_data
    parts = []
    for b in era.boosts:
        cat = g.category(b.category).label
        where = (
            f"{cat} ({', '.join(g.segment(s).label for s in b.segments)})" if b.segments else cat
        )
        if b.growth:
            parts.append(
                f"{where}: growth +{round(b.growth * PERCENT):d} points for {b.months} months"
            )
        if b.adoption != 1:
            parts.append(f"{where}: adoption x{b.adoption:g} for {b.months} months")
    return "; ".join(parts)


def eras_out(state: GameState, data: LoadedData) -> list[EraOut]:
    """Arrived eras (when, on schedule or early, and who caused them), the next one per
    domain, and later ones with thresholds; no historical date of an era to come (21.4)."""
    g, b = data.game_data, data.balance
    me = state.player.id
    rnd = b.rnd
    reward = (
        f"For {rnd.first_mover_months} months: +{rnd.first_mover_cap:g} quality cap and "
        f"+{rnd.first_mover_brand:g} brand target in its markets, and no decay of the lead"
    )
    nexts = {d: estimates.next_era(state, g, d) for d in levels.domain_keys(g)}
    out = []
    for era in g.eras.eras:
        a = state.era_arrival(era.key)
        caused = None
        if a is not None and a.company_id is not None:
            caused = "You" if a.company_id == me else state.company(a.company_id).name
        status = "arrived" if a else ("next" if nexts.get(era.domain) == era else "later")
        out.append(
            EraOut(
                key=era.key,
                label=era.label,
                domain_label=levels.domain_def(g, era.domain).label,
                status=status,
                arrived=format_turn(a.turn) if a else None,
                on_schedule=(a.company_id is None) if a else None,
                months_early=a.months_early if a else None,
                caused_by=caused,
                threshold=_r1(levels.threshold(g, b, era)),
                your_level=_r1(levels.level(state, g, b, me, era.domain)),
                accelerates=_accelerates(data, era),
                first_mover_reward=reward,
                expected=_window(era) if a is None else None,
            )
        )
    return out


def _window(era: EraDef) -> str | None:
    """'expected 2026-2028' for a future era (26.4): the public window, never t_sched."""
    if era.window is None:
        return None
    (y1, _), (y2, _) = era.window
    return f"expected {y1}\u2013{y2}"


def research_out(state: GameState, data: LoadedData) -> ResearchOut:
    b = data.balance
    lic = b.rnd.license
    return ResearchOut(
        domains=domains_out(state, data),
        categories=categories_out(state, data),
        projects=projects_out(state, data),
        units=units_out(state, data),
        rivals=rivals_out(state, data),
        licenses=licenses_out(state, data),
        eras=eras_out(state, data),
        decay_pct=b.rnd.decay * PERCENT,
        price_per_point_cents=license_price_cents(
            1, licensing.arr_cents(state, state.player.id), b
        ),
        margin=lic.margin,
        royalty_pct=lic.royalty_bp / PERCENT_BP,
        royalty_months=lic.royalty_months,
        start_energy=b.rnd.start_energy,
        stop_energy=b.rnd.stop_energy,
        license_energy=lic.energy,
    )
