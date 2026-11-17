"""Loading and syncing M41's records (formulas.md 50; migration 0058). Every collection lives in
`medical_record`, one row a record (`kind` = the GameState field), its fields in `data`
(tst.db.mna_io's encoding); a changed collection is rewritten whole."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import MedicalRecordRow
from tst.sim.medical.models import (
    Adoption,
    Clearance,
    Coverage,
    Design,
    Drift,
    Inspection,
    PlantQuality,
    Recall,
    Study,
    Submission,
)
from tst.sim.state import GameState

COLLECTIONS: Final[dict[str, type]] = {
    "med_designs": Design,
    "med_submissions": Submission,
    "med_clearances": Clearance,
    "med_studies": Study,
    "med_coverage": Coverage,
    "med_adoption": Adoption,
    "plant_quality": PlantQuality,
    "med_inspections": Inspection,
    "med_recalls": Recall,
    "med_drift": Drift,
}
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def load_medical(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every medical record (0058); a save from before M41 has none."""
    if not has_table(session, MedicalRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in COLLECTIONS}
    for row in session.scalars(select(MedicalRecordRow).order_by(MedicalRecordRow.n)):
        cls = COLLECTIONS.get(row.kind)
        if cls is not None:
            found[row.kind].append(from_data(cls, row.data))
    for kind, items in found.items():
        state = replace(state, **{kind: tuple(items)})  # type: ignore[arg-type]
    return state


def sync_medical(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, MedicalRecordRow):
        return
    for i, kind in enumerate(COLLECTIONS):
        before, after = getattr(old, kind), getattr(new, kind)
        if before == after:
            continue
        session.execute(delete(MedicalRecordRow).where(MedicalRecordRow.kind == kind))
        if after:
            session.execute(
                insert(MedicalRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": to_data(x)}
                    for j, x in enumerate(after)
                ],
            )
