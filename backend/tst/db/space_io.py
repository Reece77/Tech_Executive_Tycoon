"""Loading and syncing M40's records (formulas.md 56; migration 0063_m40). Every collection of
`GameState.space` lives in `space_record`, one row a record (`kind` = the SpaceState field), its
fields in `data`; a changed collection is rewritten whole. A constellation's cohorts and month, and
the game-wide `space_world` (one row), are encoded field by field."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import SpaceRecordRow
from tst.sim.space.models import (
    Cohort,
    Constellation,
    ConstellationMonth,
    LaunchRecord,
    LaunchSpec,
    Licence,
    SpaceState,
    SpaceWorld,
)
from tst.sim.state import GameState

COLLECTIONS: Final[dict[str, type]] = {
    "launch_specs": LaunchSpec,
    "constellations": Constellation,
    "licences": Licence,
    "launches": LaunchRecord,
    "months": ConstellationMonth,
}
PAIRS: Final = ("reuse_started", "terminal_prices", "d2d_partners")
WORLD: Final = "space_world"
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def _month(data: dict[str, Any]) -> ConstellationMonth:
    rest = {k: v for k, v in data.items() if k != "covered"}
    return from_data(
        ConstellationMonth, rest, covered=tuple(str(r) for r in data.get("covered", []))
    )


def _encode(record: Any) -> dict[str, Any]:
    if isinstance(record, SpaceWorld):
        return {
            "growth": [list(x) for x in record.growth],
            "debris_turn": record.debris_turn,
            "terminals": record.terminals,
        }
    if isinstance(record, Constellation):
        data = to_data(record, skip=("cohorts", "month"))
        data["cohorts"] = [to_data(c) for c in record.cohorts]
        data["month"] = to_data(record.month) if record.month is not None else None
        return data
    if isinstance(record, tuple):
        return {"v": list(record)}
    if isinstance(record, int):
        return {"v": record}
    return to_data(record)


def _decode(kind: str, data: dict[str, Any]) -> Any:
    if kind == WORLD:
        return SpaceWorld(
            growth=tuple((int(y), float(g)) for y, g in data.get("growth", [])),
            debris_turn=data.get("debris_turn"),
            terminals=float(data.get("terminals", 0.0)),
        )
    if kind in ("terminal_prices", "reuse_started"):
        a, b = data["v"]
        return (int(a), int(b))
    if kind == "d2d_partners":
        return int(data["v"])
    if kind == "months":
        return _month(data)
    cls = COLLECTIONS[kind]
    if cls is Constellation:
        rest = {k: v for k, v in data.items() if k not in ("cohorts", "month")}
        month = data.get("month")
        return replace(
            from_data(Constellation, rest),
            cohorts=tuple(from_data(Cohort, c) for c in data.get("cohorts", [])),
            month=_month(month) if month is not None else None,
        )
    return from_data(cls, data)


def load_space(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every space record (0063_m40); a save from before M40 has none."""
    if not has_table(session, SpaceRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in (*COLLECTIONS, *PAIRS)}
    world: SpaceWorld | None = None
    for row in session.scalars(select(SpaceRecordRow).order_by(SpaceRecordRow.n)):
        if row.kind == WORLD:
            world = _decode(WORLD, row.data)
        elif row.kind in found:
            found[row.kind].append(_decode(row.kind, row.data))
    space = SpaceState(**{k: tuple(v) for k, v in found.items()})  # type: ignore[arg-type]
    if world is not None:
        space = replace(space, world=world)
    return replace(state, space=space)


def sync_space(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, SpaceRecordRow) or old.space == new.space:
        return
    for i, kind in enumerate((*COLLECTIONS, *PAIRS, WORLD)):
        attr = "world" if kind == WORLD else kind
        before, after = getattr(old.space, attr), getattr(new.space, attr)
        if before == after:
            continue
        session.execute(delete(SpaceRecordRow).where(SpaceRecordRow.kind == kind))
        items = [after] if kind == WORLD else list(after)
        if items:
            session.execute(
                insert(SpaceRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": _encode(x)}
                    for j, x in enumerate(items)
                ],
            )
