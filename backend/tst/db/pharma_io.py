"""Loading and syncing M42's records (formulas.md 55; migration 0062). Every collection lives in
`pharma_record`, one row a record (`kind` = the GameState field), its fields in `data`
(tst.db.mna_io's encoding); a changed collection is rewritten whole."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import PharmaRecordRow
from tst.sim.pharma import models as m
from tst.sim.state import GameState

COLLECTIONS: Final[dict[str, type]] = {
    "pharma_programmes": m.Programme,
    "pharma_readouts": m.Readout,
    "pharma_reviews": m.Review,
    "pharma_authorisations": m.Authorisation,
    "pharma_drugs": m.Drug,
    "pharma_hta": m.Hta,
    "pharma_months": m.DrugMonth,
    "pharma_seeded": m.SeededDrug,
    "pharma_rules": m.Rule,
    "pharma_ira": m.IraPick,
    "pharma_plants": m.Plant,
    "pharma_supply": m.Supply,
    "pharma_inspections": m.Inspection,
    "pharma_recalls": m.Recall,
    "pharma_assets": m.Asset,
    "pharma_deals": m.Deal,
}
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def load_pharma(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every pharma record (0062); a save from before M42 has none."""
    if not has_table(session, PharmaRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in COLLECTIONS}
    for row in session.scalars(select(PharmaRecordRow).order_by(PharmaRecordRow.n)):
        cls = COLLECTIONS.get(row.kind)
        if cls is not None:
            found[row.kind].append(from_data(cls, row.data))
    for kind, items in found.items():
        state = replace(state, **{kind: tuple(items)})  # type: ignore[arg-type]
    return state


def sync_pharma(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, PharmaRecordRow):
        return
    for i, kind in enumerate(COLLECTIONS):
        before, after = getattr(old, kind), getattr(new, kind)
        if before == after:
            continue
        session.execute(delete(PharmaRecordRow).where(PharmaRecordRow.kind == kind))
        if after:
            session.execute(
                insert(PharmaRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": to_data(x)}
                    for j, x in enumerate(after)
                ],
            )
