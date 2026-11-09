"""Loading and syncing M17's records (formulas.md 33.3; migration 0041): commodity contracts
and offtake agreements, each record's fields in a JSON `data` column (tst.db.mna_io)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tst.db.mna_io import _sync, from_data, to_data
from tst.db.models import CommodityDealRow
from tst.sim.commodities.models import CommodityDeal
from tst.sim.state import GameState

KEYS = ("id", "company_id")


def load_commodities(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every deal (0041); a save from before M17 has none."""
    if not has_table(session, CommodityDealRow):
        return state
    deals = tuple(
        from_data(CommodityDeal, r.data, id=r.id, company_id=r.company_id)
        for r in session.scalars(select(CommodityDealRow).order_by(CommodityDealRow.id))
    )
    return replace(state, commodity_deals=deals)


def sync_commodities(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if old.commodity_deals == new.commodity_deals or not has_table(session, CommodityDealRow):
        return
    _sync(
        session,
        old.commodity_deals,
        new.commodity_deals,
        lambda x: x.id,
        lambda x: CommodityDealRow(id=x.id, company_id=x.company_id, data=to_data(x, KEYS)),
        lambda k: delete(CommodityDealRow).where(CommodityDealRow.id == k),
    )
