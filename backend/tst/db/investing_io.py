"""Loading and syncing M26's records (formulas.md 37; migration 0043): startups' rounds,
angel stakes, trades, public holdings, family offices, net-worth history and the market
index, each kept as JSON. Hidden fields (a trade's regulatory risk and investigation draw, a
concealed conflict's discovery) are stored with their record; the API never reads them."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import replace
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tst.db.mna_io import from_data, to_data
from tst.db.models import (
    AngelStakeRow,
    FamilyOfficeRow,
    MarketIndexRow,
    PersonalTradeRow,
    PublicHoldingRow,
    StartupRoundRow,
    WealthPointRow,
)
from tst.sim.founder.investing_models import (
    AngelStake,
    FamilyOffice,
    IndexPoint,
    PersonalTrade,
    PublicHolding,
    StartupRound,
    WealthPoint,
)
from tst.sim.state import GameState

# (state field, row class, record class, key columns)
TABLES: tuple[tuple[str, Any, Any, tuple[str, ...]], ...] = (
    ("startup_rounds", StartupRoundRow, StartupRound, ("id",)),
    ("angel_stakes", AngelStakeRow, AngelStake, ("id",)),
    ("personal_trades", PersonalTradeRow, PersonalTrade, ("id",)),
    ("public_holdings", PublicHoldingRow, PublicHolding, ("person_id", "company_id")),
    ("family_offices", FamilyOfficeRow, FamilyOffice, ("person_id",)),
    ("wealth_points", WealthPointRow, WealthPoint, ("person_id", "turn")),
    ("market_index", MarketIndexRow, IndexPoint, ("turn",)),
)


def _key(record: Any, keys: tuple[str, ...]) -> Hashable:
    return tuple(getattr(record, k) for k in keys)


def load_investing(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every M26 record; a save from before M26 has none."""
    if not has_table(session, StartupRoundRow):
        return state
    loaded: dict[str, tuple[Any, ...]] = {}
    for name, row_cls, cls, keys in TABLES:
        order = [getattr(row_cls, k) for k in keys]
        loaded[name] = tuple(
            from_data(cls, r.data, **{k: getattr(r, k) for k in keys})
            for r in session.scalars(select(row_cls).order_by(*order))
        )
    return replace(state, **loaded)


def sync_investing(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    changed = [t for t in TABLES if getattr(old, t[0]) != getattr(new, t[0])]
    if not changed or not has_table(session, StartupRoundRow):
        return
    for name, row_cls, _, keys in changed:
        before = {_key(r, keys): r for r in getattr(old, name)}
        after = {_key(r, keys): r for r in getattr(new, name)}
        for k in before.keys() - after.keys():  # the index keeps its last months only
            cond = [getattr(row_cls, c) == v for c, v in zip(keys, k, strict=True)]  # type: ignore[arg-type]
            session.execute(delete(row_cls).where(*cond))
        for k, record in after.items():
            if before.get(k) != record:
                session.merge(
                    row_cls(**{c: getattr(record, c) for c in keys}, data=to_data(record, keys))
                )
