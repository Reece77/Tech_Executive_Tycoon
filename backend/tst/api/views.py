"""Build API responses from the live state, as seen by the viewing company (ADR-0007).

Ranges come from the company's knowledge records; true values never leave this module.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.api import breakdowns
from tst.api.schemas.people import (
    ActiveEffectOut,
    AttributeOut,
    CandidacyOut,
    EmploymentOut,
    EnergyAdjustmentOut,
    EnergyOut,
    EventLinkOut,
    InboxItemOut,
    KnowledgeOut,
    LearnedOut,
    MoralePointOut,
    OptionsOut,
    PendingOfferOut,
    PersonOrgOut,
    PersonProfileOut,
    PersonSummaryOut,
    PitchRecordOut,
    RangeChangeOut,
    RangeOut,
    SearchOut,
    TagOut,
)
from tst.db.inbox import InboxMessage
from tst.db.models import DecisionLogRow, PersonMoraleLogRow
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.errors import UnknownPersonError
from tst.sim.events.data import MODIFIER_STATS
from tst.sim.events.describe import running_text, signed
from tst.sim.events.models import Modifier
from tst.sim.events.modifiers import founder_factor, running
from tst.sim.finance.captable import fd_shares
from tst.sim.finance.options import at_cliff, next_vesting
from tst.sim.geo.cities import home_city, person_work_city
from tst.sim.geo.models import ANYWHERE
from tst.sim.geo.offices import employee_office_cents
from tst.sim.hiring.formulas import severance_cents
from tst.sim.hiring.models import Search
from tst.sim.hiring.phases import employment_monthly_cost_cents
from tst.sim.hiring.recruit import leadership_fit
from tst.sim.org.morale import market_mid_for
from tst.sim.org.rules import is_remote, org_view
from tst.sim.people.formulas import potential_phrase
from tst.sim.people.models import PA_KEY, Person, RevealState
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState, life_of


def options_out(state: GameState, employment_id: int, data: LoadedData) -> OptionsOut | None:
    """Granted, vested and unvested options and the next vesting (M4b)."""
    grant = state.grant_for(employment_id)
    if grant is None:
        return None
    fb = data.balance.finance
    fd = fd_shares(state, grant.company_id)
    nxt = next_vesting(grant, state.turn, fb)
    return OptionsOut(
        granted=grant.granted,
        vested=grant.vested,
        unvested=grant.unvested,
        fraction=grant.outstanding / fd if fd else 0.0,
        next_vest_label=format_turn(nxt[0]) if nxt else None,
        next_vest_shares=nxt[1] if nxt else 0,
        next_vest_is_cliff=nxt is not None and at_cliff(grant, nxt[0], fb),
    )


HISTORY_TURNS = 12
PERSONALITY_GROUP = "personality"
CHECK_KINDS = ("interview", "reference_check")
INTERVIEW_REQUIRED = "interview_required"  # CandidacyOut.offer_blocked_reason (ADR-0016)

# Spec section 3. Display names only; the stage number drives the rules.
STAGE_LABELS = {
    0: "Solo founder",
    1: "Garage startup",
    2: "Venture-backed",
    3: "Scale-up",
    4: "Public company",
    5: "Conglomerate",
}

type Checks = Mapping[int, Sequence[tuple[str, int]]]  # person id -> (kind, turn), in order


def checks_by_person(session: Session, company_id: int) -> dict[int, list[tuple[str, int]]]:
    """Interviews and reference checks the company has run, from decision_log."""
    rows = session.scalars(
        select(DecisionLogRow)
        .where(DecisionLogRow.company_id == company_id, DecisionLogRow.kind.in_(CHECK_KINDS))
        .order_by(DecisionLogRow.turn, DecisionLogRow.seq)
    ).all()
    out: dict[int, list[tuple[str, int]]] = {}
    for row in rows:
        out.setdefault(int(row.payload["candidate_id"]), []).append((row.kind, row.turn))
    return out


def energy(state: GameState, data: LoadedData) -> EnergyOut:
    founder = state.founder_of(state.player.id)
    left = state.person_state(founder.id).energy if founder else None
    cap = data.balance.founder.energy_per_month
    adjustments: list[EnergyAdjustmentOut] = []
    if founder is not None:  # M10b (23.2): last month's answers and running modifiers
        boost = founder_factor(state, state.player.id, founder.id)
        cap = cap if boost == 1 else max(0, round(cap * boost))
        for event in state.events:
            if event.resolved_turn != state.turn - 1 or event.chosen is None:
                continue
            choice = event.choice(event.chosen)
            for e in choice.effects if choice else ():
                if e.type == "energy_delta" and e.target == f"founder:{founder.id}" and e.value:
                    adjustments.append(
                        EnergyAdjustmentOut(
                            label=f"{signed(e.value)} from {event.title or 'an event'}",
                            value=e.value,
                            percent=False,
                        )
                    )
        for m in running(state, state.player.id):
            if m.stat == "founder_energy":
                adjustments.append(
                    EnergyAdjustmentOut(
                        label=f"{signed(m.value_pct)}% a month from {_source(state, m)} "
                        f"({m.end_turn - state.turn} months left)",
                        value=m.value_pct,
                        percent=True,
                    )
                )
        life = life_of(state, founder.id)  # M24 (32.1): burnout's cut, a month off
        if life is not None and life.burnout:
            cut = data.balance.stress.burnout_cut
            cap = math.floor(cap * (1 - cut))
            adjustments.append(
                EnergyAdjustmentOut(
                    label=f"-{cut:.0%} while burnt out", value=-cut * 100, percent=True
                )
            )
        if life is not None and life.rest_turn == state.turn:
            adjustments.append(EnergyAdjustmentOut(label="a month off", value=0, percent=False))
    return EnergyOut(energy=cap if left is None else left, max=cap, adjustments=adjustments)


def _source(state: GameState, m: Modifier) -> str:
    event = next((e for e in state.events if e.id == m.event_id), None)
    if event is None and m.event_id is None and m.stat == "brand_target":
        return "a public promise"  # M14b (29.2): kept and broken promises have no event
    return event.title if event is not None and event.title else "an event"


def active_effects(
    state: GameState, keep: Callable[[Modifier], bool] = lambda _m: True
) -> list[ActiveEffectOut]:
    """Running event modifiers of the player company, newest first (23.2, M10b)."""
    return [
        ActiveEffectOut(
            modifier_id=m.id,
            event_id=m.event_id,
            source=_source(state, m),
            stat=m.stat,
            text=running_text(state, m),
            value_pct=m.value_pct,
            months_left=m.end_turn - state.turn,
        )
        for m in sorted(running(state, state.player.id), key=lambda m: -m.id)
        if keep(m)
    ]


PRODUCT_STATS = frozenset(
    s for s, words in MODIFIER_STATS.items() if "product" in words
)  # M10b: what a product's panel lists


def product_effects(state: GameState, product_id: int) -> list[ActiveEffectOut]:
    return active_effects(
        state,
        lambda m: (
            m.target == f"product:{product_id}"
            or (m.target.startswith("company:") and m.stat in PRODUCT_STATS)
        ),
    )


def person_effects(state: GameState, person_id: int) -> list[ActiveEffectOut]:
    employment = state.employment_of(person_id)
    unit = f"unit:{employment.unit_id}" if employment and employment.unit_id else None
    return active_effects(
        state,
        lambda m: (
            m.target in (f"person:{person_id}", f"founder:{person_id}", unit)
            or (m.target.startswith("company:") and m.stat == "morale_target")
        ),
    )


def inbox_item(m: InboxMessage) -> InboxItemOut:
    return InboxItemOut(
        item_id=m.id,
        turn=m.turn,
        date_label=format_turn(m.turn),
        kind=m.template,
        title=m.title,
        body=m.body,
        link_kind=m.link_kind,
        link_id=m.link_id,
        read=m.read,
        archived=m.archived,
        bookmarked=m.bookmarked,
        in_digest=m.in_digest,
        event_links=[EventLinkOut(event_id=e, label=label) for e, label in m.event_links],
    )


def _knowledge(state: GameState, company_id: int, person: Person) -> RevealState:
    reveal = state.reveal(company_id, person.id)
    if reveal is None:
        raise UnknownPersonError(f"no person {person.id}")
    return reveal


def _skills(person: Person, reveal: RevealState, data: LoadedData) -> list[AttributeOut]:
    out = []
    for skill in data.game_data.skills:
        lo, hi = revealed_range(person, reveal, skill.key)
        out.append(
            AttributeOut(
                key=skill.key,
                label=skill.label,
                short_label=skill.short_label,
                group=skill.group,
                range=RangeOut(min=lo, max=hi),
            )
        )
    return out


def _personality(person: Person, reveal: RevealState, data: LoadedData) -> list[AttributeOut]:
    out = []
    for trait in data.game_data.personality:
        lo, hi = revealed_range(person, reveal, trait.key)
        out.append(
            AttributeOut(
                key=trait.key,
                label=trait.label,
                short_label=trait.label,
                group=PERSONALITY_GROUP,
                range=RangeOut(min=lo, max=hi),
            )
        )
    return out


def _tags(reveal: RevealState, data: LoadedData) -> list[TagOut]:
    tags = {t.key: t for t in data.game_data.tags}
    return [
        TagOut(
            key=key,
            label=tags[key].label,
            text=tags[key].reveal_text,
            noticed_turn=turn,
            noticed_date_label=format_turn(turn),
        )
        for key, turn in reveal.revealed_tags
    ]


def person_org(state: GameState, company_id: int, person_id: int) -> PersonOrgOut:
    """Unit, manager and led unit of a staff member (M2b)."""
    view = org_view(state, company_id)
    unit_id = view.unit_of.get(person_id)
    unit = view.units.get(unit_id) if unit_id is not None else None
    parent = view.units.get(unit.parent_id) if unit is not None and unit.parent_id else None
    manager = view.manager_of.get(person_id)
    leads = next((u.id for u in view.units.values() if u.leader_id == person_id), None)
    return PersonOrgOut(
        unit_id=unit_id,
        unit_name=state.company(company_id).name if unit is None else unit.name,
        parent_unit_name=None if parent is None else parent.name,
        manager_id=manager,
        manager_name=None if manager is None else person_name(state.person(manager)),
        leads_unit_id=leads,
    )


def person_name(person: Person) -> str:
    return f"{person.first_name} {person.last_name}"


def role_label(role: str | None, data: LoadedData) -> str | None:
    if role is None:
        return None
    try:
        return data.game_data.role(role).label
    except KeyError:
        return role.replace("_", " ").capitalize()  # "founder"


def _knowledge_out(
    reveal: RevealState, checks: Sequence[tuple[str, int]], channel: str | None
) -> KnowledgeOut:
    interviews = [turn for kind, turn in checks if kind == "interview"]
    return KnowledgeOut(
        channel=channel,
        interviews=len(interviews),
        reference_checks=sum(1 for kind, _ in checks if kind == "reference_check"),
        first_interview_date_label=format_turn(interviews[0]) if interviews else None,
        profile_known=reveal.profile_revealed_turn is not None,
    )


def person_summary(
    state: GameState,
    company_id: int,
    person_id: int,
    data: LoadedData,
    checks: Checks | None = None,
) -> PersonSummaryOut:
    try:
        person = state.person(person_id)
    except KeyError as exc:
        raise UnknownPersonError(f"no person {person_id}") from exc
    reveal = _knowledge(state, company_id, person)
    employment = state.employment_of(person.id)
    if employment is not None and employment.company_id != company_id:
        employment = None
    candidate = state.candidate(person.id)
    if candidate is not None and (candidate.company_id != company_id or candidate.status != "open"):
        candidate = None
    if employment is None and candidate is None:
        raise UnknownPersonError(f"no person {person_id}")
    pa_lo, pa_hi = revealed_range(person, reveal, PA_KEY)
    offer = state.pending_offer_for(person.id)
    role = employment.role if employment else person.role
    market_rate = None
    if employment is not None and not person.is_founder:
        market_rate = market_mid_for(state, employment, data.balance, data.game_data)
    city: str | None = None
    relocate: bool | None = None
    if data.game_data.cities:
        if employment is not None:
            city = person_work_city(state, person, data.balance, data.game_data)
        else:
            city = home_city(person, data.game_data)
            relocate = candidate is not None and candidate.relocate_to is not None
    fit_low, fit_high = leadership_fit(person, reveal, data.balance)  # M14b (29.5)
    return PersonSummaryOut(
        leadership_fit_low=fit_low,
        leadership_fit_high=fit_high,
        person_id=person.id,
        name=f"{person.first_name} {person.last_name}",
        age=person.age(state.turn),
        region=person.region,
        city=city,
        city_label=_city_label(city, data),
        would_relocate=relocate,
        role=role,
        role_label=role_label(role, data),
        level=employment.level if employment else person.level,
        is_founder=person.is_founder,
        morale=state.person_state(person.id).morale if employment else None,
        potential_phrase=potential_phrase(pa_lo, pa_hi, data.balance.reveal.pa_phrase_bounds),
        skills=_skills(person, reveal, data),
        personality=_personality(person, reveal, data),
        employment=None
        if employment is None
        else EmploymentOut(
            employment_id=employment.id,
            role=employment.role,
            role_label=role_label(employment.role, data) or employment.role,
            level=employment.level,
            salary_cents=employment.salary_cents,
            equity_bp=employment.equity_bp,
            start_turn=employment.start_turn,
            status=employment.status,
            end_turn=employment.end_turn,
            severance_cents=0
            if person.is_founder
            else severance_cents(employment.salary_cents, data.balance.payroll),
            start_date_label=format_turn(employment.start_turn),
            end_date_label=None
            if employment.end_turn is None
            else format_turn(employment.end_turn),
            tenure_months=state.turn - employment.start_turn,
            market_rate_cents=market_rate,
            salary_breakdown=breakdowns.salary(employment.salary_cents, market_rate),
            monthly_cost_cents=employment_monthly_cost_cents(
                employment,
                data.balance,
                remote=is_remote(state, employment),
                office_cents=employee_office_cents(state, employment, data.balance, data.game_data),
            ),
            options=options_out(state, employment.id, data),
        ),
        candidacy=None
        if candidate is None
        else CandidacyOut(
            search_id=candidate.search_id,
            channel=candidate.channel,
            expires_turn=candidate.expires_turn,
            expires_date_label=format_turn(candidate.expires_turn),
            salary_expectation_cents=person.salary_expectation_cents or 0,
            offer_blocked_reason=INTERVIEW_REQUIRED if candidate.interviewed_turn is None else None,
            pending_offer=None
            if offer is None
            else PendingOfferOut(
                offer_id=offer.id,
                salary_cents=offer.salary_cents,
                equity_bp=offer.equity_bp,
                made_turn=offer.made_turn,
                answer_date_label=format_turn(offer.made_turn + 1),
            ),
        ),
        noticed_tags=_tags(reveal, data),
        knowledge=_knowledge_out(
            reveal, (checks or {}).get(person.id, ()), candidate.channel if candidate else None
        ),
        interests=list(person.interests) if reveal.profile_revealed_turn is not None else None,
        org=None if employment is None else person_org(state, company_id, person.id),
        energy=state.person_state(person.id).energy if employment is not None else None,
    )


def pitch_record(state: GameState, person_id: int) -> PitchRecordOut:
    """An executive's pitch record (27.1): their pitches by answer and outcome."""
    mine = [p for p in state.pitches if p.person_id == person_id]
    approved = [p for p in mine if p.approved]
    return PitchRecordOut(
        pitches=len(mine),
        approved=len(approved),
        hits=sum(1 for p in mine if p.outcome == "hit"),
        misses=sum(1 for p in mine if p.outcome == "miss"),
        too_early=sum(1 for p in mine if p.outcome == "too_early"),
        tracking=sum(1 for p in approved if p.outcome is None),
    )


