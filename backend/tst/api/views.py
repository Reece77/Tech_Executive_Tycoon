"""Build API responses from the live state, as seen by the viewing company (ADR-0007).

Ranges come from the company's knowledge records; true values never leave this module.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.api.schemas.people import (
    AttributeOut,
    CandidacyOut,
    EmploymentOut,
    EnergyOut,
    InboxItemOut,
    MoralePointOut,
    PendingOfferOut,
    PersonProfileOut,
    PersonSummaryOut,
    RangeOut,
    SearchOut,
    TagOut,
)
from tst.db.inbox import InboxMessage
from tst.db.models import PersonMoraleLogRow
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.errors import UnknownPersonError
from tst.sim.hiring.formulas import severance_cents
from tst.sim.hiring.models import Search
from tst.sim.people.formulas import potential_phrase
from tst.sim.people.models import PA_KEY, Person, RevealState
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState

HISTORY_TURNS = 12
PERSONALITY_GROUP = "personality"


def energy(state: GameState, data: LoadedData) -> EnergyOut:
    founder = state.founder_of(state.player.id)
    left = state.person_state(founder.id).energy if founder else None
    cap = data.balance.founder.energy_per_month
    return EnergyOut(energy=cap if left is None else left, max=cap)


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
                key=skill.key, label=skill.label, group=skill.group, range=RangeOut(min=lo, max=hi)
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
                group=PERSONALITY_GROUP,
                range=RangeOut(min=lo, max=hi),
            )
        )
    return out


def _tags(reveal: RevealState, data: LoadedData) -> list[TagOut]:
    tags = {t.key: t for t in data.game_data.tags}
    return [
        TagOut(key=key, label=tags[key].label, text=tags[key].reveal_text, noticed_turn=turn)
        for key, turn in reveal.revealed_tags
    ]


def _role_label(role: str | None, data: LoadedData) -> str | None:
    if role is None:
        return None
    try:
        return data.game_data.role(role).label
    except KeyError:
        return role.replace("_", " ").capitalize()  # "founder"


def person_summary(
    state: GameState, company_id: int, person_id: int, data: LoadedData
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
    return PersonSummaryOut(
        person_id=person.id,
        name=f"{person.first_name} {person.last_name}",
        age=person.age(state.turn),
        region=person.region,
        role=role,
        role_label=_role_label(role, data),
        level=employment.level if employment else person.level,
        is_founder=person.is_founder,
        morale=state.person_state(person.id).morale if employment else None,
        potential_phrase=potential_phrase(pa_lo, pa_hi, data.balance.reveal.pa_phrase_bounds),
        skills=_skills(person, reveal, data),
        employment=None
        if employment is None
        else EmploymentOut(
            employment_id=employment.id,
            role=employment.role,
            role_label=_role_label(employment.role, data) or employment.role,
            level=employment.level,
            salary_cents=employment.salary_cents,
            equity_bp=employment.equity_bp,
            start_turn=employment.start_turn,
            status=employment.status,
            end_turn=employment.end_turn,
            severance_cents=0
            if person.is_founder
            else severance_cents(employment.salary_cents, data.balance.payroll),
        ),
        candidacy=None
        if candidate is None
        else CandidacyOut(
            search_id=candidate.search_id,
            channel=candidate.channel,
            expires_turn=candidate.expires_turn,
            salary_expectation_cents=person.salary_expectation_cents or 0,
            pending_offer=None
            if offer is None
            else PendingOfferOut(
                offer_id=offer.id,
                salary_cents=offer.salary_cents,
                equity_bp=offer.equity_bp,
                made_turn=offer.made_turn,
            ),
        ),
        noticed_tags=_tags(reveal, data),
    )


def person_profile(
    session: Session, state: GameState, company_id: int, person_id: int, data: LoadedData
) -> PersonProfileOut:
    summary = person_summary(state, company_id, person_id, data)
    person = state.person(person_id)
    reveal = _knowledge(state, company_id, person)
    known = reveal.profile_revealed_turn is not None
    rows = session.scalars(
        select(PersonMoraleLogRow)
        .where(PersonMoraleLogRow.person_id == person_id)
        .order_by(PersonMoraleLogRow.turn.desc())
        .limit(HISTORY_TURNS)
    ).all()
    return PersonProfileOut(
        **summary.model_dump(),
        personality=_personality(person, reveal, data),
        interests=list(person.interests) if known else None,
        work_style=person.work_style if known else None,
        morale_history=[
            MoralePointOut(turn=r.turn, date_label=format_turn(r.turn), morale=r.morale)
            for r in reversed(rows)
        ],
    )


def search_out(state: GameState, search: Search, data: LoadedData) -> SearchOut:
    return SearchOut(
        search_id=search.id,
        role=search.role,
        role_label=_role_label(search.role, data) or search.role,
        channel=search.channel,
        opened_turn=search.opened_turn,
        status=search.status,
        monthly_cost_cents=data.balance.hiring.job_post_cost_cents
        if search.channel == "job_post" and search.status == "open"
        else 0,
        open_candidates=sum(
            1 for c in state.candidates if c.search_id == search.id and c.status == "open"
        ),
    )
