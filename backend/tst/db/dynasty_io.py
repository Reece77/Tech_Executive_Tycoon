"""Loading and syncing M37's records (formulas.md 52; migration 0059_m37): one `dynasty_record`
row, rewritten whole when the dynasty state changes. A save before M37, or any game before
January 2040, has none."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import DynastyRecordRow
from tst.sim.dynasty.models import Death, DynastyState, LeaderChange, Relaunch
from tst.sim.state import GameState

KINDS: dict[str, type] = {"leader_changes": LeaderChange, "deaths": Death, "relaunches": Relaunch}


def load_dynasty(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    if not has_table(session, DynastyRecordRow):
        return state
    row = session.get(DynastyRecordRow, 1)
    if row is None:
        return state
    parts = {k: tuple(from_data(cls, d) for d in row.data.get(k, [])) for k, cls in KINDS.items()}
    return replace(state, dynasty=DynastyState(**parts))


def sync_dynasty(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if old.dynasty == new.dynasty or not has_table(session, DynastyRecordRow):
        return
    if new.dynasty is None:
        session.execute(delete(DynastyRecordRow))
        return
    data = {k: [to_data(r) for r in getattr(new.dynasty, k)] for k in KINDS}
    session.merge(DynastyRecordRow(id=1, data=data))