def person_profile(
    session: Session, state: GameState, company_id: int, person_id: int, data: LoadedData
) -> PersonProfileOut:
    summary = person_summary(
        state, company_id, person_id, data, checks_by_person(session, company_id)
    )
    person = state.person(person_id)
    reveal = _knowledge(state, company_id, person)
    known = reveal.profile_revealed_turn is not None
    role_key = summary.employment.role if summary.employment else person.role
    role = None
    if role_key is not None and role_key in {r.key for r in data.game_data.roles}:
        role = data.game_data.role(role_key)
    rows = session.scalars(
        select(PersonMoraleLogRow)
        .where(PersonMoraleLogRow.person_id == person_id)
        .order_by(PersonMoraleLogRow.turn.desc())
        .limit(HISTORY_TURNS)
    ).all()
    return PersonProfileOut(
        **summary.model_dump(),
        active_effects=person_effects(state, person_id),
        work_style=person.work_style if known else None,
        work_style_matches_role=None
        if not known or role is None
        else person.work_style == role.work_style,
        morale_history=[
            MoralePointOut(turn=r.turn, date_label=format_turn(r.turn), morale=r.morale)
            for r in reversed(rows)
        ],
        pitch_record=(
            pitch_record(state, person_id)
            if any(p.person_id == person_id for p in state.pitches)
            else None
        ),
    )


