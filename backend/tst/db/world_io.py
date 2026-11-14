"""Loading and syncing M28's records (formulas.md 41; migration 0049). Every collection lives
in `world_record`, one row a record (`kind` = the GameState field), its fields in `data`
(tst.db.mna_io's encoding); a changed collection is rewritten whole (they are small: a few
hundred rows at most)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import WorldRecordRow
from tst.sim.state import GameState
from tst.sim.world.models import (
    ChainCompany,
    ChinaLag,
    RegionCycle,
    RivalDeal,
    RivalMandate,
    WorldBid,
    WorldFacility,
    WorldGood,
    WorldNews,
    WorldOfftake,
)

COLLECTIONS: Final[dict[str, type]] = {
    "chain_companies": ChainCompany,
    "world_facilities": WorldFacility,
    "world_goods": WorldGood,
    "region_cycles": RegionCycle,
    "world_news": WorldNews,
    "rival_deals": RivalDeal,
    "rival_mandates": RivalMandate,
    "world_offtakes": WorldOfftake,
    "world_bids": WorldBid,
    "china_lags": ChinaLag,
}
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def load_world(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every living-world record (0049); a save from before M28 has none."""
    if not has_table(session, WorldRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in COLLECTIONS}
    for row in session.scalars(select(WorldRecordRow).order_by(WorldRecordRow.n)):
        cls = COLLECTIONS.get(row.kind)
        if cls is not None:
            found[row.kind].append(from_data(cls, row.data))
    for kind, items in found.items():
        state = replace(state, **{kind: tuple(items)})  # type: ignore[arg-type]
    return state


def sync_world(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, WorldRecordRow):
        return
    for i, kind in enumerate(COLLECTIONS):
        before, after = getattr(old, kind), getattr(new, kind)
        if before == after:
            continue
        session.execute(delete(WorldRecordRow).where(WorldRecordRow.kind == kind))
        if after:
            session.execute(
                insert(WorldRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": to_data(x)}
                    for j, x in enumerate(after)
                ],
            )
