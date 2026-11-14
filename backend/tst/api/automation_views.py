"""Automation views (M27a, formulas.md 40.8, 40.11). Fit bands come from displayed ranges
(18.8); nothing here reads a true skill, a true score, a quality probability or a draw."""

from __future__ import annotations

from tst.api.schemas.automation import (
    AreaOut,
    AssignmentOut,
    AutomatePlanOut,
    AutomationOut,
    CandidateOut,
    CompanyChoiceOut,
    DigestAreaOut,
    DigestOut,
    GuardrailOut,
    HeadcountTargetOut,
    KpiOut,
    RecordOut,
    RoleChoiceOut,
    UnitChoiceOut,
)
from tst.loader import LoadedData
from tst.sim.automation import digest, owners
from tst.sim.automation.plan import automate_everything, energy_left
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance
from tst.sim.errors import InvalidActionError
from tst.sim.money import Cents
from tst.sim.state import GameState

# The screen each area's header sits on (40.8): "Run by <name> (<role>) · Take back".
SCREEN: dict[str, str] = {
    "hiring": "recruitment",
    "engineering": "org",
    "products": "products",
    "pricing": "products/markets",
    "marketing": "products",
    "support": "org/offices",
    "treasury": "finance",
    "research": "products/research",
    "regions": "competitors/world",
    "cloud": "products/infrastructure",
    "press": "people",
    "events": "inbox",
    # M27b
    "production": "products/hardware",
    "supply": "products/markets",
    "exploration": "products/exploration",
    "mines": "products/mines",
    "fabs": "products/fabs",
    "government": "competitors/world",
    "corp_dev": "competitors",
}
BUDGETED = frozenset({"exploration", "government", "corp_dev"})  # M27b: spend within a budget
RECENT = 5  # tunable-exempt: the record's latest lines


def _candidate(
    state: GameState,
    area: str,
    person_id: int,
    kind: str,
    data: LoadedData,
    company: int | None = None,
) -> CandidateOut:
    b = data.balance
    company = state.player.id if company is None else company
    person = state.person(person_id)
    e = state.employment_of(person_id)
    score = owners.shown_area_score(state, company, area, person_id, b)
    return CandidateOut(
        person_id=person_id,
        name=f"{person.first_name} {person.last_name}",
        role=data.game_data.role(e.role).label if e is not None and e.role != "founder" else "",
        kind=kind,
        fit=owners.fit_band(score, b),
        energy_left=energy_left(state, person_id, b, data.game_data),
    )


def automation_out(
    state: GameState,
    cash: Cents,
    data: LoadedData,
    stop_for_approvals: bool,
    company_id: int | None = None,
) -> AutomationOut:
    """The Automation screen for the player's company or (M27b) one of its subsidiaries."""
    from tst.sim.automation import scope

    b = data.balance
    company = state.player.id if company_id is None else company_id
    if not scope.in_scope(state, company):
        raise InvalidActionError(f"company {company} is not in your group")
    player = state.player.id
    month = [
        d for d in state.area_decisions if d.company_id == company and d.turn == state.turn - 1
    ]
    pending = {p.id for p in state.pending_proposals(player)} | {
        p.id for p in state.pending_pitches(player)
    }
    areas = []
    for key in owners.area_keys(b):
        a = owners.area_def(b, key)
        if not owners.automatable_in(state, company, key, b):
            continue
        o = state.area_owner(company, key)
        people = owners.eligible_people(state, company, key, b)
        mine = [d for d in month if d.area == key]
        owner = None
        if o is not None:
            kind = owners.owner_kind(state, company, key, o.person_id, b) or "lead"
            owner = _candidate(state, key, o.person_id, kind, data, company)
        reason = (
            None if o is not None else owners.cant_automate(state, company, key, b, data.game_data)
        )
        areas.append(
            AreaOut(
                area=key,
                label=a.label,
                seat=a.seat if company == player else None,
                status="automated" if o is not None else ("cant" if reason else "manage"),
                reason=reason,
                owner=owner,
                candidates=[
                    _candidate(state, key, pid, kind, data, company) for pid, kind in people
                ],
                limit_cents=o.limit_cents if o else None,
                priority=o.priority if o else None,
                answer_events=o.answer_events if o else True,
                allow_bold=o.allow_bold if o else False,
                events=bool(a.events),
                energy=a.energy,
                decisions=sum(1 for d in mine if d.kind in digest.DID),
                mistakes=sum(1 for d in mine if d.kind == "mistake"),
                proposals_waiting=sum(
                    1 for d in mine if d.kind == "proposal" and d.ref_id in pending
                ),
                no_time=any(d.kind == "no_time" for d in mine),
                over_budget=any(d.kind == "over_budget" for d in mine),
                screen=SCREEN.get(key, "automation"),
                budget_cents=o.budget_cents if o else 0,
                budgeted=key in BUDGETED,
                guardrails=[
                    GuardrailOut(
                        key=g,
                        value=o.guardrail(g, float(v)) if o else float(v),
                        default=float(v),
                    )
                    for g, v in a.guardrails.items()
                ],
            )
        )
    return AutomationOut(
        company_id=company,
        company_name=state.company(company).name,
        areas=areas,
        default_limit_cents=owners.default_limit(cash, b),
        stop_for_approvals=stop_for_approvals,
        companies=[
            CompanyChoiceOut(company_id=c, name=state.company(c).name, subsidiary=c != player)
            for c in scope.companies(state)
        ],
        subsidiary=company != player,
        headcount_targets=_targets(state, company, data),
        units=[UnitChoiceOut(unit_id=u.id, name=u.name) for u in state.active_units(company)],
        roles=[
            RoleChoiceOut(key=r.key, label=r.label)
            for r in data.game_data.roles
            if r.key != "founder" and r.founder_fit
        ],
    )