def learned(
    before: GameState,
    after: GameState,
    company_id: int,
    person_id: int,
    action: str,
    data: LoadedData,
) -> LearnedOut:
    """What an action taught the company about a person (M4c): every displayed range that
    narrowed, the potential phrase before and after, and interests, work style and tags that
    became known. Both sides are displayed values, so nothing hidden leaves (ADR-0007)."""
    person = after.person(person_id)
    old = _knowledge(before, company_id, before.person(person_id))
    new = _knowledge(after, company_id, person)
    bounds = data.balance.reveal.pa_phrase_bounds
    attrs = [(s.key, s.label, s.group) for s in data.game_data.skills] + [
        (t.key, t.label, PERSONALITY_GROUP) for t in data.game_data.personality
    ]
    ranges = []
    for key, label, group in attrs:
        lo0, hi0 = revealed_range(before.person(person_id), old, key)
        lo1, hi1 = revealed_range(person, new, key)
        if (lo0, hi0) != (lo1, hi1):
            ranges.append(
                RangeChangeOut(
                    key=key,
                    label=label,
                    group=group,
                    before=RangeOut(min=lo0, max=hi0),
                    after=RangeOut(min=lo1, max=hi1),
                )
            )
    revealed = old.profile_revealed_turn is None and new.profile_revealed_turn is not None
    known_tags = {t for t, _ in old.revealed_tags}
    return LearnedOut(
        person_id=person_id,
        name=person_name(person),
        action=action,
        ranges=ranges,
        potential_before=potential_phrase(
            *revealed_range(before.person(person_id), old, PA_KEY), bounds
        ),
        potential_after=potential_phrase(*revealed_range(person, new, PA_KEY), bounds),
        interests=list(person.interests) if revealed else None,
        work_style=person.work_style if revealed else None,
        tags=[t for t in _tags(new, data) if t.key not in known_tags],
    )


