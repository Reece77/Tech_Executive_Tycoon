"""Loading and syncing M18's records (formulas.md 34; migration 0042). Each record keeps its
dataclass fields in a JSON `data` column (tst.db.mna_io)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.mna_io import _sync, from_data, to_data
from tst.db.models import (
    DeskStudyRow,
    DrillHoleRow,
    ExplorationProjectRow,
    GeoBlockRow,
    SupplierLicenceRow,
)
from tst.sim.exploration.models import DeskStudy, GeoBlock, Hole, Project, SupplierLicence
from tst.sim.state import GameState

BLOCK_KEYS = ("region", "index")
LICENCE_KEYS = ("region", "block")


def block_row(b: GeoBlock) -> dict[str, Any]:
    return {"region": b.region, "idx": b.index, "data": to_data(b, BLOCK_KEYS)}


def licence_row(x: SupplierLicence) -> dict[str, Any]:
    return {"region": x.region, "block": x.block, "data": to_data(x, LICENCE_KEYS)}


def load_exploration(
    session: Session,
    state: GameState,
    has_table: Callable[[Session, Any], bool],
) -> GameState:
    """Every exploration record (0041); a save from before M18 has its backfilled geology."""
    if not has_table(session, GeoBlockRow):
        return state
    blocks = tuple(
        from_data(GeoBlock, r.data, region=r.region, index=r.idx)
        for r in session.scalars(select(GeoBlockRow).order_by(GeoBlockRow.region, GeoBlockRow.idx))
    )
    licences = tuple(
        from_data(SupplierLicence, r.data, region=r.region, block=r.block)
        for r in session.scalars(
            select(SupplierLicenceRow).order_by(SupplierLicenceRow.region, SupplierLicenceRow.block)
        )
    )
    studies = tuple(
        from_data(DeskStudy, r.data, id=r.id, company_id=r.company_id)
        for r in session.scalars(select(DeskStudyRow).order_by(DeskStudyRow.id))
    )
    projects = tuple(
        from_data(Project, r.data, id=r.id, company_id=r.company_id)
        for r in session.scalars(select(ExplorationProjectRow).order_by(ExplorationProjectRow.id))
    )
    holes = tuple(
        from_data(Hole, r.data, project_id=r.project_id, n=r.n)
        for r in session.scalars(
            select(DrillHoleRow).order_by(DrillHoleRow.project_id, DrillHoleRow.n)
        )
    )
    return replace(
        state,
        geo_blocks=blocks,
        supplier_licences=licences,
        desk_studies=studies,
        projects=projects,
        holes=holes,
    )


def sync_exploration(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    fields = ("geo_blocks", "supplier_licences", "desk_studies", "projects", "holes")
    if all(getattr(old, f) == getattr(new, f) for f in fields) or not has_table(
        session, GeoBlockRow
    ):
        return
    if old.geo_blocks != new.geo_blocks:  # written once, at game start (bulk: 280 rows)
        session.execute(delete(GeoBlockRow))
        if new.geo_blocks:
            session.execute(insert(GeoBlockRow), [block_row(b) for b in new.geo_blocks])
    if old.supplier_licences != new.supplier_licences:
        session.execute(delete(SupplierLicenceRow))
        if new.supplier_licences:
            session.execute(
                insert(SupplierLicenceRow), [licence_row(x) for x in new.supplier_licences]
            )
    _sync(
        session,
        old.desk_studies,
        new.desk_studies,
        lambda x: x.id,
        lambda x: DeskStudyRow(
            id=x.id, company_id=x.company_id, data=to_data(x, ("id", "company_id"))
        ),
        lambda k: delete(DeskStudyRow).where(DeskStudyRow.id == k),
    )
    _sync(
        session,
        old.projects,
        new.projects,
        lambda x: x.id,
        lambda x: ExplorationProjectRow(
            id=x.id, company_id=x.company_id, data=to_data(x, ("id", "company_id"))
        ),
        lambda k: delete(ExplorationProjectRow).where(ExplorationProjectRow.id == k),
    )
    old_holes = {(h.project_id, h.n) for h in old.holes}
    fresh = [h for h in new.holes if (h.project_id, h.n) not in old_holes]
    if fresh:  # holes never change once drilled
        session.execute(
            insert(DrillHoleRow),
            [
                {"project_id": h.project_id, "n": h.n, "data": to_data(h, ("project_id", "n"))}
                for h in fresh
            ],
        )
