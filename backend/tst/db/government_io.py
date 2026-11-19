"""Loading and syncing M44's records (formulas.md 57; migration 0064_m44). Every collection lives
in `government_record`, one row a record (`kind` = the GameState field), its fields in `data`; a
changed collection is rewritten whole. Nested records (a bid's score terms, a contract's month)
and the game-wide `government_world` (one row) are encoded field by field."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import GovernmentRecordRow
from tst.sim.government.models import (
    Bid,
    Clearance,
    Contract,
    ContractMonth,
    ControlledProduct,
    DefenceRecord,
    FacilityClearance,
    GovernmentWorld,
    Protest,
    ScoreTerms,
    Tender,
)
from tst.sim.state import GameState

COLLECTIONS: Final[dict[str, type]] = {
    "tenders": Tender,
    "gov_bids": Bid,
    "protests": Protest,
    "gov_contracts": Contract,
    "clearances": Clearance,
    "facility_clearances": FacilityClearance,
    "controlled_products": ControlledProduct,
    "defence_records": DefenceRecord,
}
WORLD: Final = "government_world"
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def _encode(record: Any) -> dict[str, Any]:
    if isinstance(record, GovernmentWorld):
        data = to_data(record, skip=("growth",))
        data["growth"] = [list(x) for x in record.growth]
        return data
    if isinstance(record, Bid):
        data = to_data(record, skip=("terms",))
        data["terms"] = to_data(record.terms) if record.terms is not None else None
        return data
    if isinstance(record, Contract):
        data = to_data(record, skip=("month",))
        data["month"] = to_data(record.month) if record.month is not None else None
        return data
    if isinstance(record, DefenceRecord):
        data = to_data(record, skip=("brand_lost",))
        data["brand_lost"] = [list(x) for x in record.brand_lost]
        return data
    return to_data(record)


def _decode(kind: str, data: dict[str, Any]) -> Any:
    if kind == WORLD:
        rest = {k: v for k, v in data.items() if k != "growth"}
        return replace(
            from_data(GovernmentWorld, rest),
            growth=tuple((str(g), int(y), float(v)) for g, y, v in data.get("growth", [])),
        )
    cls = COLLECTIONS[kind]
    if cls is Bid:
        rest = {k: v for k, v in data.items() if k != "terms"}
        terms = data.get("terms")
        return replace(
            from_data(Bid, rest), terms=from_data(ScoreTerms, terms) if terms is not None else None
        )
    if cls is Contract:
        rest = {k: v for k, v in data.items() if k != "month"}
        month = data.get("month")
        return replace(
            from_data(Contract, rest),
            month=from_data(ContractMonth, month) if month is not None else None,
        )
    if cls is DefenceRecord:
        rest = {k: v for k, v in data.items() if k != "brand_lost"}
        return replace(
            from_data(DefenceRecord, rest),
            brand_lost=tuple((int(t), float(p)) for t, p in data.get("brand_lost", [])),
        )
    return from_data(cls, data)


def load_government(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every government record (0064_m44); a save from before M44 has none."""
    if not has_table(session, GovernmentRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in COLLECTIONS}
    world: GovernmentWorld | None = None
    for row in session.scalars(select(GovernmentRecordRow).order_by(GovernmentRecordRow.n)):
        if row.kind == WORLD:
            world = _decode(WORLD, row.data)
        elif row.kind in COLLECTIONS:
            found[row.kind].append(_decode(row.kind, row.data))
    for kind, items in found.items():
        state = replace(state, **{kind: tuple(items)})  # type: ignore[arg-type]
    if world is not None:
        state = replace(state, government_world=world)
    return state


def sync_government(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, GovernmentRecordRow):
        return
    for i, kind in enumerate((*COLLECTIONS, WORLD)):
        before, after = getattr(old, kind), getattr(new, kind)
        if before == after:
            continue
        session.execute(delete(GovernmentRecordRow).where(GovernmentRecordRow.kind == kind))
        items = [after] if kind == WORLD else list(after)
        if items:
            session.execute(
                insert(GovernmentRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": _encode(x)}
                    for j, x in enumerate(items)
                ],
            )
