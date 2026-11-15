"""Loading and syncing M33's records (formulas.md 47; migration 0055_m33). Every collection lives
in `equipment_record`, one row a record (`kind` = the GameState field), its fields in `data`
(tst.db.mna_io's encoding); a changed collection is rewritten whole."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import EquipmentRecordRow
from tst.sim.equipment.models import (
    Delivery,
    FabTools,
    OwnTools,
    Programme,
    SupplierYear,
    ToolOrder,
    ToolStock,
)
from tst.sim.state import GameState

COLLECTIONS: Final[dict[str, type]] = {
    "tool_orders": ToolOrder,
    "tool_deliveries": Delivery,
    "supplier_years": SupplierYear,
    "tool_stock": ToolStock,
    "programmes": Programme,
    "own_tools": OwnTools,
    "fab_tools": FabTools,
}
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def load_equipment(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every equipment record (0055_m33); a save from before M33 has none."""
    if not has_table(session, EquipmentRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in COLLECTIONS}
    for row in session.scalars(select(EquipmentRecordRow).order_by(EquipmentRecordRow.n)):
        cls = COLLECTIONS.get(row.kind)
        if cls is not None:
            found[row.kind].append(from_data(cls, row.data))
    for kind, items in found.items():
        state = replace(state, **{kind: tuple(items)})  # type: ignore[arg-type]
    return state


def sync_equipment(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, EquipmentRecordRow):
        return
    for i, kind in enumerate(COLLECTIONS):
        before, after = getattr(old, kind), getattr(new, kind)
        if before == after:
            continue
        session.execute(delete(EquipmentRecordRow).where(EquipmentRecordRow.kind == kind))
        if after:
            session.execute(
                insert(EquipmentRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": to_data(x)}
                    for j, x in enumerate(after)
                ],
            )
