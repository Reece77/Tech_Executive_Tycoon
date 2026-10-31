"""Load live GameState from a save and write back only what changed.

Live state only (M1b sweep rule 1): staff (active and notice employments), open candidates,
open searches, pending offers, active org units, hiring plans that are not closed, products
that are not retired with their segments, every market segment (M3), and the
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
from functools import cache
from typing import Any, cast

from sqlalchemy import Table, Update, and_, bindparam, delete, func, insert, inspect, select
from sqlalchemy.orm import Session

from tst.db.mappers import (
    candidate_from_row,
    candidate_to_row,
    company_to_row,
    employment_from_row,
    employment_to_row,
    event_from_row,
    event_to_row,
    finance_from_row,
    finance_to_row,
    game_state_from_rows,
    market_from_row,
    market_to_row,
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
    product_from_row,
    product_segment_from_row,
    product_segment_to_row,
    product_to_row,
    queued_from_row,
    queued_to_row,
    reveal_from_rows,
    reveal_to_rows,
    rival_from_row,
    rival_to_row,
    round_nominee_row,
    search_from_row,
    search_to_row,
    seat_history_row,
    storyline_from_row,
    storyline_to_row,
    unit_from_row,
    unit_to_row,
)
from tst.db.models import (
    BoardSeatHistoryRow,
    BoardSeatRow,
    CandidateRow,
    CapTableEntryRow,
    CompanyRow,
    EmploymentRow,
    EventQueueRow,
    EventRow,
    ExecSeatRow,
    FreeAgentRow,
    FundingRoundRow,
    HiringPlanRow,
    LedgerEntryRow,
    LedgerLineRow,
    MarketSegmentRow,
    OfferRow,
    OptionGrantRow,
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
    PoachApproachRow,
    ProductDivisionRow,
    ProductRow,
    ProductSegmentRow,
    RelationshipRow,
    RivalEffectRow,
    RivalMoveRow,
    RoundNomineeRow,
    SafeRow,
    SaveMetaRow,
    SearchLevelRow,
    SearchRow,
    SegmentShareRow,
    StorylineRow,
    TermSheetRow,
    UnitServicesRow,
    WorkforcePoolRow,
)
from tst.sim.errors import SaveNotFoundError
from tst.sim.finance.models import (
    BoardSeat,
    CapEntry,
    FundingRound,
    OptionGrant,
    Safe,
    TermSheet,
)
from tst.sim.hiring.models import NextIds
from tst.sim.ledger import LedgerEntry
from tst.sim.org.models import ExecSeat
from tst.sim.people.models import RevealState
from tst.sim.people.relationships import Relationship
from tst.sim.rivals.models import (
    FreeAgent,
    PoachApproach,
    RivalEffect,
    RivalMove,
    SegmentShare,
    WorkforcePool,
)
from tst.sim.state import GameState

META_ID = 1
RIVAL_MOVE_MEMORY = 24  # months of rival moves loaded: news, cooldowns, stance (M5)
EVENT_MEMORY = 24  # months of events loaded: the director's longest cooldown (M6, 16.1)
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
    nominees = {r.round_id: r.person_id for r in session.scalars(select(RoundNomineeRow))}
    histories = {
        r.seat_id: tuple(float(v) for v in r.history)
        for r in session.scalars(select(BoardSeatHistoryRow))
    }
    seats = tuple(
        finance_from_row(BoardSeat, r, history=histories.get(r.id, ()))
        for r in session.scalars(select(BoardSeatRow).order_by(BoardSeatRow.id))
    )
    free_agents = (
        tuple(
            rival_from_row(FreeAgent, r)
            for r in session.scalars(
                select(FreeAgentRow)
                .where(FreeAgentRow.status == "available")
                .order_by(FreeAgentRow.person_id)
            )
        )
        if has_table(session, FreeAgentRow)
        else ()
    )
    live_ids = sorted(
        {e.person_id for e in employments}
        | {c.person_id for c in candidates}
        | {o.actor_id for o in offers}
        | {p.owner_id for p in plans}
        | {s.person_id for s in seats if s.person_id is not None}
        | {a.person_id for a in free_agents}
    )

    def in_live(column: Any) -> Any:
        return column.in_(live_ids)

    skills = _by_person(_rows(session, PersonSkillRow, in_live(PersonSkillRow.person_id)))
    personality = _by_person(
        _rows(session, PersonPersonalityRow, in_live(PersonPersonalityRow.person_id))
    )
    hidden = _by_person(_rows(session, PersonHiddenRow, in_live(PersonHiddenRow.person_id)))
    interests = _by_person(_rows(session, PersonInterestRow, in_live(PersonInterestRow.person_id)))
    tags = _by_person(_rows(session, PersonTagRow, in_live(PersonTagRow.person_id)))
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
    for r in _rows(session, PersonRevealRow, in_live(PersonRevealRow.person_id)):
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
    products = tuple(
        product_from_row(r)
        for r in session.scalars(
            select(ProductRow).where(ProductRow.status != "retired").order_by(ProductRow.id)
        )
    )
    m8 = has_table(session, ExecSeatRow)  # M8 side tables (0020_divisions)
    if m8:
        divisions = {
            r.product_id: r.division_id for r in session.scalars(select(ProductDivisionRow))
        }
        services = {r.unit_id: r.services for r in session.scalars(select(UnitServicesRow))}
        levels = {r.search_id: r.level for r in session.scalars(select(SearchLevelRow))}
        products = tuple(replace(p, division_id=divisions.get(p.id)) for p in products)
    else:
        services, levels = {}, {}
    product_ids = [p.id for p in products]
    return replace(
        state,
        searches=tuple(
            replace(search_from_row(r), level=levels.get(r.id))
            for r in session.scalars(
                select(SearchRow).where(SearchRow.status == "open").order_by(SearchRow.id)
            )
        ),
        candidates=tuple(candidates),
        offers=tuple(offers),
        units=tuple(
            replace(unit_from_row(r), services=services.get(r.id))  # type: ignore[arg-type]
            for r in session.scalars(
                select(OrgUnitRow).where(OrgUnitRow.status == "active").order_by(OrgUnitRow.id)
            )
        ),
        plans=tuple(plans),
        products=products,
        product_segments=tuple(
            product_segment_from_row(r)
            for r in session.scalars(
                select(ProductSegmentRow)
                .where(ProductSegmentRow.product_id.in_(product_ids))
                .order_by(ProductSegmentRow.product_id, ProductSegmentRow.segment)
            )
        ),
        markets=tuple(
            market_from_row(r)
            for r in session.scalars(
                select(MarketSegmentRow).order_by(
                    MarketSegmentRow.category, MarketSegmentRow.segment
                )
            )
        ),
        person_states=tuple(
            person_state_from_row(r)
            for r in session.scalars(
                select(PersonStateRow)
                .where(in_live(PersonStateRow.person_id))
                .order_by(PersonStateRow.person_id)
            )
        ),
        cap_entries=_all(session, CapEntry, CapTableEntryRow),
        grants=_all(session, OptionGrant, OptionGrantRow),
        safes=_all(session, Safe, SafeRow),
        rounds=tuple(
            finance_from_row(FundingRound, r, nominee_id=nominees.get(r.id))
            for r in session.scalars(select(FundingRoundRow).order_by(FundingRoundRow.id))
        ),
        term_sheets=_all(session, TermSheet, TermSheetRow),
        seats=seats,
        pools=tuple(
            rival_from_row(WorkforcePool, r)
            for r in session.scalars(
                select(WorkforcePoolRow).order_by(
                    WorkforcePoolRow.company_id, WorkforcePoolRow.function
                )
            )
        ),
        rival_effects=tuple(
            rival_from_row(RivalEffect, r)
            for r in session.scalars(
                select(RivalEffectRow)
                .where(RivalEffectRow.end_turn >= meta.current_turn - 1)
                .order_by(RivalEffectRow.id)
            )
        ),
        rival_moves=tuple(
            rival_from_row(RivalMove, r)
            for r in session.scalars(
                select(RivalMoveRow)
                .where(RivalMoveRow.turn >= meta.current_turn - RIVAL_MOVE_MEMORY)
                .order_by(RivalMoveRow.id)
            )
        ),
        approaches=tuple(
            rival_from_row(PoachApproach, r)
            for r in session.scalars(
                select(PoachApproachRow)
                .where(PoachApproachRow.status.in_(("pending", "accepted")))
                .order_by(PoachApproachRow.id)
            )
        ),
        segment_shares=tuple(
            rival_from_row(SegmentShare, r)
            for r in session.scalars(
                select(SegmentShareRow)
                .where(SegmentShareRow.product_id.in_(product_ids))
                .order_by(SegmentShareRow.product_id, SegmentShareRow.segment)
            )
        ),
        free_agents=free_agents,
        **_event_state(session, meta.current_turn),
        relationships=(
            tuple(
                Relationship(r.person_id, r.other_person_id, r.value, r.start_value, r.since_turn)
                for r in session.scalars(
                    select(RelationshipRow).order_by(
                        RelationshipRow.person_id, RelationshipRow.other_person_id
                    )
                )
            )
            if has_table(session, RelationshipRow)
            else ()
        ),
        exec_seats=(
            tuple(
                ExecSeat(r.company_id, r.seat, r.person_id, r.since_turn)
                for r in session.scalars(
                    select(ExecSeatRow).order_by(ExecSeatRow.company_id, ExecSeatRow.seat)
                )
            )
            if m8
            else ()
        ),
        next_ids=_event_ids(session, next_ids_from_meta(meta)),
    )


def _event_state(session: Session, turn: int) -> dict[str, Any]:
    """Events of the last 24 months and any still open, active storylines and follow-ups not
    yet queued (M6). Empty on a save whose migration 0016 has not run yet."""
    if not has_table(session, EventRow):
        return {}
    return {
        "events": tuple(
            event_from_row(r)
            for r in session.scalars(
                select(EventRow)
                .where(
                    (EventRow.turn > turn - EVENT_MEMORY) | EventRow.status.in_(("pending", "open"))
                )
                .order_by(EventRow.id)
            )
        ),
        "storylines": tuple(
            storyline_from_row(r)
            for r in session.scalars(
                select(StorylineRow)
                .where(StorylineRow.status == "active")
                .order_by(StorylineRow.id)
            )
        ),
        "queued": tuple(
            queued_from_row(r)
            for r in session.scalars(
                select(EventQueueRow)
                .where(EventQueueRow.done.is_(False))
                .order_by(EventQueueRow.id)
            )
        ),
    }


def _event_ids(session: Session, ids: NextIds) -> NextIds:
    """Event, storyline and queue ids continue from the largest stored (M6: not in
    save_meta, so an old save's migration 0013 never reads a column it lacks)."""
    if not has_table(session, EventRow):
        return ids

    def after(model: Any) -> int:
        return int(session.scalar(select(func.max(model.id))) or 0) + 1

    return replace(
        ids, event=after(EventRow), storyline=after(StorylineRow), queued=after(EventQueueRow)
    )


def has_table(session: Session, model: Any) -> bool:
    """Whether the save already has a table added or rebuilt after 0013, with the model's
    columns. Migration 0013 loads and syncs state through the current models, so on an
    older save it runs before later migrations have made their tables; those tables then
    read as empty and are not written (M6 sub-task 0)."""
    insp = inspect(session.connection())
    if not insp.has_table(model.__tablename__):
        return False
    have = {c["name"] for c in insp.get_columns(model.__tablename__)}
    return {c.name for c in model.__table__.columns} <= have


def _rows(session: Session, model: Any, where: Any) -> list[Any]:
    """Plain rows (column attributes only) for a large child table: building ORM objects
    for every skill and knowledge record was most of a load's time once rivals had people
    (M5)."""
    return list(session.execute(select(model.__table__).where(where)).all())


def _all[T](session: Session, cls: type[T], row: Any) -> tuple[T, ...]:
    """Every row of a small finance table (M4), by id."""
    return tuple(finance_from_row(cls, r) for r in session.scalars(select(row).order_by(row.id)))


# --- Writing --------------------------------------------------------------------------------


def _changed[T](old: Iterable[T], new: Iterable[T], key: Any) -> list[T]:
    """Items of `new` that are new or differ from the item with the same key in `old`."""
    before = {key(x): x for x in old}
    return [x for x in new if before.get(key(x)) != x]


def _write[T](session: Session, old: Iterable[T], new: Iterable[T], key: Any, to_row: Any) -> None:
    """Write the changed items of `new`: one bulk UPDATE by primary key for items that were in
    `old` (their rows exist), a merge for the rest. A merge per row costs a SELECT, which made
    every turn write rivals' people and shares one at a time (M6 sub-task 0)."""
    known = {key(x) for x in old}
    updates: list[dict[str, Any]] = []
    model: Any = None
    for item in _changed(old, new, key):
        row = to_row(item)
        if key(item) in known:
            model = type(row)
            updates.append({a.key: getattr(row, a.key) for a in model.__mapper__.column_attrs})
        else:
            session.merge(row)
    _update_rows(session, model, updates)


@cache
def _update_statement(model: Any, keys: tuple[str, ...]) -> Update:
    """UPDATE <table> SET <keys> WHERE <primary key>, with a bind parameter per attribute."""
    mapper = model.__mapper__
    pk = {mapper.get_property_by_column(c).key: c for c in mapper.primary_key}
    return (
        model.__table__.update()
        .where(and_(*(col == bindparam(f"b_{k}") for k, col in pk.items())))
        .values({mapper.columns[k].name: bindparam(f"b_{k}") for k in keys if k not in pk})
    )


def _update_rows(session: Session, model: Any, rows: list[dict[str, Any]]) -> None:
    """Bulk UPDATE by primary key as one Core executemany per set of attributes. The ORM's
    bulk UPDATE builds each row's parameters in Python and cost more than the SQL itself
    (M7a sub-task 0). `rows` are attribute -> value and include the primary key."""
    if not rows:
        return
    session.flush()  # a Core statement does not flush: rows it may reference come first
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row)].append({f"b_{k}": v for k, v in row.items()})
    for keys, params in groups.items():
        session.execute(_update_statement(model, keys), params)


