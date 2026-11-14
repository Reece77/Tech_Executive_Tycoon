"""Building the Family screen's response (M36, formulas.md 45.9) from the state. Ratings come
from the player's revealed ranges only; potential is a phrase; hidden traits never appear."""

from __future__ import annotations

from tst.api.schemas.family import (
    AdviserOut,
    DynastyOut,
    EducationChoiceOut,
    EstateOut,
    FamilyMemberOut,
    FamilyOut,
    GenerationOut,
    NoteOut,
    OpinionOut,
    ReadinessOut,
)
from tst.api.views import _personality, _skills
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.family import dynasty, estate, rules
from tst.sim.family.answers import COSTS, family_energy
from tst.sim.family.models import CHILD, EX_PARTNER, FamilyMember
from tst.sim.family.phase import time_now
from tst.sim.finance.board import average_confidence
from tst.sim.ledger import LedgerBalances
from tst.sim.people.formulas import potential_phrase
from tst.sim.people.models import PA_KEY
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState, family_partner

MONTHS_A_YEAR = 12  # tunable-exempt: calendar
BOARD_MID = 50.0  # 45.4's formula


def _readiness(state: GameState, m: FamilyMember, data: LoadedData) -> ReadinessOut | None:
    if m.relation != CHILD:
        return None
    b = data.balance
    rb = b.family.ready
    fit = rules.shown_ceo_fit(state, m.person_id, b)
    in_group = rules.in_group(state, m.person_id) is not None and m.company_turn is not None
    years = (
        min(rb.years_cap, (state.turn - (m.company_turn or state.turn)) / MONTHS_A_YEAR)
        if in_group
        else 0.0
    )
    board = average_confidence(state, state.player.id) if in_group else None
    return ReadinessOut(
        band=rules.readiness(state, m, b),
        points=round(rules.readiness_points(state, m, b), 1),
        fit=round(fit, 1),
        years=round(years, 1),
        seats=len(m.seats_held) if in_group else 0,
        board=round((board - BOARD_MID) / rb.board_divisor, 1) if board is not None else 0.0,
    )


def _choices(state: GameState, m: FamilyMember, data: LoadedData) -> list[EducationChoiceOut]:
    if m.relation != CHILD:
        return []
    ed = data.balance.family.education
    age = state.person(m.person_id).age(state.turn)
    stages = []
    if m.school is None and ed.school_age <= age < ed.university_age:
        stages.append("school")
    if m.university is None and ed.university_age <= age < ed.graduate_age:
        stages.append("university")
    if not m.mba and age >= ed.mba_from:
        stages.append("mba")
    out = []
    for (stage, tier), key in COSTS.items():
        if stage in stages:
            out.append(
                EducationChoiceOut(
                    stage=stage, tier=tier, cost_cents=ed.cents[key] if key is not None else 0
                )
            )
    return out


def member_out(state: GameState, m: FamilyMember, data: LoadedData) -> FamilyMemberOut:
    person = state.person(m.person_id)
    reveal = state.reveal(state.player.id, m.person_id)
    assert reveal is not None, "every family member has the player's view"
    lo, hi = revealed_range(person, reveal, PA_KEY)
    job = state.employment_of(m.person_id)
    company = state.company(job.company_id) if job is not None else None
    fb = data.balance.family
    return FamilyMemberOut(
        person_id=m.person_id,
        name=rules.full_name(person),
        relation=m.relation,
        age=person.age(state.turn),
        closeness=round(m.closeness, 1) if m.relation == CHILD else None,
        school=m.school,
        university=m.university,
        degree=m.degree,
        mba=m.mba,
        company_id=company.id if company is not None else None,
        company_name=company.name if company is not None else None,
        role=job.role if job is not None else None,
        level=job.level if job is not None else None,
        mentored=m.mentored,
        own_way=m.own_way,
        interests=list(person.interests),
        skills=_skills(person, reveal, data),
        personality=_personality(person, reveal, data),
        potential=potential_phrase(lo, hi, data.balance.reveal.pa_phrase_bounds),
        readiness=_readiness(state, m, data),
        choices=_choices(state, m, data),
        can_join=m.relation == CHILD and job is None and person.age(state.turn) >= fb.join_age,
    )


