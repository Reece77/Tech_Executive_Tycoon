"""Loading and syncing M38's records (formulas.md 49; migration 0058_m38). Every collection lives
in `vehicle_record`, one row a record (`kind` = the GameState field), its fields in `data`; a
changed collection is rewritten whole. Nested months (a cell plant's or charging network's month
and history) and the game-wide `vehicle_world` (one row) are encoded field by field."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import VehicleRecordRow
from tst.sim.state import GameState
from tst.sim.vehicles.models import (
    CellLot,
    CellPlant,
    CellPlantMonth,
    ChargingMonth,
    ChargingNetwork,
    Incident,
    Suspension,
    VehicleMonth,
    VehicleSpec,
    VehicleWorld,
)

COLLECTIONS: Final[dict[str, type]] = {
    "vehicle_specs": VehicleSpec,
    "cell_plants": CellPlant,
    "charging_networks": ChargingNetwork,
    "cell_lots": CellLot,
    "vehicle_months": VehicleMonth,
    "incidents": Incident,
}
WORLD: Final = "vehicle_world"
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position
NESTED: Final = {CellPlant: CellPlantMonth, ChargingNetwork: ChargingMonth}


def _month(cls: type, raw: dict[str, Any] | None) -> Any:
    if raw is None:
        return None
    names = {f.name for f in fields(cls)}
    out = {k: v for k, v in raw.items() if k in names}
    if cls is CellPlantMonth and "inputs" in out:
        out["inputs"] = tuple((str(g), float(q)) for g, q in out["inputs"])
    return cls(**out)


def _encode(record: Any) -> dict[str, Any]:
    if isinstance(record, VehicleWorld):
        return {
            "logit": [list(x) for x in record.logit],
            "k": [list(x) for x in record.k],
            "learning_rate": record.learning_rate,
            "cumulative_gwh": record.cumulative_gwh,
            "base_cumulative_gwh": record.base_cumulative_gwh,
            "approved": [list(x) for x in record.approved],
            "suspensions": [to_data(s) for s in record.suspensions],
        }
    nested = NESTED.get(type(record))
    if nested is None:
        return to_data(record)
    data = to_data(record, skip=("month", "history"))
    data["month"] = to_data(record.month) if record.month is not None else None
    data["history"] = [to_data(m) for m in record.history]
    return data


def _decode(kind: str, data: dict[str, Any]) -> Any:
    if kind == WORLD:
        return VehicleWorld(
            logit=tuple((str(r), float(v)) for r, v in data.get("logit", [])),
            k=tuple((str(r), float(v)) for r, v in data.get("k", [])),
            learning_rate=data.get("learning_rate"),
            cumulative_gwh=float(data.get("cumulative_gwh", 0.0)),
            base_cumulative_gwh=float(data.get("base_cumulative_gwh", 0.0)),
            approved=tuple((str(r), str(lv), int(t)) for r, lv, t in data.get("approved", [])),
            suspensions=tuple(from_data(Suspension, s) for s in data.get("suspensions", [])),
        )
    cls = COLLECTIONS[kind]
    nested = NESTED.get(cls)
    if nested is None:
        record = from_data(cls, data)
        if cls is VehicleMonth:
            record = replace(
                record,
                subsidy_regions=tuple((str(r), bool(e)) for r, e in record.subsidy_regions),
            )
        return record
    rest = {k: v for k, v in data.items() if k not in ("month", "history")}
    record = from_data(cls, rest)
    return replace(
        record,
        month=_month(nested, data.get("month")),
        history=tuple(_month(nested, m) for m in data.get("history", [])),
    )


def load_vehicles(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every vehicle record (0058_m38); a save from before M38 has none."""
    if not has_table(session, VehicleRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in COLLECTIONS}
    world: VehicleWorld | None = None
    for row in session.scalars(select(VehicleRecordRow).order_by(VehicleRecordRow.n)):
        if row.kind == WORLD:
            world = _decode(WORLD, row.data)
        elif row.kind in COLLECTIONS:
            found[row.kind].append(_decode(row.kind, row.data))
    for kind, items in found.items():
        state = replace(state, **{kind: tuple(items)})  # type: ignore[arg-type]
    if world is not None:
        state = replace(state, vehicle_world=world)
    return state


def sync_vehicles(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, VehicleRecordRow):
        return
    for i, kind in enumerate((*COLLECTIONS, WORLD)):
        before, after = getattr(old, kind), getattr(new, kind)
        if before == after:
            continue
        session.execute(delete(VehicleRecordRow).where(VehicleRecordRow.kind == kind))
        items = [after] if kind == WORLD else list(after)
        if items:
            session.execute(
                insert(VehicleRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": _encode(x)}
                    for j, x in enumerate(items)
                ],
            )
