"""Loading and syncing M21's records (formulas.md 38; migration 0046). A fab keeps its dataclass
fields in a JSON `data` column (tst.db.mna_io); its capex parts, latest month and history are
nested."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tst.db.mna_io import _sync, from_data, to_data
from tst.db.models import FabRow
from tst.sim.fabs.models import CapexPart, Fab, FabMonth
from tst.sim.state import GameState

KEYS = ("facility_id", "company_id")


def fab_data(f: Fab) -> dict[str, Any]:
    data = to_data(replace(f, month=None, parts=(), history=()), KEYS)
    data["month"] = asdict(f.month) if f.month is not None else None
    data["parts"] = [asdict(p) for p in f.parts]
    data["history"] = [list(h) for h in f.history]
    return data


def fab_from(row: FabRow) -> Fab:
    data = dict(row.data)
    month = data.pop("month", None)
    parts = data.pop("parts", [])
    history = data.pop("history", [])
    fab = from_data(Fab, data, facility_id=row.facility_id, company_id=row.company_id)
    if month is not None:
        month = dict(month)
        month["customers"] = tuple((str(n), float(v)) for n, v in month.get("customers", ()))
        month["group"] = tuple(
            (int(c), float(n), float(p), float(m)) for c, n, p, m in month.get("group", ())
        )
    return replace(
        fab,
        month=FabMonth(**month) if month is not None else None,
        parts=tuple(CapexPart(**p) for p in parts),
        history=tuple(
            (int(h[0]), float(h[1]), float(h[2]), float(h[3]), float(h[4])) for h in history
        ),
    )


def load_fabs(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every fab (0046); a save from before M21 has none."""
    if not has_table(session, FabRow):
        return state
    fabs = tuple(fab_from(r) for r in session.scalars(select(FabRow).order_by(FabRow.facility_id)))
    return replace(state, fabs=fabs)


def sync_fabs(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if old.fabs == new.fabs or not has_table(session, FabRow):
        return
    _sync(
        session,
        old.fabs,
        new.fabs,
        lambda x: x.facility_id,
        lambda x: FabRow(facility_id=x.facility_id, company_id=x.company_id, data=fab_data(x)),
        lambda k: delete(FabRow).where(FabRow.facility_id == k),
    )
