"""Loading and syncing M16's records (formulas.md 31; migration 0039). Each record keeps its
dataclass fields in a JSON `data` column (tst.db.mna_io)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tst.db.mna_io import _sync, from_data, to_data
from tst.db.models import HoldingRow, OwnershipRow
from tst.sim.group.models import Holding, Ownership
from tst.sim.state import GameState

KEYS = ("id", "company_id", "owner_id")


def load_group(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every holding (0039); a save from before M16 has the backfilled ones."""
    if not has_table(session, OwnershipRow):
        return state
    ownerships = tuple(
        from_data(Ownership, r.data, id=r.id, company_id=r.company_id, owner_id=r.owner_id)
        for r in session.scalars(select(OwnershipRow).order_by(OwnershipRow.id))
    )
    holdings = tuple(
        from_data(Holding, r.data, company_id=r.company_id)
        for r in session.scalars(select(HoldingRow).order_by(HoldingRow.company_id))
    )
    return replace(state, ownerships=ownerships, holdings=holdings)


def sync_group(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if (old.ownerships, old.holdings) == (new.ownerships, new.holdings) or not has_table(
        session, OwnershipRow
    ):
        return
    _sync(
        session,
        old.holdings,
        new.holdings,
        lambda h: h.company_id,
        lambda h: HoldingRow(company_id=h.company_id, data=to_data(h, ("company_id",))),
        lambda k: delete(HoldingRow).where(HoldingRow.company_id == k),
    )
    _sync(
        session,
        old.ownerships,
        new.ownerships,
        lambda o: o.id,
        lambda o: OwnershipRow(
            id=o.id, company_id=o.company_id, owner_id=o.owner_id, data=to_data(o, KEYS)
        ),
        lambda k: delete(OwnershipRow).where(OwnershipRow.id == k),
    )
