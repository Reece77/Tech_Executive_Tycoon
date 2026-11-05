"""Loading and syncing M14's records (formulas.md 28; migration 0034). Each M&A record keeps
its dataclass fields in a JSON `data` column; tuples round-trip as JSON lists."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import fields, replace
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from tst.db.models import (
    AcquiredPersonRow,
    AcquisitionRow,
    CompanyParentRow,
    DealRow,
    RivalListingRow,
    TargetFileRow,
)
from tst.sim.mna.models import AcquiredPerson, Acquisition, Deal, RivalListing, TargetFile
from tst.sim.state import GameState


def _encode(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_encode(v) for v in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_decode(v) for v in value)
    return value


def to_data(record: Any, skip: tuple[str, ...] = ()) -> dict[str, Any]:
    """A frozen record's fields as JSON (the key columns left out)."""
    return {f.name: _encode(getattr(record, f.name)) for f in fields(record) if f.name not in skip}


def from_data[T](cls: Callable[..., T], data: dict[str, Any], **keys: Any) -> T:
    known = {f.name for f in fields(cls)}  # type: ignore[arg-type]
    return cls(**keys, **{k: _decode(v) for k, v in data.items() if k in known})


def load_mna(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every M&A record, and kept brands' parents (0034)."""
    if not has_table(session, DealRow):
        return state
    parents = {r.company_id: r.parent_id for r in session.scalars(select(CompanyParentRow))}
    companies = tuple(
        replace(c, parent_id=parents[c.id]) if c.id in parents else c for c in state.companies
    )
    listings = tuple(
        RivalListing(r.company_id, float(r.sentiment))
        for r in session.scalars(select(RivalListingRow).order_by(RivalListingRow.company_id))
    )
    files = tuple(
        from_data(TargetFile, r.data, acquirer_id=r.acquirer_id, target_id=r.target_id)
        for r in session.scalars(
            select(TargetFileRow).order_by(TargetFileRow.acquirer_id, TargetFileRow.target_id)
        )
    )
    deals = tuple(
        from_data(Deal, r.data, id=r.id)
        for r in session.scalars(select(DealRow).order_by(DealRow.id))
    )
    acquisitions = tuple(
        from_data(Acquisition, r.data, deal_id=r.deal_id)
        for r in session.scalars(select(AcquisitionRow).order_by(AcquisitionRow.deal_id))
    )
    people = tuple(
        from_data(AcquiredPerson, r.data, person_id=r.person_id)
        for r in session.scalars(select(AcquiredPersonRow).order_by(AcquiredPersonRow.person_id))
    )
    last = int(session.scalar(select(func.max(DealRow.id))) or 0)
    return replace(
        state,
        companies=companies,
        rival_listings=listings,
        target_files=files,
        deals=deals,
        acquisitions=acquisitions,
        acquired_people=people,
        next_ids=replace(state.next_ids, deal=last + 1),
    )


def _sync[T](
    session: Session,
    old: Iterable[T],
    new: Iterable[T],
    key: Callable[[T], Any],
    to_row: Callable[[T], Any],
    delete_row: Callable[[Any], Any],
) -> None:
    before = {key(x): x for x in old}
    after = {key(x): x for x in new}
    for k in before.keys() - after.keys():
        session.execute(delete_row(k))
    for k, x in after.items():
        if before.get(k) != x:
            session.merge(to_row(x))


def sync_mna(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    """Write what changed in the M&A records and kept brands' parents (0034)."""
    unchanged = (
        old.rival_listings,
        old.target_files,
        old.deals,
        old.acquisitions,
        old.acquired_people,
    ) == (
        new.rival_listings,
        new.target_files,
        new.deals,
        new.acquisitions,
        new.acquired_people,
    )
    parents_old = {c.id: c.parent_id for c in old.companies if c.parent_id is not None}
    parents_new = {c.id: c.parent_id for c in new.companies if c.parent_id is not None}
    if (unchanged and parents_old == parents_new) or not has_table(session, DealRow):
        return
    for cid in parents_old.keys() - parents_new.keys():
        session.execute(delete(CompanyParentRow).where(CompanyParentRow.company_id == cid))
    for cid, parent in parents_new.items():
        if parents_old.get(cid) != parent:
            session.merge(CompanyParentRow(company_id=cid, parent_id=parent))
    _sync(
        session,
        old.rival_listings,
        new.rival_listings,
        lambda x: x.company_id,
        lambda x: RivalListingRow(company_id=x.company_id, sentiment=x.sentiment),
        lambda k: delete(RivalListingRow).where(RivalListingRow.company_id == k),
    )
    _sync(
        session,
        old.target_files,
        new.target_files,
        lambda f: (f.acquirer_id, f.target_id),
        lambda f: TargetFileRow(
            acquirer_id=f.acquirer_id,
            target_id=f.target_id,
            data=to_data(f, ("acquirer_id", "target_id")),
        ),
        lambda k: delete(TargetFileRow).where(
            TargetFileRow.acquirer_id == k[0], TargetFileRow.target_id == k[1]
        ),
    )
    _sync(
        session,
        old.deals,
        new.deals,
        lambda d: d.id,
        lambda d: DealRow(id=d.id, data=to_data(d, ("id",))),
        lambda k: delete(DealRow).where(DealRow.id == k),
    )
    _sync(
        session,
        old.acquisitions,
        new.acquisitions,
        lambda a: a.deal_id,
        lambda a: AcquisitionRow(deal_id=a.deal_id, data=to_data(a, ("deal_id",))),
        lambda k: delete(AcquisitionRow).where(AcquisitionRow.deal_id == k),
    )
    _sync(
        session,
        old.acquired_people,
        new.acquired_people,
        lambda p: p.person_id,
        lambda p: AcquiredPersonRow(person_id=p.person_id, data=to_data(p, ("person_id",))),
        lambda k: delete(AcquiredPersonRow).where(AcquiredPersonRow.person_id == k),
    )
