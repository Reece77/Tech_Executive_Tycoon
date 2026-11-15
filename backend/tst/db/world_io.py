"""Loading and syncing M28's records (formulas.md 41; migration 0050). Every collection lives
in `world_record`, one row a record (`kind` = the GameState field), its fields in `data`
(tst.db.mna_io's encoding). A changed collection writes only what changed (M30): items dropped
from its front and its changed tail, so World news no longer rewrites its whole window a month."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, func, insert, select
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
    """Every living-world record (0050); a save from before M28 has none."""
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
        if before is after or before == after:
            continue
        _write_changes(session, kind, i * STRIDE, before, after)


def _write_changes(
    session: Session, kind: str, base: int, before: tuple[Any, ...], after: tuple[Any, ...]
) -> None:
    """Write only what changed (M30). A collection's rows are numbered `base` + offset +
    position, and load reads them in `n` order, so numbers need not start at `base`: items
    dropped from the front (World news past its window) are deleted, the run both share
    keeps its rows, and only the changed tail is rewritten."""
    first = session.scalar(
        select(func.min(WorldRecordRow.n)).where(
            WorldRecordRow.n >= base, WorldRecordRow.n < base + STRIDE
        )
    )
    offset = 0 if first is None else first - base
    dropped = _dropped(before, after)
    same = _common_prefix(before[dropped:], after)
    start = offset + dropped + same  # the first position rewritten
    if start + len(after) - same >= STRIDE:  # out of numbers: renumber from the start
        offset, dropped, same, start = 0, 0, 0, 0
        session.execute(
            delete(WorldRecordRow).where(WorldRecordRow.n >= base, WorldRecordRow.n < base + STRIDE)
        )
    else:
        if dropped:
            session.execute(
                delete(WorldRecordRow).where(
                    WorldRecordRow.n >= base, WorldRecordRow.n < base + offset + dropped
                )
            )
        session.execute(
            delete(WorldRecordRow).where(
                WorldRecordRow.n >= base + start, WorldRecordRow.n < base + STRIDE
            )
        )
    if len(after) > same:
        session.execute(
            insert(WorldRecordRow),
            [
                {"n": base + start + j, "kind": kind, "data": to_data(after[same + j])}
                for j in range(len(after) - same)
            ],
        )


def _dropped(before: tuple[Any, ...], after: tuple[Any, ...]) -> int:
    """How many of `before`'s leading items `after` dropped, when the rest of `before` starts
    `after` (a window moving on); else 0."""
    if not before or not after or before[0] is after[0]:
        return 0
    first = after[0]
    for d in range(1, len(before)):
        if before[d] is first:
            return d if _common_prefix(before[d:], after) == len(before) - d else 0
    return len(before) if not _common_prefix(before, after) else 0


def _common_prefix(before: tuple[Any, ...], after: tuple[Any, ...]) -> int:
    """How many leading items `before` and `after` share."""
    n = min(len(before), len(after))
    k = 0
    while k < n and (before[k] is after[k] or before[k] == after[k]):
        k += 1
    return k
