"""Loading and syncing M20's records (formulas.md 36; migration 0044). Each record keeps its
dataclass fields in a JSON `data` column (tst.db.mna_io); a refinery's latest month is a nested
object."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import _sync, from_data, to_data
from tst.db.models import RefineryRow, RefiningDealRow, RefiningSupplyRow
from tst.sim.refining.models import OwnSupply, PlantMonth, Refinery, RefiningDeal
from tst.sim.state import GameState

KEYS = ("facility_id", "company_id")


def refinery_data(r: Refinery) -> dict[str, Any]:
    data = to_data(replace(r, month=None), KEYS)
    data["month"] = asdict(r.month) if r.month is not None else None
    return data


def refinery_from(row: RefineryRow) -> Refinery:
    data = dict(row.data)
    month = data.pop("month", None)
    ref = from_data(Refinery, data, facility_id=row.facility_id, company_id=row.company_id)
    return replace(ref, month=PlantMonth(**month) if month is not None else None)


def load_refining(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every refining record (0044); a save from before M20 has none."""
    if not has_table(session, RefineryRow):
        return state
    refineries = tuple(
        refinery_from(r)
        for r in session.scalars(select(RefineryRow).order_by(RefineryRow.facility_id))
    )
    deals = tuple(
        from_data(RefiningDeal, r.data, id=r.id, company_id=r.company_id)
        for r in session.scalars(select(RefiningDealRow).order_by(RefiningDealRow.id))
    )
    supply = tuple(
        from_data(OwnSupply, r.data)
        for r in session.scalars(select(RefiningSupplyRow).order_by(RefiningSupplyRow.n))
    )
    return replace(state, refineries=refineries, refining_deals=deals, own_supply=supply)


def sync_refining(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    fields = ("refineries", "refining_deals", "own_supply")
    if all(getattr(old, f) == getattr(new, f) for f in fields) or not has_table(
        session, RefineryRow
    ):
        return
    _sync(
        session,
        old.refineries,
        new.refineries,
        lambda x: x.facility_id,
        lambda x: RefineryRow(
            facility_id=x.facility_id, company_id=x.company_id, data=refinery_data(x)
        ),
        lambda k: delete(RefineryRow).where(RefineryRow.facility_id == k),
    )
    _sync(
        session,
        old.refining_deals,
        new.refining_deals,
        lambda x: x.id,
        lambda x: RefiningDealRow(
            id=x.id, company_id=x.company_id, data=to_data(x, ("id", "company_id"))
        ),
        lambda k: delete(RefiningDealRow).where(RefiningDealRow.id == k),
    )
    if old.own_supply != new.own_supply:  # the month's lots, replaced each phase 4
        session.execute(delete(RefiningSupplyRow))
        if new.own_supply:
            session.execute(
                insert(RefiningSupplyRow),
                [{"n": i, "data": to_data(s)} for i, s in enumerate(new.own_supply)],
            )
