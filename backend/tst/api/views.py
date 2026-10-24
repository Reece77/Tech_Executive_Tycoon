"""Build API responses from the live state, as seen by the viewing company (ADR-0007).

Ranges come from the company's knowledge records; true values never leave this module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.api.schemas.people import (
    AttributeOut,
    CandidacyOut,
    EmploymentOut,
    EnergyOut,
    InboxItemOut,
    KnowledgeOut,
    MoralePointOut,
    PendingOfferOut,
    PersonProfileOut,
    PersonSummaryOut,
    RangeOut,
    SearchOut,
    TagOut,
)
from tst.db.inbox import InboxMessage
from tst.db.models import DecisionLogRow, PersonMoraleLogRow
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.errors import UnknownPersonError
from tst.sim.hiring.formulas import market_mid_cents, severance_cents
from tst.sim.hiring.models import Search
from tst.sim.hiring.phases import employment_monthly_cost_cents
from tst.sim.org.rules import is_remote
from tst.sim.people.formulas import potential_phrase
from tst.sim.people.models import PA_KEY, Person, RevealState
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState

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
        market_rate = market_mid_cents(
            data.game_data.role(employment.role).salary_band_mid_cents[employment.level],
            data.game_data.region(person.region).salary_multiplier_bp,
        )
    return PersonSummaryOut(
        person_id=person.id,
        name=f"{person.first_name} {person.last_name}",
        age=person.age(state.turn),
        region=person.region,
        role=role,
        role_label=role_label(role, data),
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
            monthly_cost_cents=employment_monthly_cost_cents(
                employment, data.balance, remote=is_remote(state, employment)
            ),
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
        personality=_personality(person, reveal, data),
        work_style=person.work_style if known else None,
        work_style_matches_role=None
        if not known or role is None
        else person.work_style == role.work_style,
        morale_history=[
            MoralePointOut(turn=r.turn, date_label=format_turn(r.turn), morale=r.morale)
            for r in reversed(rows)
        ],
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
    )


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
    appeal = hiring.offer.stage_appeal.get(company.stage, 0.0)
    if appeal < 0:
        reasons.append(f"A {STAGE_LABELS[company.stage].lower()} company is a harder sell.")
    elif appeal > 0:
        reasons.append("Your company's stage makes the offer more attractive.")
    return reasons
