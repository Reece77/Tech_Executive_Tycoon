"""The "Former employee" profile (M7c): read-only, built from `former_staff` (what the player
knew at departure) and the History timeline. Never a true value (ADR-0007)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from tst.api.history_views import timeline
from tst.api.schemas.people import AttributeOut, FormerProfileOut, RangeOut, TagOut
from tst.api.views import role_label
from tst.db.models import CompanyRow, FormerStaffRow, PersonRow
from tst.db.state_io import has_table
from tst.loader import LoadedData
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
    )
