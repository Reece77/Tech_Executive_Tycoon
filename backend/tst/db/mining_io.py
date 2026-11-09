"""Loading and syncing M19's records (formulas.md 35; migration 0043). Each record keeps its
dataclass fields in a JSON `data` column (tst.db.mna_io); a mine's monthly history is a list of
rows in MineMonth's field order."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import astuple, fields, replace
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tst.db.mna_io import _sync, from_data, to_data
from tst.db.models import MineDealRow, MineRow, RivalBidRow
from tst.sim.mining.models import Mine, MineDeal, MineMonth, RivalBid
from tst.sim.state import GameState

MONTH_FIELDS = tuple(f.name for f in fields(MineMonth))


def mine_data(mine: Mine) -> dict[str, Any]:
    data = to_data(replace(mine, history=()), ("id", "company_id"))
    data["history"] = [list(astuple(m)) for m in mine.history]
    return data


def mine_from(row: MineRow) -> Mine:
    data = dict(row.data)
    history = tuple(MineMonth(*m) for m in data.pop("history", []))
    return replace(from_data(Mine, data, id=row.id, company_id=row.company_id), history=history)


def load_mining(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    if not has_table(session, MineRow):
        return state
    mines = tuple(mine_from(r) for r in session.scalars(select(MineRow).order_by(MineRow.id)))
    deals = tuple(
        from_data(MineDeal, r.data, id=r.id, mine_id=r.mine_id)
        for r in session.scalars(select(MineDealRow).order_by(MineDealRow.id))
    )
    bids = tuple(
        from_data(RivalBid, r.data, id=r.id, company_id=r.company_id)
        for r in session.scalars(select(RivalBidRow).order_by(RivalBidRow.id))
    )
    return replace(state, mines=mines, mine_deals=deals, rival_bids=bids)


def sync_mining(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    unchanged = (old.mines, old.mine_deals, old.rival_bids) == (
        new.mines,
        new.mine_deals,
        new.rival_bids,
    )
    if unchanged or not has_table(session, MineRow):
        return
    _sync(
        session,
        old.mines,
        new.mines,
        lambda x: x.id,
        lambda x: MineRow(id=x.id, company_id=x.company_id, data=mine_data(x)),
        lambda k: delete(MineRow).where(MineRow.id == k),
    )
    _sync(
        session,
        old.mine_deals,
        new.mine_deals,
        lambda x: x.id,
        lambda x: MineDealRow(id=x.id, mine_id=x.mine_id, data=to_data(x, ("id", "mine_id"))),
        lambda k: delete(MineDealRow).where(MineDealRow.id == k),
    )
    _sync(
        session,
        old.rival_bids,
        new.rival_bids,
        lambda x: x.id,
        lambda x: RivalBidRow(
            id=x.id, company_id=x.company_id, data=to_data(x, ("id", "company_id"))
        ),
        lambda k: delete(RivalBidRow).where(RivalBidRow.id == k),
    )
