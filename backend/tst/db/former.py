"""Former staff (M7c): what the player knew of an employee when they left, frozen at
departure. Written by `sync_state` when one of the player's employments ends; read by the
"Former employee" profile. Only displayed ranges and noticed tags are kept (ADR-0007)."""

from __future__ import annotations

from typing import Any

from tst.db.models import FormerStaffRow
from tst.sim.people.models import Employment, Person, RevealState
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState


def knowledge_snapshot(person: Person, reveal: RevealState) -> dict[str, Any]:
    """Displayed ranges of every attribute the observer tracks, noticed tags, and the
    interests and work style once the profile was revealed."""
    profile = reveal.profile_revealed_turn is not None
    return {
        "ranges": {
            attr: list(revealed_range(person, reveal, attr)) for attr, _ in reveal.attributes
        },
        "tags": [[tag, turn] for tag, turn in reveal.revealed_tags],
        "interests": list(person.interests) if profile else None,
        "work_style": person.work_style if profile else None,
    }


def former_row(before: GameState, after: GameState, ended: Employment) -> FormerStaffRow | None:
    """The snapshot for an employment that ended between `before` and `after`."""
    try:
        person = before.person(ended.person_id)
    except KeyError:
        return None
    reveal = before.reveal(ended.company_id, person.id)
    if reveal is None or person.is_founder:
        return None
    unit = before.unit(ended.unit_id) if ended.unit_id is not None else None
    rival = after.employment_of(person.id)
    rival_id = (
        rival.company_id if rival is not None and rival.company_id != ended.company_id else None
    )
    return FormerStaffRow(
        person_id=person.id,
        company_id=ended.company_id,
        employment_id=ended.id,
        role=ended.role,
        level=ended.level,
        unit_name=unit.name if unit is not None else None,
        start_turn=ended.start_turn,
        end_turn=ended.end_turn if ended.end_turn is not None else after.turn,
        reason=ended.end_reason or "left",
        rival_id=rival_id,
        knowledge=knowledge_snapshot(person, reveal),
    )


def former_rows(before: GameState, after: GameState) -> list[FormerStaffRow]:
    """Snapshots for the player's employments that were on staff in `before` and have
    ended in `after`."""
    if not before.companies:
        return []
    player = after.player.id
    was = {e.id: e for e in before.employments if e.company_id == player and e.counts_as_staff}
    rows = []
    for e in after.employments:
        if e.id in was and e.status == "ended":
            row = former_row(before, after, e)
            if row is not None:
                rows.append(row)
    return rows