def _insert(session: Session, rows: Iterable[Any]) -> None:
    """Insert new rows with one executemany per table instead of the unit of work (a new
    save writes thousands of people's child rows; M6 sub-task 0). A column left None that
    has a default keeps its default."""
    by_model: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        model = type(row)
        by_model[model].append(
            {
                a.key: v
                for a in model.__mapper__.column_attrs
                if (v := getattr(row, a.key)) is not None
                or (a.columns[0].default is None and a.columns[0].server_default is None)
            }
        )
    for model, values in by_model.items():
        session.execute(insert(model), values)


def insert_rows(session: Session, rows: Iterable[Any]) -> None:
    """`_insert` for append-only rows of a turn (logs, months, snapshots): one executemany per
    table instead of the unit of work (M7a sub-task 0)."""
    session.flush()  # rows they reference come first
    _insert(session, rows)


def insert_entries(session: Session, entries: Iterable[LedgerEntry]) -> None:
    """Ledger entries and their lines as two executemanys, entry ids continuing from the
    largest stored (the unit of work inserted them one entry at a time; M7a sub-task 0)."""
    entries = list(entries)
    if not entries:
        return
    session.flush()
    first = int(session.scalar(select(func.max(LedgerEntryRow.id))) or 0) + 1
    session.execute(
        insert(cast(Table, LedgerEntryRow.__table__)),
        [
            {"id": first + i, "turn": e.turn, "company_id": e.company_id, "memo": e.memo}
            for i, e in enumerate(entries)
        ],
    )
    lines = [
        {"entry_id": first + i, "account_code": ln.account, "amount_cents": ln.amount}
        for i, e in enumerate(entries)
        for ln in e.lines
    ]
    divisions = [ln.division_id for e in entries for ln in e.lines]
    if any(d is not None for d in divisions):  # M8 (18.1); absent keeps pre-0020 saves working
        for line, division in zip(lines, divisions, strict=True):
            line["division_id"] = division
    session.execute(insert(cast(Table, LedgerLineRow.__table__)), lines)