def search_out(state: GameState, search: Search, data: LoadedData) -> SearchOut:
    is_open = search.status == "open"
    return SearchOut(
        search_id=search.id,
        role=search.role,
        role_label=role_label(search.role, data) or search.role,
        channel=search.channel,
        opened_turn=search.opened_turn,
        opened_date_label=format_turn(search.opened_turn),
        status=search.status,
        closed_date_label=None if search.closed_turn is None else format_turn(search.closed_turn),
        # Batches are generated in phase 12 of the current turn, visible the next month.
        next_batch_date_label=format_turn(state.turn + 1) if is_open else None,
        monthly_cost_cents=data.balance.hiring.job_post_cost_cents
        if search.channel == "job_post" and search.status == "open"
        else 0,
        open_candidates=sum(
            1 for c in state.candidates if c.search_id == search.id and c.status == "open"
        ),
        rival_id=search.rival_id,
        rival_name=state.company(search.rival_id).name if search.rival_id is not None else None,
        level=search.level,
        city=search.city,
        city_label=_city_label(search.city, data),
    )


def _city_label(city: str | None, data: LoadedData) -> str | None:
    if city is None:
        return None
    if city == ANYWHERE:
        return "Anywhere"
    return data.game_data.city(city).label if data.game_data.has_city(city) else city


