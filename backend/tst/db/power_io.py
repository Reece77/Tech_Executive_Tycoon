"""Loading and syncing M32's records (formulas.md 46; migration 0055_m32). Every collection lives
in `power_record`, one row a record (`kind` = the GameState field), its fields in `data`; a
changed collection is rewritten whole. A plant's month is nested as a dict; the game-wide draws
(`power_world`) are one row."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import PowerRecordRow
from tst.sim.power.models import (
    GridOutage,
    Plant,
    PlantMonth,
    PowerMonth,
    PowerWorld,
    Ppa,
    QueueEntry,
    RegionPath,
)
from tst.sim.state import GameState

COLLECTIONS: Final[dict[str, type]] = {
    "plants": Plant,
    "ppas": Ppa,
    "grid_queue": QueueEntry,
    "power_months": PowerMonth,
    "grid_outages": GridOutage,
    "region_paths": RegionPath,
}
WORLD: Final = "power_world"
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def _encode(record: Any) -> dict[str, Any]:
    data = to_data(record, skip=("month",) if isinstance(record, Plant) else ())
    if isinstance(record, Plant):
        data["month"] = to_data(record.month) if record.month is not None else None
    if isinstance(record, PowerWorld):
        data["learning"] = [list(x) for x in record.learning]
        data["revenue_marks"] = [list(x) for x in record.revenue_marks]
        data["brand"] = [list(x) for x in record.brand]
    return data


def _decode(kind: str, data: dict[str, Any]) -> Any:
    if kind == WORLD:
        return PowerWorld(
            learning=tuple((str(k), float(v)) for k, v in data.get("learning", [])),
            smr_year=data.get("smr_year"),
            unlocked=tuple(int(x) for x in data.get("unlocked", [])),
            revenue_marks=tuple((int(c), int(v)) for c, v in data.get("revenue_marks", [])),
            brand=tuple((int(c), float(p), int(u)) for c, p, u in data.get("brand", [])),
        )
    cls = COLLECTIONS[kind]
    if cls is Plant:
        month = data.get("month")
        rest = {k: v for k, v in data.items() if k != "month"}
        plant = from_data(Plant, rest)
        names = {f.name for f in fields(PlantMonth)}
        pm = PlantMonth(**{k: v for k, v in month.items() if k in names}) if month else None
        return replace(plant, month=pm)
    return from_data(cls, data)


def load_power(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every power record (0055_m32); a save from before M32 has none."""
    if not has_table(session, PowerRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in COLLECTIONS}
    world: PowerWorld | None = None
    for row in session.scalars(select(PowerRecordRow).order_by(PowerRecordRow.n)):
        if row.kind == WORLD:
            world = _decode(WORLD, row.data)
        elif row.kind in COLLECTIONS:
            found[row.kind].append(_decode(row.kind, row.data))
    for kind, items in found.items():
        state = replace(state, **{kind: tuple(items)})  # type: ignore[arg-type]
    if world is not None:
        state = replace(state, power_world=world)
    return state


def sync_power(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, PowerRecordRow):
        return
    for i, kind in enumerate((*COLLECTIONS, WORLD)):
        before, after = getattr(old, kind), getattr(new, kind)
        if before == after:
            continue
        session.execute(delete(PowerRecordRow).where(PowerRecordRow.kind == kind))
        items = [after] if kind == WORLD else list(after)
        if items:
            session.execute(
                insert(PowerRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": _encode(x)}
                    for j, x in enumerate(items)
                ],
            )