def family_out(state: GameState, balances: LedgerBalances | None, data: LoadedData) -> FamilyOut:
    family = state.family
    b = data.balance
    if family is None:
        return FamilyOut(
            exists=False,
            setting="none",
            head_id=None,
            head_name=None,
            head_mode="founder",
            family_time=0,
            max_time=b.family.max_time,
            time_now=0,
            energy_cost=0,
            relationship=None,
            married=False,
            partner=None,
            children=[],
            others=[],
            heirs=[],
            succession_open=None,
            step_back_open=False,
            adviser=None,
            estate=None,
            dynasty=None,
            notes=[],
            trust_since=None,
        )
    head = state.person(family.head_id)
    partner = family_partner(state)
    kids = rules.children(state)
    kid_ids = {k.person_id for k in kids}
    others = [
        m
        for m in state.family_members
        if m.person_id not in kid_ids
        and (partner is None or m.person_id != partner.person_id)
        and m.person_id != family.head_id
        and (m.relation == EX_PARTNER or m.relation == CHILD)
    ]
    adviser = None
    if family.adviser_id is not None:
        a = state.person(family.adviser_id)
        adviser = AdviserOut(
            person_id=a.id,
            name=rules.full_name(a),
            age=a.age(state.turn),
            retires_at=b.family.adviser_retire_age,
            opinions=[
                OpinionOut(
                    turn=o.turn,
                    date_label=format_turn(o.turn),
                    subject=o.subject,
                    subject_id=o.subject_id,
                    title=o.title,
                    stance=o.stance,
                    text=o.text,
                    overruled=o.overruled,
                )
                for o in reversed(family.opinions)
            ],
        )
    q = estate.quote(state, family.head_id, balances, b, data.game_data)
    region = b.estate_tax[q.region]
    est = EstateOut(
        region=q.region,
        rate=q.rate,
        exemption_cents=q.exemption_cents,
        used_exemption_cents=q.used_exemption_cents,
        shares=q.shares,
        share_price_cents=q.share_price_cents,
        shares_cents=q.shares_cents,
        cash_cents=q.cash_cents,
        other_cents=q.other_cents,
        estate_cents=q.estate_cents,
        taxable_cents=q.taxable_cents,
        tax_cents=q.tax_cents,
        shares_to_sell=q.shares_to_sell,
        family_bp_now=q.family_bp_now,
        family_bp_after=q.family_bp_after,
        control_bp=b.family.control_bp,
        trust_shares=q.trust_shares,
        gift_tax=region.gift_tax,
        lifetime_gifts_cents=family.lifetime_gifts_cents,
        gift_tax_paid_cents=family.gift_tax_cents,
        estate_tax_paid_cents=family.estate_tax_cents,
    )
    d = dynasty.dynasty(state, balances, b, data.game_data)
    assert d is not None
    dyn = DynastyOut(
        generations=[
            GenerationOut(
                person_id=g.person_id,
                name=g.name,
                from_label=format_turn(g.from_turn),
                to_label=format_turn(g.to_turn) if g.to_turn is not None else None,
                legacy=g.legacy,
                how=g.how,
            )
            for g in d.generations
        ],
        legacies=d.legacies,
        family_value_cents=d.family_value_cents,
        value_points=round(d.value_points, 1),
        control_losses=d.control_losses,
        loss_points=d.loss_points,
        total=d.total,
    )
    return FamilyOut(
        exists=True,
        setting=family.setting,
        head_id=head.id,
        head_name=rules.full_name(head),
        head_mode=family.head_mode,
        family_time=family.family_time,
        max_time=b.family.max_time,
        time_now=time_now(state, b),
        energy_cost=family_energy(state, b),
        relationship=round(family.relationship, 1) if partner is not None else None,
        married=family.married,
        partner=member_out(state, partner, data) if partner is not None else None,
        children=[member_out(state, k, data) for k in kids],
        others=[member_out(state, m, data) for m in others],
        heirs=rules.eligible_heirs(state, b),
        succession_open=family.succession_open,
        step_back_open=family.step_back_open,
        adviser=adviser,
        estate=est,
        dynasty=dyn,
        notes=[
            NoteOut(turn=n.turn, date_label=format_turn(n.turn), kind=n.kind, text=n.text)
            for n in reversed(family.notes)
        ],
        trust_since=format_turn(family.trust_turn) if family.trust_turn is not None else None,
    )
