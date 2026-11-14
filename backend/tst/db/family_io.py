"""Loading and syncing M36's records (formulas.md 45; migration 0052): the family (one row)
and its members, each as JSON. The family's people are people in `person`; `family_people`
names them so the state loads them though most work nowhere."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import FamilyMemberRow, FamilyRow
from tst.sim.family.models import Family, FamilyMember, FamilyNote, Generation, Opinion
from tst.sim.state import GameState

NESTED: dict[str, Any] = {"generations": Generation, "opinions": Opinion, "notes": FamilyNote}


def _family_data(family: Family) -> dict[str, Any]:
    out = to_data(family, ("id", *NESTED))
    for key in NESTED:
        out[key] = [asdict(item) for item in getattr(family, key)]
    return out


def _family_from(row: FamilyRow) -> Family:
    data = dict(row.data)
    gens = tuple(Generation(**g) for g in data.pop("generations", []))
    opinions = tuple(Opinion(**o) for o in data.pop("opinions", []))
    notes = tuple(FamilyNote(**n) for n in data.pop("notes", []))
    family = from_data(Family, data, id=row.id)
    return replace(family, generations=gens, opinions=opinions, notes=notes)


def family_people(session: Session, has_table: Callable[[Session, Any], bool]) -> set[int]:
    """Person ids the family needs loaded: members, heads past and present, the adviser."""
    if not has_table(session, FamilyRow):
        return set()
    ids = set(session.scalars(select(FamilyMemberRow.person_id)))
    for row in session.scalars(select(FamilyRow)):
        family = _family_from(row)
        ids.add(family.head_id)
        ids.update(g.person_id for g in family.generations)
        if family.adviser_id is not None:
            ids.add(family.adviser_id)
    return ids


def live_family(state: GameState) -> set[int]:
    """`family_people` for a state in memory (state_io.live_view)."""
    family = state.family
    if family is None:
        return set()
    ids = {m.person_id for m in state.family_members}
    ids.add(family.head_id)
    ids.update(g.person_id for g in family.generations)
    if family.adviser_id is not None:
        ids.add(family.adviser_id)
    return ids


def load_family(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    if not has_table(session, FamilyRow):
        return state
    row = session.scalars(select(FamilyRow).order_by(FamilyRow.id)).first()
    members = tuple(
        from_data(FamilyMember, r.data, person_id=r.person_id)
        for r in session.scalars(select(FamilyMemberRow).order_by(FamilyMemberRow.person_id))
    )
    return replace(
        state, family=_family_from(row) if row is not None else None, family_members=members
    )


def sync_family(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if (old.family, old.family_members) == (new.family, new.family_members):
        return
    if not has_table(session, FamilyRow):
        return
    if new.family != old.family:
        if new.family is None:
            session.execute(delete(FamilyRow))
        else:
            session.merge(FamilyRow(id=new.family.id, data=_family_data(new.family)))
    if new.family_members != old.family_members:
        before = {m.person_id: m for m in old.family_members}
        for m in new.family_members:
            if before.get(m.person_id) != m:
                session.merge(
                    FamilyMemberRow(person_id=m.person_id, data=to_data(m, ("person_id",)))
                )
        gone = set(before) - {m.person_id for m in new.family_members}
        if gone:
            session.execute(delete(FamilyMemberRow).where(FamilyMemberRow.person_id.in_(gone)))
