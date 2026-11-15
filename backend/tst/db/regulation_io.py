"""Loading and syncing M34's records (formulas.md 48; migration 0055). Every collection lives in
`regulation_record`, one row a record (`kind` = the GameState field), its fields in `data`
(tst.db.mna_io's encoding); a changed collection is rewritten whole."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import RegulationRecordRow
from tst.sim.regulation.models import Case, Designation, DesignationWarning, Duty, Order, Watch
from tst.sim.state import GameState

COLLECTIONS: Final[dict[str, type]] = {
    "designations": Designation,
    "designation_warnings": DesignationWarning,
    "duties": Duty,
    "reg_cases": Case,
    "reg_watches": Watch,
    "reg_orders": Order,
}
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def load_regulation(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every regulation record (0055); a save from before M34 has none."""
    if not has_table(session, RegulationRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in COLLECTIONS}
    for row in session.scalars(select(RegulationRecordRow).order_by(RegulationRecordRow.n)):
        cls = COLLECTIONS.get(row.kind)
        if cls is not None:
            found[row.kind].append(from_data(cls, row.data))
    for kind, items in found.items():
        state = replace(state, **{kind: tuple(items)})  # type: ignore[arg-type]
    return state


def sync_regulation(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, RegulationRecordRow):
        return
    for i, kind in enumerate(COLLECTIONS):
        before, after = getattr(old, kind), getattr(new, kind)
        if before == after:
            continue
        session.execute(delete(RegulationRecordRow).where(RegulationRecordRow.kind == kind))
        if after:
            session.execute(
                insert(RegulationRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": to_data(x)}
                    for j, x in enumerate(after)
                ],
            )
