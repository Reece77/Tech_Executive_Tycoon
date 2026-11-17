"""Loading and syncing M39's records (formulas.md 53; migration 0061_m39). Every collection lives
in `robotics_record`, one row a record (`kind` = the GameState field), its fields in `data`; a
changed collection is rewritten whole. Nested months (a plant automation's month and history, a
zone's month) and the game-wide `robotics_world` (one row) are encoded field by field."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import RoboticsRecordRow
from tst.sim.robotics.models import (
    AutomationMonth,
    Depot,
    HumanoidSpec,
    PlantAutomation,
    RivalCity,
    RoboIncident,
    RoboticsWorld,
    Zone,
    ZoneMonth,
)
from tst.sim.state import GameState

COLLECTIONS: Final[dict[str, type]] = {
    "plant_automations": PlantAutomation,
    "humanoid_specs": HumanoidSpec,
    "zones": Zone,
    "depots": Depot,
    "zone_months": ZoneMonth,
    "robo_incidents": RoboIncident,
}
WORLD: Final = "robotics_world"
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def _encode(record: Any) -> dict[str, Any]:
    if isinstance(record, RoboticsWorld):
        return {
            "growth": [list(x) for x in record.growth],
            "adoption": [list(x) for x in record.adoption],
            "actuator_units": record.actuator_units,
            "home_turn": record.home_turn,
            "rival_cities": [to_data(c) for c in record.rival_cities],
        }
    if isinstance(record, PlantAutomation):
        data = to_data(record, skip=("month", "history"))
        data["month"] = to_data(record.month) if record.month is not None else None
        data["history"] = [to_data(m) for m in record.history]
        return data
    if isinstance(record, Zone):
        data = to_data(record, skip=("month",))
        data["month"] = to_data(record.month) if record.month is not None else None
        return data
    return to_data(record)


def _decode(kind: str, data: dict[str, Any]) -> Any:
    if kind == WORLD:
        return RoboticsWorld(
            growth=tuple((str(r), int(y), float(g)) for r, y, g in data.get("growth", [])),
            adoption=tuple((str(r), float(v)) for r, v in data.get("adoption", [])),
            actuator_units=float(data.get("actuator_units", 0.0)),
            home_turn=data.get("home_turn"),
            rival_cities=tuple(from_data(RivalCity, c) for c in data.get("rival_cities", [])),
        )
    cls = COLLECTIONS[kind]
    if cls is PlantAutomation:
        rest = {k: v for k, v in data.items() if k not in ("month", "history")}
        month = data.get("month")
        return replace(
            from_data(PlantAutomation, rest),
            month=from_data(AutomationMonth, month) if month is not None else None,
            history=tuple(from_data(AutomationMonth, m) for m in data.get("history", [])),
        )
    if cls is Zone:
        rest = {k: v for k, v in data.items() if k != "month"}
        month = data.get("month")
        return replace(
            from_data(Zone, rest),
            month=from_data(ZoneMonth, month) if month is not None else None,
        )
    return from_data(cls, data)


def load_robotics(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every robotics record (0061_m39); a save from before M39 has none."""
    if not has_table(session, RoboticsRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in COLLECTIONS}
    world: RoboticsWorld | None = None
    for row in session.scalars(select(RoboticsRecordRow).order_by(RoboticsRecordRow.n)):
        if row.kind == WORLD:
            world = _decode(WORLD, row.data)
        elif row.kind in COLLECTIONS:
            found[row.kind].append(_decode(row.kind, row.data))
    for kind, items in found.items():
        state = replace(state, **{kind: tuple(items)})  # type: ignore[arg-type]
    if world is not None:
        state = replace(state, robotics_world=world)
    return state


def sync_robotics(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, RoboticsRecordRow):
        return
    for i, kind in enumerate((*COLLECTIONS, WORLD)):
        before, after = getattr(old, kind), getattr(new, kind)
        if before == after:
            continue
        session.execute(delete(RoboticsRecordRow).where(RoboticsRecordRow.kind == kind))
        items = [after] if kind == WORLD else list(after)
        if items:
            session.execute(
                insert(RoboticsRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": _encode(x)}
                    for j, x in enumerate(items)
                ],
            )
