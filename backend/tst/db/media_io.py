"""Loading and syncing M55's records (formulas.md 65; migration 0068_m55). Every collection of
`GameState.media` lives in `media_record`, one row a record (`kind` = the MediaState field), its
fields in `data`; a changed collection is rewritten whole."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import MediaRecordRow
from tst.sim.media.models import (
    AdMonth,
    AdRef,
    CreativeLead,
    DivestLaw,
    LeadOffer,
    Licence,
    LineSetting,
    MediaState,
    PaidBack,
    RivalBonus,
    RivalFormat,
    ServiceMonth,
    Title,
    WorldDraw,
)
from tst.sim.state import GameState

COLLECTIONS: Final[dict[str, type]] = {
    "titles": Title,
    "leads": CreativeLead,
    "offers": LeadOffer,
    "settings": LineSetting,
    "licences": Licence,
    "laws": DivestLaw,
    "months": ServiceMonth,
    "ad_months": AdMonth,
    "draws": WorldDraw,
    "ad_refs": AdRef,
    "rival_formats": RivalFormat,
    "rival_bonus": RivalBonus,
    "paid_back": PaidBack,
}
STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position


def load_media(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every media record (0068_m55); a save from before M55 has none."""
    if not has_table(session, MediaRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in COLLECTIONS}
    for row in session.scalars(select(MediaRecordRow).order_by(MediaRecordRow.n)):
        if row.kind in found:
            found[row.kind].append(from_data(COLLECTIONS[row.kind], row.data))
    media = MediaState(**{k: tuple(v) for k, v in found.items()})
    return replace(state, media=media)


def sync_media(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, MediaRecordRow) or old.media == new.media:
        return
    for i, f in enumerate(fields(MediaState)):
        before, after = getattr(old.media, f.name), getattr(new.media, f.name)
        if before == after:
            continue
        session.execute(delete(MediaRecordRow).where(MediaRecordRow.kind == f.name))
        if after:
            session.execute(
                insert(MediaRecordRow),
                [
                    {"n": i * STRIDE + j, "kind": f.name, "data": to_data(x)}
                    for j, x in enumerate(after)
                ],
            )
