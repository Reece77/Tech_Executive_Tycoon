"""Load live GameState from a save and write back only what changed.

Live state only (M1b sweep rule 1): staff (active and notice employments), open candidates,
open searches, pending offers, active org units, hiring plans that are not closed, and the
people and knowledge records they need (including whoever made a pending offer and every
plan's owner, who may have left). Records that leave the live set keep their rows, with a
status, in the database.

`sync_state(old, new)` compares the state that was loaded with the state the sim returned
and writes inserts and in-place updates for the differences, so a turn costs time in
proportion to what happened, not to the size of the save.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tst.db.mappers import (
    candidate_from_row,
    candidate_to_row,
    company_to_row,
    employment_from_row,
    employment_to_row,
    game_state_from_rows,
    next_ids_from_meta,
    next_ids_to_meta,
    offer_from_row,
    offer_to_row,
    person_from_rows,
    person_state_from_row,
    person_state_to_row,
    person_to_rows,
    plan_from_row,
    plan_to_row,
    reveal_from_rows,
    reveal_to_rows,
    search_from_row,
    search_to_row,
    unit_from_row,
    unit_to_row,
)
from tst.db.models import (
    CandidateRow,
    CompanyRow,
    EmploymentRow,
    HiringPlanRow,
    OfferRow,
    OrgUnitRow,
    PersonHiddenRow,
    PersonInterestRow,
    PersonPersonalityRow,
    PersonProfileRevealRow,
    PersonRevealRow,
    PersonRow,
    PersonSkillRow,
    PersonStateRow,
    PersonTagRevealRow,
    PersonTagRow,
    SaveMetaRow,
    SearchRow,
)
from tst.sim.errors import SaveNotFoundError
from tst.sim.people.models import RevealState
from tst.sim.state import GameState

META_ID = 1
STAFF_STATUSES = ("active", "notice")


def read_meta(session: Session) -> SaveMetaRow:
    meta = session.get(SaveMetaRow, META_ID)
    if meta is None:
        raise SaveNotFoundError("save file has no save_meta row")
    return meta


def _by_person[R](rows: Iterable[R]) -> dict[int, list[R]]:
    grouped: dict[int, list[R]] = defaultdict(list)
    for row in rows:
        grouped[row.person_id].append(row)  # type: ignore[attr-defined]
    return grouped


def load_state(session: Session) -> GameState:
    meta = read_meta(session)
    companies = list(session.scalars(select(CompanyRow)))

    employments = [
        employment_from_row(r)
        for r in session.scalars(
            select(EmploymentRow)
            .where(EmploymentRow.status.in_(STAFF_STATUSES))
            .order_by(EmploymentRow.id)
        )
    ]
    candidates = [
        candidate_from_row(r)
        for r in session.scalars(
            select(CandidateRow)
            .where(CandidateRow.status == "open")
            .order_by(CandidateRow.person_id)
        )
    ]
    offers = [
        offer_from_row(r)
        for r in session.scalars(
            select(OfferRow).where(OfferRow.status == "pending").order_by(OfferRow.id)
        )
    ]
    plans = [
        plan_from_row(r)
        for r in session.scalars(
            select(HiringPlanRow).where(HiringPlanRow.status != "closed").order_by(HiringPlanRow.id)
        )
    ]
    live_ids = sorted(
        {e.person_id for e in employments}
        | {c.person_id for c in candidates}
        | {o.actor_id for o in offers}
        | {p.owner_id for p in plans}
    )

    def in_live(column: Any) -> Any:
        return column.in_(live_ids)

    skills = _by_person(
        session.scalars(select(PersonSkillRow).where(in_live(PersonSkillRow.person_id)))
    )
    personality = _by_person(
        session.scalars(select(PersonPersonalityRow).where(in_live(PersonPersonalityRow.person_id)))
    )
    hidden = _by_person(
        session.scalars(select(PersonHiddenRow).where(in_live(PersonHiddenRow.person_id)))
    )
    interests = _by_person(
        session.scalars(select(PersonInterestRow).where(in_live(PersonInterestRow.person_id)))
    )
    tags = _by_person(session.scalars(select(PersonTagRow).where(in_live(PersonTagRow.person_id))))
    people = tuple(
        person_from_rows(
            row,
            skills[row.id],
            personality[row.id],
            hidden[row.id],
            interests[row.id],
            tags[row.id],
        )
        for row in session.scalars(
            select(PersonRow).where(in_live(PersonRow.id)).order_by(PersonRow.id)
        )
    )

    def key(row: Any) -> tuple[int, int]:
        return (row.observer_company_id, row.person_id)

    records: dict[tuple[int, int], list[PersonRevealRow]] = defaultdict(list)
    for r in session.scalars(select(PersonRevealRow).where(in_live(PersonRevealRow.person_id))):
        records[key(r)].append(r)
    profiles = {
        key(r): r
        for r in session.scalars(
            select(PersonProfileRevealRow).where(in_live(PersonProfileRevealRow.person_id))
        )
    }
    tag_reveals: dict[tuple[int, int], list[PersonTagRevealRow]] = defaultdict(list)
    for t in session.scalars(
        select(PersonTagRevealRow).where(in_live(PersonTagRevealRow.person_id))
    ):
        tag_reveals[key(t)].append(t)
    reveals = tuple(
        reveal_from_rows(o, p, records[(o, p)], profiles.get((o, p)), tag_reveals[(o, p)])
        for o, p in sorted(records)
    )

    state = game_state_from_rows(meta, companies, people, tuple(employments), reveals)
    return replace(
        state,
        searches=tuple(
            search_from_row(r)
            for r in session.scalars(
                select(SearchRow).where(SearchRow.status == "open").order_by(SearchRow.id)
            )
        ),
        candidates=tuple(candidates),
        offers=tuple(offers),
        units=tuple(
            unit_from_row(r)
            for r in session.scalars(
                select(OrgUnitRow).where(OrgUnitRow.status == "active").order_by(OrgUnitRow.id)
            )
        ),
        plans=tuple(plans),
        person_states=tuple(
            person_state_from_row(r)
            for r in session.scalars(
                select(PersonStateRow)
                .where(in_live(PersonStateRow.person_id))
                .order_by(PersonStateRow.person_id)
            )
        ),
        next_ids=next_ids_from_meta(meta),
    )


# --- Writing --------------------------------------------------------------------------------


def _changed[T](old: Iterable[T], new: Iterable[T], key: Any) -> list[T]:
    """Items of `new` that are new or differ from the item with the same key in `old`."""
    before = {key(x): x for x in old}
    return [x for x in new if before.get(key(x)) != x]


def _sync_reveal(session: Session, old: RevealState | None, new: RevealState) -> None:
    if old is None:
        session.add_all(reveal_to_rows(new))
        return
    base = {"person_id": new.person_id, "observer_company_id": new.observer_company_id}
    old_records = dict(old.attributes)
    changed = [
        {
            **base,
            "attribute": attr,
            "hw": rec.hw,
            "center_offset": rec.offset,
            "last_updated_turn": rec.last_updated_turn,
        }
        for attr, rec in new.attributes
        if old_records.get(attr) != rec
    ]
    if changed:
        session.execute(update(PersonRevealRow), changed)
    if old.profile_revealed_turn is None and new.profile_revealed_turn is not None:
        session.add(PersonProfileRevealRow(**base, revealed_turn=new.profile_revealed_turn))
    known = {tag for tag, _ in old.revealed_tags}
    session.add_all(
        PersonTagRevealRow(**base, tag=tag, revealed_turn=turn)
        for tag, turn in new.revealed_tags
        if tag not in known
    )


def sync_state(session: Session, old: GameState | None, new: GameState) -> None:
    """Write the differences between `old` (as loaded, or None for a new save) and `new`."""
    old = old or GameState(save_meta=new.save_meta, turn=new.turn, companies=())

    for company in _changed(old.companies, new.companies, lambda c: c.id):
        session.merge(company_to_row(company))
    session.flush()

    old_people = {p.id: p for p in old.people}
    skill_updates: list[dict[str, Any]] = []
    added = [p for p in new.people if p.id not in old_people]
    rows = [person_to_rows(p) for p in added]
    session.add_all(r[0] for r in rows)  # person rows first: children reference them
    session.flush()
    session.add_all(child for r in rows for child in r[1:])
    for person in new.people:
        before = old_people.get(person.id)
        if before is not None and before != person:
            old_skills = before.skills.as_dict()
            skill_updates += [
                {"person_id": person.id, "skill": k, "value": v}
                for k, v in person.skills.items
                if old_skills[k] != v
            ]
    session.flush()
    if skill_updates:
        session.execute(update(PersonSkillRow), skill_updates)

    # Units before employments and plans, which reference them; plans before offers.
    for unit in _changed(old.units, new.units, lambda u: u.id):
        session.merge(unit_to_row(unit))
    session.flush()
    for employment in _changed(old.employments, new.employments, lambda e: e.id):
        session.merge(employment_to_row(employment))
    for search in _changed(old.searches, new.searches, lambda s: s.id):
        session.merge(search_to_row(search))
    session.flush()
    for plan in _changed(old.plans, new.plans, lambda p: p.id):
        session.merge(plan_to_row(plan))
    session.flush()
    for candidate in _changed(old.candidates, new.candidates, lambda c: c.person_id):
        session.merge(candidate_to_row(candidate))
    for offer in _changed(old.offers, new.offers, lambda o: o.id):
        session.merge(offer_to_row(offer))
    for ps in _changed(old.person_states, new.person_states, lambda p: p.person_id):
        session.merge(person_state_to_row(ps))

    old_reveals = {(r.observer_company_id, r.person_id): r for r in old.reveals}
    for reveal in new.reveals:
        known = old_reveals.get((reveal.observer_company_id, reveal.person_id))
        if known != reveal:
            _sync_reveal(session, known, reveal)

    if old.next_ids != new.next_ids:
        next_ids_to_meta(read_meta(session), new.next_ids)
    session.flush()