def _range_text(lo: int, hi: int) -> str:
    return str(lo) if lo == hi else f"{lo}\N{EN DASH}{hi}"


def offer_reasons(
    state: GameState,
    person: Person,
    company_id: int,
    ratio: float,
    equity_bp: int,
    data: LoadedData,
) -> list[str]:
    """Plain sentences behind the offer hint, built only from what the company knows.

    Mirrors the known-value score in formulas.md section 7: pay ratio, equity, revealed mission
    interests, the displayed risk-appetite range, and company stage.
    """
    hiring = data.balance.hiring
    reveal = _knowledge(state, company_id, person)
    company = state.company(company_id)
    reasons = []
    if ratio < hiring.lowball_ratio:
        reasons.append(
            f"The salary is below {round(hiring.lowball_ratio * 100)}% of their ask, "
            "so they will decline."
        )
    elif round(ratio, 2) == 1:
        reasons.append("Pay matches their ask.")
    elif ratio > 1:
        reasons.append("Pay is above their ask.")
    else:
        reasons.append("Pay is below their ask.")
    if equity_bp > 0:
        reasons.append(f"{equity_bp} bp of equity adds to the appeal.")
    if reveal.profile_revealed_turn is None:
        reasons.append("You do not know their interests yet; an interview reveals them.")
    else:
        labels = {i.key: i.label for i in data.game_data.interests}
        shared = [labels[k] for k in company.mission if k in person.interests]
        reasons.append(
            f"They share {' and '.join(shared)} with your mission."
            if shared
            else "They share none of your mission's interests."
        )
    lo, hi = revealed_range(person, reveal, "risk_appetite")
    reasons.append(f"Their risk appetite looks like {_range_text(lo, hi)} out of 20.")
    stage = min(company.stage, max(hiring.offer.stage_appeal))  # M13: stage 4 as 3
    appeal = hiring.offer.stage_appeal.get(stage, 0.0)
    if appeal < 0:
        reasons.append(f"A {STAGE_LABELS[company.stage].lower()} company is a harder sell.")
    elif appeal > 0:
        reasons.append("Your company's stage makes the offer more attractive.")
    return reasons
