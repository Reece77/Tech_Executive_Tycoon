"""Loading and syncing M22's records (formulas.md 39; migration 0047). Every collection lives
in `geo_record`, one row a record (`kind` = the GameState field), its fields in `data`
(tst.db.mna_io's encoding); a changed collection is rewritten whole (they are small)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import GeoRecordRow
from tst.sim.contracts.models import FoundryContract, Relation
from tst.sim.geopolitics.models import (
    EntityListing,
    Exit,
    Licence,
    Notice,
    SeededRule,
    Site,
    Suspension,
    TensionMonth,
    Variant,
)
from tst.sim.state import GameState

COLLECTIONS: Final[dict[str, type]] = {
    "tension": TensionMonth,
    "seeded_rules": SeededRule,
    "suspensions": Suspension,
    "licences": Licence,
    "variants": Variant,
    "entity_listings": EntityListing,
    "sites": Site,
    "exits": Exit,
    "geo_notices": Notice,
    # M23a (no new table): counterparties' memory and foundry contracts, appended so existing
    # rows keep their numbers
    "relations": Relation,
    "foundry_contracts": FoundryContract,
}
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def load_geopolitics(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every geopolitical record (0047); a save from before M22 has none."""
    if not has_table(session, GeoRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in COLLECTIONS}
    for row in session.scalars(select(GeoRecordRow).order_by(GeoRecordRow.n)):
        cls = COLLECTIONS.get(row.kind)
        if cls is not None:
            found[row.kind].append(from_data(cls, row.data))
    for kind, items in found.items():
        state = replace(state, **{kind: tuple(items)})  # type: ignore[arg-type]
    return state


def sync_geopolitics(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, GeoRecordRow):
        return
    for i, kind in enumerate(COLLECTIONS):
        before, after = getattr(old, kind), getattr(new, kind)
        if before == after:
            continue
        session.execute(delete(GeoRecordRow).where(GeoRecordRow.kind == kind))
        if after:
            session.execute(
                insert(GeoRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": to_data(x)}
                    for j, x in enumerate(after)
                ],
            )
