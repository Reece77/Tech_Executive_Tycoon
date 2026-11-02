"""The "Former employee" profile (M7c): read-only, built from `former_staff` (what the player
knew at departure) and the History timeline. Never a true value (ADR-0007)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.api.history_views import timeline
from tst.api.schemas.people import (
    AttributeOut,
    FormerProfileOut,
    JobPeriodOut,
    LedOut,
    RangeOut,
    TagOut,
)
from tst.api.views import role_label
from tst.db.models import (
    CompanyRow,
    DecisionLogRow,
    FormerStaffRow,
    OfferRow,
    OrgUnitRow,
    PersonRow,
    ProductRow,
    StorylineRow,
)
from tst.db.state_io import has_table
from tst.loader import LoadedData
from tst.sim.actions.org import next_level
from tst.sim.actions.scaleup import EXEC_LEVEL
from tst.sim.calendar import format_turn
from tst.sim.errors import UnknownPersonError
from tst.sim.people.formulas import potential_phrase
from tst.sim.people.models import PA_KEY

HISTORY_LIMIT = 50  # entries on the profile; History holds the rest
PERSONALITY_GROUP = "personality"
REASONS = {
    "resigned": "Resigned",
    "fired": "Let go",
    "retired": "Retired",
    "company_failed": "Left when the company closed",
    "left": "Left",
}


def _range(ranges: dict[str, list[int]], key: str) -> RangeOut:
    lo, hi = ranges.get(key, [1, 20])
    return RangeOut(min=lo, max=hi)


def former_profile(
    session: Session, company_id: int, person_id: int, data: LoadedData
) -> FormerProfileOut:
    row = session.get(FormerStaffRow, person_id) if has_table(session, FormerStaffRow) else None
    if row is None or row.company_id != company_id:
        raise UnknownPersonError(f"no former employee {person_id}")
    person = session.get(PersonRow, person_id)
    assert person is not None
    know = row.knowledge
    ranges: dict[str, list[int]] = know.get("ranges", {})
    rival = session.get(CompanyRow, row.rival_id) if row.rival_id is not None else None
    reason = (
        f"Poached by {rival.name}"
        if row.reason == "poached" and rival is not None
        else "Poached by a rival"
        if row.reason == "poached"
        else REASONS.get(row.reason, row.reason.replace("_", " ").capitalize())
    )
    pa_lo, pa_hi = ranges.get(PA_KEY, [0, 200])
    tags = {t.key: t for t in data.game_data.tags}
    history = timeline(session, company_id, data, person_id=person_id, limit=HISTORY_LIMIT)
    return FormerProfileOut(
        person_id=person_id,
        name=f"{person.first_name} {person.last_name}",
        role=row.role,
        role_label=role_label(row.role, data) or row.role,
        level=row.level,
        unit_name=row.unit_name,
        start_turn=row.start_turn,
        start_date_label=format_turn(row.start_turn),
        end_turn=row.end_turn,
        end_date_label=format_turn(row.end_turn),
        tenure_months=max(0, row.end_turn - row.start_turn),
        reason=row.reason,
        reason_label=reason,
        rival_id=row.rival_id,
        rival_name=rival.name if rival is not None else None,
        potential_phrase=potential_phrase(pa_lo, pa_hi, data.balance.reveal.pa_phrase_bounds),
        skills=[
            AttributeOut(
                key=s.key,
                label=s.label,
                short_label=s.short_label,
                group=s.group,
                range=_range(ranges, s.key),
            )
            for s in data.game_data.skills
        ],
        personality=[
            AttributeOut(
                key=t.key,
                label=t.label,
                short_label=t.label,
                group=PERSONALITY_GROUP,
                range=_range(ranges, t.key),
            )
            for t in data.game_data.personality
        ],
        noticed_tags=[
            TagOut(
                key=key,
                label=tags[key].label,
                text=tags[key].reveal_text,
                noticed_turn=turn,
                noticed_date_label=format_turn(turn),
            )
            for key, turn in know.get("tags", [])
            if key in tags
        ],
        interests=know.get("interests"),
        work_style=know.get("work_style"),
        history=[e for e in history.rows if e.kind != "month"],
        job_history=job_history(session, row, person, data),
        led=led(session, row, data),
    )


# --- Job history and what they led (23.6, M10b) ----------------------------------------------


def _log(session: Session, company_id: int, start: int, end: int) -> list[DecisionLogRow]:
    """The company's actions from `start` to `end` (inclusive), in the order they were taken."""
    return list(
        session.scalars(
            select(DecisionLogRow)
            .where(
                DecisionLogRow.company_id == company_id,
                DecisionLogRow.turn >= start,
                DecisionLogRow.turn <= end,
            )
            .order_by(DecisionLogRow.turn, DecisionLogRow.seq, DecisionLogRow.id)
        )
    )


def _unit_name(session: Session, unit_id: int | None) -> str | None:
    if unit_id is None:
        return None
    unit = session.get(OrgUnitRow, unit_id)
    return unit.name if unit is not None else None


