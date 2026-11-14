"""Loading and syncing M31's records (formulas.md 44; migration 0051). Every collection lives in
`platform_record`, one row a record (`kind` = the GameState field), its fields in `data`
(tst.db.mna_io's encoding); a changed collection is rewritten whole. The player's steering apps
(plain ids) are one row each with `{"product_id": id}`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import PlatformRecordRow
from tst.sim.platforms.models import (
    DeviceRun,
    OpenSource,
    Platform,
    PlatformListing,
    PlatformRegion,
    ProductStandard,
    Review,
    RivalStore,
    Standard,
)
from tst.sim.state import GameState

COLLECTIONS: Final[dict[str, type]] = {
    "platforms": Platform,
    "platform_regions": PlatformRegion,
    "device_runs": DeviceRun,
    "platform_listings": PlatformListing,
    "platform_reviews": Review,
    "open_sources": OpenSource,
    "standards": Standard,
    "product_standards": ProductStandard,
    "rival_stores": RivalStore,
}
STEERING: Final = "steering_products"
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def load_platforms(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every platform record (0051); a save from before M31 has none."""
    if not has_table(session, PlatformRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in (*COLLECTIONS, STEERING)}
    for row in session.scalars(select(PlatformRecordRow).order_by(PlatformRecordRow.n)):
        if row.kind == STEERING:
            found[STEERING].append(int(row.data["product_id"]))
            continue
        cls = COLLECTIONS.get(row.kind)
        if cls is not None:
            found[row.kind].append(from_data(cls, row.data))
    for kind, items in found.items():
        state = replace(state, **{kind: tuple(items)})  # type: ignore[arg-type]
    return state


def sync_platforms(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, PlatformRecordRow):
        return
    for i, kind in enumerate((*COLLECTIONS, STEERING)):
        before, after = getattr(old, kind), getattr(new, kind)
        if before == after:
            continue
        session.execute(delete(PlatformRecordRow).where(PlatformRecordRow.kind == kind))
        if after:
            session.execute(
                insert(PlatformRecordRow),
                [
                    {
                        "n": i * STRIDE + j,
                        "kind": kind,
                        "data": {"product_id": x} if kind == STEERING else to_data(x),
                    }
                    for j, x in enumerate(after)
                ],
            )
