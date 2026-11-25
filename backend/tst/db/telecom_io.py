"""Loading and syncing M53's records (formulas.md 62; migration 0067_m53). Every collection of
`GameState.telecom` lives in `telecom_record`, one row a record (`kind` = the TelecomState field),
its fields in `data`; a changed collection is rewritten whole. An auction's awards and the
game-wide `telecom_world` (one row) are encoded field by field."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import TelecomRecordRow
from tst.sim.state import GameState
from tst.sim.telecom.models import (
    Auction,
    Award,
    FibreNetwork,
    LineSetting,
    NetworkMonth,
    RadioNetwork,
    SeededBan,
    SpectrumLicence,
    SubseaCable,
    TelecomState,
    TelecomWorld,
)

COLLECTIONS: Final[dict[str, type]] = {
    "radios": RadioNetwork,
    "fibres": FibreNetwork,
    "cables": SubseaCable,
    "licences": SpectrumLicence,
    "auctions": Auction,
    "settings": LineSetting,
    "months": NetworkMonth,
}
TUPLES: Final = ("cash", "paid_back")
WORLD: Final = "telecom_world"
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def _encode(record: Any) -> dict[str, Any]:
    if isinstance(record, TelecomWorld):
        return {
            "g6_turn": record.g6_turn,
            "growth": [list(x) for x in record.growth],
            "next_auction": [list(x) for x in record.next_auction],
            "bans": [to_data(b) for b in record.bans],
        }
    if isinstance(record, Auction):
        data = to_data(record, skip=("awards",))
        data["awards"] = [to_data(a) for a in record.awards]
        return data
    if isinstance(record, tuple):
        return {"v": list(record)}
    return to_data(record)


def _decode(kind: str, data: dict[str, Any]) -> Any:
    if kind == WORLD:
        return TelecomWorld(
            g6_turn=data.get("g6_turn"),
            growth=tuple((int(y), int(r), float(g)) for y, r, g in data.get("growth", [])),
            next_auction=tuple((str(a), int(t)) for a, t in data.get("next_auction", [])),
            bans=tuple(from_data(SeededBan, b) for b in data.get("bans", [])),
        )
    if kind == "cash":
        c, r, v, capex = data["v"]
        return (int(c), str(r), int(v), int(capex))
    if kind == "paid_back":
        c, r, t = data["v"]
        return (int(c), str(r), int(t))
    cls = COLLECTIONS[kind]
    if cls is Auction:
        rest = {k: v for k, v in data.items() if k != "awards"}
        return replace(
            from_data(Auction, rest),
            awards=tuple(from_data(Award, a) for a in data.get("awards", [])),
        )
    return from_data(cls, data)


def load_telecom(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every telecom record (0067_m53); a save from before M53 has none."""
    if not has_table(session, TelecomRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in (*COLLECTIONS, *TUPLES)}
    world: TelecomWorld | None = None
    for row in session.scalars(select(TelecomRecordRow).order_by(TelecomRecordRow.n)):
        if row.kind == WORLD:
            world = _decode(WORLD, row.data)
        elif row.kind in found:
            found[row.kind].append(_decode(row.kind, row.data))
    telecom = TelecomState(**{k: tuple(v) for k, v in found.items()})  # type: ignore[arg-type]
    if world is not None:
        telecom = replace(telecom, world=world)
    return replace(state, telecom=telecom)


def sync_telecom(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, TelecomRecordRow) or old.telecom == new.telecom:
        return
    for i, kind in enumerate((*COLLECTIONS, *TUPLES, WORLD)):
        attr = "world" if kind == WORLD else kind
        before, after = getattr(old.telecom, attr), getattr(new.telecom, attr)
        if before == after:
            continue
        session.execute(delete(TelecomRecordRow).where(TelecomRecordRow.kind == kind))
        items = [after] if kind == WORLD else list(after)
        if items:
            session.execute(
                insert(TelecomRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": kind, "data": _encode(x)}
                    for j, x in enumerate(items)
                ],
            )