def _period(
    role: str, level: str, unit: str | None, start: int, end: int, data: LoadedData
) -> JobPeriodOut:
    return JobPeriodOut(
        role_label=role_label(role, data) or role,
        level=level,
        unit_name=unit,
        from_label=format_turn(start),
        to_label=format_turn(end),
        months=max(0, end - start),
    )


def job_history(
    session: Session, row: FormerStaffRow, person: PersonRow, data: LoadedData
) -> list[JobPeriodOut]:
    """From the hire (the candidate's level, the offer's unit) forward through promotions,
    moves and appointments in the decision log, to the month they left."""
    pid = row.person_id
    offer = session.scalars(
        select(OfferRow)
        .where(
            OfferRow.company_id == row.company_id,
            OfferRow.candidate_id == pid,
            OfferRow.status == "accepted",
        )
        .order_by(OfferRow.id.desc())
    ).first()
    level = person.level or row.level
    unit_id = offer.unit_id if offer is not None else None
    unit = _unit_name(session, unit_id)
    start = row.start_turn
    out: list[JobPeriodOut] = []
    for entry in _log(session, row.company_id, row.start_turn, row.end_turn):
        payload = entry.payload
        if payload.get("person_id") != pid:
            continue
        new_level, new_unit = level, unit
        if entry.kind == "promote":
            new_level = next_level(level) or level
        elif entry.kind == "appoint_executive":
            new_level = EXEC_LEVEL
        elif entry.kind == "move_person":
            new_unit = _unit_name(session, payload.get("unit_id"))
        else:
            continue
        if (new_level, new_unit) == (level, unit):
            continue
        if entry.turn > start:
            out.append(_period(row.role, level, unit, start, entry.turn, data))
        start, level, unit = max(start, entry.turn), new_level, new_unit
    out.append(_period(row.role, row.level, row.unit_name, start, row.end_turn, data))
    return out


def led(session: Session, row: FormerStaffRow, data: LoadedData) -> list[LedOut]:
    """Units they led, seats they held, products their unit worked on while they were in it,
    and the storylines they were in."""
    pid = row.person_id
    end = row.end_turn
    leading: dict[int, int] = {}  # unit id -> since
    seats: dict[str, int] = {}
    units_of_product: dict[int | None, int] = {}  # unit id -> product id (assign_unit)
    offer = session.scalars(
        select(OfferRow)
        .where(OfferRow.candidate_id == pid, OfferRow.status == "accepted")
        .order_by(OfferRow.id.desc())
    ).first()
    in_unit: int | None = offer.unit_id if offer is not None else None
    built: dict[int, list[int]] = {}  # product id -> [from, to]
    out: list[LedOut] = []

    def item(kind: str, name: str, start: int, stop: int) -> LedOut:
        return LedOut(
            kind=kind,
            name=name,
            from_label=format_turn(start),
            to_label=format_turn(stop),
            months=max(0, stop - start),
        )

    def note_product(turn: int) -> None:
        product = units_of_product.get(in_unit)
        if product is not None:
            span = built.setdefault(product, [turn, turn])
            span[1] = max(span[1], turn)

    for entry in _log(session, row.company_id, 0, end):
        p = entry.payload
        during = entry.turn >= row.start_turn
        if entry.kind == "assign_unit":
            units_of_product[p.get("unit_id")] = int(p["product_id"])
        elif entry.kind == "move_person" and p.get("person_id") == pid:
            note_product(entry.turn)
            in_unit = p.get("unit_id")
        elif entry.kind == "set_leader" and during:
            unit = int(p["unit_id"])
            if p.get("person_id") == pid:
                leading[unit] = entry.turn
            elif unit in leading:
                since = leading.pop(unit)
                out.append(item("unit", _unit_name(session, unit) or "a unit", since, entry.turn))
        elif entry.kind == "appoint_executive" and during:
            seat = p.get("seat", "")
            if p.get("person_id") == pid:
                seats[seat] = entry.turn
            elif seat in seats:
                out.append(item("seat", seat.upper(), seats.pop(seat), entry.turn))
        elif entry.kind == "remove_executive" and p.get("seat") in seats:
            seat = p["seat"]
            out.append(item("seat", seat.upper(), seats.pop(seat), entry.turn))
        if during:
            note_product(entry.turn)
    note_product(end)
    for unit, since in leading.items():
        out.append(item("unit", _unit_name(session, unit) or "a unit", since, end))
    for seat, since in seats.items():
        out.append(item("seat", seat.upper(), since, end))
    for product_id, (start, stop) in sorted(built.items()):
        product = session.get(ProductRow, product_id)
        if product is not None:
            out.append(item("product", product.name, max(start, row.start_turn), stop))
    if has_table(session, StorylineRow):
        for story in session.scalars(
            select(StorylineRow)
            .where(StorylineRow.company_id == row.company_id)
            .order_by(StorylineRow.id)
        ):
            if pid in (story.person_ids or []):
                stop = story.ended_turn if story.ended_turn is not None else end
                out.append(item("storyline", story.title, story.started_turn, stop))
    return out