def _targets(state: GameState, company: int, data: LoadedData) -> list[HeadcountTargetOut]:
    from tst.sim.automation.rules import target_gaps

    gaps = {(u, r): g for u, r, g in target_gaps(state, company)}
    names = {u.id: u.name for u in state.units}
    out = []
    for t in state.headcount_targets:
        if t.company_id != company:
            continue
        staff = sum(
            1
            for e in state.staff(company)
            if e.unit_id == t.unit_id and e.role == t.role and e.status == "active"
        )
        out.append(
            HeadcountTargetOut(
                unit_id=t.unit_id,
                unit_name=names.get(t.unit_id, f"Unit {t.unit_id}"),
                role=t.role,
                role_label=data.game_data.role(t.role).label,
                target=t.target,
                staff=staff,
                gap=gaps.get((t.unit_id, t.role), 0),
            )
        )
    return out


def plan_out(
    state: GameState, cash: Cents, data: LoadedData, company_id: int | None = None
) -> AutomatePlanOut:
    b = data.balance
    company = state.player.id if company_id is None else company_id
    plan = automate_everything(state, cash, b, data.game_data, company_id)
    chosen = {a.area for a in plan}
    out = []
    for a in plan:
        person = state.person(a.person_id)
        score = owners.shown_area_score(state, company, a.area, a.person_id, b)
        out.append(
            AssignmentOut(
                area=a.area,
                label=owners.area_def(b, a.area).label,
                person_id=a.person_id,
                name=f"{person.first_name} {person.last_name}",
                fit=owners.fit_band(score, b),
                limit_cents=a.limit_cents,
            )
        )
    left = [
        owners.area_def(b, k).label
        for k in owners.area_keys(b)
        if k not in chosen
        and state.area_owner(company, k) is None
        and owners.automatable_in(state, company, k, b)
    ]
    return AutomatePlanOut(assignments=out, left_out=left)


def digest_out(
    state: GameState, turn: int, data: LoadedData, item_id: int | None, items: list[int]
) -> DigestOut | None:
    d = digest.build(state, turn, data.balance, data.game_data)
    if d is None:
        return None
    return DigestOut(
        turn=turn,
        month=format_turn(turn),
        opening=d.opening,
        areas=[
            DigestAreaOut(
                area=a.area,
                label=a.label,
                person_id=a.person_id,
                owner=a.owner,
                did=a.did,
                lines=list(a.lines),
                committed_cents=a.committed_cents,
                limit_cents=a.limit_cents,
                mistakes=list(a.mistakes),
                proposals=list(a.proposals),
                kpis=[
                    KpiOut(
                        key=k.key,
                        label=k.label,
                        now=k.now,
                        last=k.last,
                        target=k.target,
                        money=k.money,
                        text=digest.kpi_text(k),
                    )
                    for k in a.kpis
                ],
                notes=list(a.notes),
            )
            for a in d.areas
        ],
        attention=list(d.attention),
        quarter_reports=d.quarter_reports,
        inbox_item_id=item_id,
        items=items,
    )


def record_out(state: GameState, person_id: int, data: LoadedData) -> RecordOut:
    """40.3's visible record: decisions this year, proposals and their outcomes, pitches hit
    or missed. Never the probability or the draw."""
    from tst.sim.org.pitches import record

    e = state.employment_of(person_id)
    company = e.company_id if e is not None else state.player.id
    b = data.balance
    person = state.person(person_id)
    year = [
        d
        for d in state.area_decisions
        if d.company_id == company and d.person_id == person_id and d.turn > state.turn - 13
    ]
    props = [p for p in state.proposals if p.kind == "auto" and p.person_id == person_id]
    hits, misses, _ = record(state, person_id)
    return RecordOut(
        person_id=person_id,
        name=f"{person.first_name} {person.last_name}",
        areas=[
            owners.area_def(b, o.area).label
            for o in state.owners_of(company)
            if o.person_id == person_id
        ],
        decisions_year=sum(1 for d in year if d.kind in digest.DID),
        mistakes_year=sum(1 for d in year if d.kind == "mistake"),
        proposals=len(props),
        proposals_approved=sum(1 for p in props if p.status == "approved"),
        proposals_declined=sum(1 for p in props if p.status == "declined"),
        proposals_expired=sum(1 for p in props if p.status == "expired"),
        pitches_hit=hits,
        pitches_missed=misses,
        recent=[
            f"{format_turn(d.turn)}: {d.text}"
            for d in sorted(year, key=lambda d: (-d.turn, -d.seq))
            if d.kind in digest.DID or d.kind == "proposal"
        ][:RECENT],
        company_id=company,
        kpis=_record_kpis(state, company, person_id, b),
    )


def _record_kpis(state: GameState, company: int, person_id: int, b: Balance) -> list[str]:
    """M27b (40.3's record): each area they run, its KPIs at the latest month they ran it."""
    from tst.sim.automation.kpis import LABELS, MONEY
    from tst.sim.money import format_money

    out = []
    for o in state.owners_of(company):
        if o.person_id != person_id:
            continue
        rows = [d for d in state.area_decisions if d.company_id == company and d.area == o.area]
        if not rows:
            continue
        last = max(d.turn for d in rows)
        label = owners.area_def(b, o.area).label
        for d in rows:
            if d.turn == last and d.kind == "kpi":
                v = d.commitment_cents
                shown = format_money(v) if d.text in MONEY else f"{v:,}"
                out.append(f"{label}: {LABELS.get(d.text, d.text)} {shown}")
    return out