def _sync_relationships(session: Session, old: GameState, new: GameState) -> None:
    """Pairs are written like other rows; a pair that ended is deleted (16.7)."""
    ended = {r.key for r in old.relationships} - {r.key for r in new.relationships}
    for a, b in sorted(ended):
        session.execute(
            delete(RelationshipRow).where(
                RelationshipRow.person_id == a, RelationshipRow.other_person_id == b
            )
        )
    _write(
        session,
        old.relationships,
        new.relationships,
        lambda r: r.key,
        lambda r: RelationshipRow(
            person_id=r.a,
            other_person_id=r.b,
            value=r.value,
            start_value=r.start,
            since_turn=r.since_turn,
        ),
    )


def _sync_reveal(
    session: Session,
    old: RevealState | None,
    new: RevealState,
    changed: list[dict[str, Any]],
) -> None:
    """Write one reveal; its changed attribute records go to `changed`, which the caller
    writes for every reveal at once (M7a: one UPDATE per reveal was a tenth of a turn)."""
    if old is None:
        _insert(session, reveal_to_rows(new))
        return
    base = {"person_id": new.person_id, "observer_company_id": new.observer_company_id}
    old_records = dict(old.attributes)
    changed += [
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

    _write(session, old.companies, new.companies, lambda c: c.id, company_to_row)
    session.flush()
    _write(session, old.products, new.products, lambda p: p.id, product_to_row)
    session.flush()
    _write(
        session,
        old.product_segments,
        new.product_segments,
        lambda s: (s.product_id, s.segment),
        product_segment_to_row,
    )
    _write(session, old.markets, new.markets, lambda m: (m.category, m.segment), market_to_row)

    old_people = {p.id: p for p in old.people}
    skill_updates: list[dict[str, Any]] = []
    asks: list[dict[str, Any]] = []  # a poached key person's new ask (M5, 15.6)
    added = [p for p in new.people if p.id not in old_people]
    rows = [person_to_rows(p) for p in added]
    session.add_all(r[0] for r in rows)  # person rows first: children reference them
    session.flush()
    _insert(session, (child for r in rows for child in r[1:]))
    for person in new.people:
        before = old_people.get(person.id)
        if (
            before is not None
            and before.salary_expectation_cents != person.salary_expectation_cents
        ):
            asks.append(
                {"id": person.id, "salary_expectation_cents": person.salary_expectation_cents}
            )
        if before is not None and before != person:
            old_skills = before.skills.as_dict()
            skill_updates += [
                {"person_id": person.id, "skill": k, "value": v}
                for k, v in person.skills.items
                if old_skills[k] != v
            ]
    session.flush()
    _update_rows(session, PersonSkillRow, skill_updates)
    _update_rows(session, PersonRow, asks)

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
    _write(
        session, old.person_states, new.person_states, lambda p: p.person_id, person_state_to_row
    )

    old_reveals = {(r.observer_company_id, r.person_id): r for r in old.reveals}
    reveal_updates: list[dict[str, Any]] = []
    for reveal in new.reveals:
        known = old_reveals.get((reveal.observer_company_id, reveal.person_id))
        if known != reveal:
            _sync_reveal(session, known, reveal, reveal_updates)
    _update_rows(session, PersonRevealRow, reveal_updates)

    # Finance (M4): rounds before their term sheets.
    for items in (
        _changed(old.cap_entries, new.cap_entries, lambda e: e.id),
        _changed(old.grants, new.grants, lambda g: g.id),
        _changed(old.safes, new.safes, lambda s: s.id),
        _changed(old.rounds, new.rounds, lambda r: r.id),
        _changed(old.term_sheets, new.term_sheets, lambda t: t.id),
        _changed(old.seats, new.seats, lambda s: s.id),
    ):
        for item in items:
            session.merge(finance_to_row(item))
        session.flush()
    for seat in _changed(old.seats, new.seats, lambda s: s.id):
        session.merge(seat_history_row(seat))
    for rnd in _changed(old.rounds, new.rounds, lambda r: r.id):
        session.merge(round_nominee_row(rnd))

    # Rivals (M5)
    for olds, news, rival_key in (
        (old.pools, new.pools, lambda p: (p.company_id, p.function)),
        (old.rival_effects, new.rival_effects, lambda e: e.id),
        (old.rival_moves, new.rival_moves, lambda m: m.id),
        (old.approaches, new.approaches, lambda a: a.id),
        (old.segment_shares, new.segment_shares, lambda s: (s.product_id, s.segment)),
        (old.free_agents, new.free_agents, lambda a: a.person_id),
    ):
        _write(session, olds, news, rival_key, rival_to_row)

    changed = (old.events, old.storylines, old.queued) != (new.events, new.storylines, new.queued)
    if changed and has_table(session, EventRow):
        # Storylines before the events that name them, events before their follow-ups.
        _write(session, old.storylines, new.storylines, lambda s: s.id, storyline_to_row)
        session.flush()
        _write(session, old.events, new.events, lambda e: e.id, event_to_row)
        session.flush()
        _write(session, old.queued, new.queued, lambda q: q.id, queued_to_row)

    if old.relationships != new.relationships and has_table(session, RelationshipRow):
        _sync_relationships(session, old, new)
    _sync_m8(session, old, new)

    if old.next_ids != new.next_ids:
        next_ids_to_meta(read_meta(session), new.next_ids)
    if (old.save_meta.game_state, old.save_meta.ended_turn) != (
        new.save_meta.game_state,
        new.save_meta.ended_turn,
    ):
        meta = read_meta(session)
        meta.game_state = new.save_meta.game_state
        meta.ended_turn = new.save_meta.ended_turn
    session.flush()


def _sync_m8(session: Session, old: GameState, new: GameState) -> None:
    """Divisions' services, products' divisions, exec-level searches and seats (M8)."""
    old_units = {u.id: u.services for u in old.units}
    old_products = {p.id: p.division_id for p in old.products}
    old_levels = {s.id: s.level for s in old.searches}
    rows: list[Any] = [
        UnitServicesRow(unit_id=u.id, services=u.services)
        for u in new.units
        if u.services is not None and old_units.get(u.id) != u.services
    ]
    rows += [
        ProductDivisionRow(product_id=p.id, division_id=p.division_id)
        for p in new.products
        if old_products.get(p.id) != p.division_id
    ]
    rows += [
        SearchLevelRow(search_id=s.id, level=s.level)
        for s in new.searches
        if s.level is not None and old_levels.get(s.id) != s.level
    ]
    rows += [
        ExecSeatRow(
            company_id=s.company_id, seat=s.seat, person_id=s.person_id, since_turn=s.since_turn
        )
        for s in _changed(old.exec_seats, new.exec_seats, lambda s: (s.company_id, s.seat))
    ]
    if not rows or not has_table(session, ExecSeatRow):
        return
    session.flush()
    for row in rows:
        session.merge(row)


# --- The last state written, per save (M6 sub-task 0) -----------------------------------------


def live_view(state: GameState) -> GameState:
    """What `load_state` would return after `state` was written: the same live set, by the
    same rules (golden seed 1 runs with TST_STATE_CACHE_CHECK=1, which compares them)."""
    staff = tuple(e for e in state.employments if e.status in STAFF_STATUSES)
    candidates = tuple(c for c in state.candidates if c.status == "open")
    offers = tuple(o for o in state.offers if o.status == "pending")
    plans = tuple(p for p in state.plans if p.status != "closed")
    free_agents = tuple(a for a in state.free_agents if a.status == "available")
    live = (
        {e.person_id for e in staff}
        | {c.person_id for c in candidates}
        | {o.actor_id for o in offers}
        | {p.owner_id for p in plans}
        | {s.person_id for s in state.seats if s.person_id is not None}
        | {a.person_id for a in free_agents}
    )
    products = tuple(p for p in state.products if p.status != "retired")
    product_ids = {p.id for p in products}
    turn = state.turn
    return replace(
        state,
        people=tuple(p for p in state.people if p.id in live),
        employments=staff,
        reveals=tuple(r for r in state.reveals if r.person_id in live and r.attributes),
        searches=tuple(s for s in state.searches if s.status == "open"),
        candidates=candidates,
        offers=offers,
        units=tuple(u for u in state.units if u.status == "active"),
        plans=plans,
        products=products,
        product_segments=tuple(s for s in state.product_segments if s.product_id in product_ids),
        person_states=tuple(p for p in state.person_states if p.person_id in live),
        rival_effects=tuple(e for e in state.rival_effects if e.end_turn >= turn - 1),
        rival_moves=tuple(m for m in state.rival_moves if m.turn >= turn - RIVAL_MOVE_MEMORY),
        approaches=tuple(a for a in state.approaches if a.status in ("pending", "accepted")),
        segment_shares=tuple(s for s in state.segment_shares if s.product_id in product_ids),
        free_agents=free_agents,
        events=tuple(
            e
            for e in state.events
            if e.turn > turn - EVENT_MEMORY or e.status in ("pending", "open")
        ),
        storylines=tuple(s for s in state.storylines if s.status == "active"),
        queued=tuple(q for q in state.queued if not q.done),
    )
