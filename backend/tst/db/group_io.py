"""Loading and syncing M16's records (formulas.md 31; migration 0039). Each record keeps its
dataclass fields in a JSON `data` column (tst.db.mna_io)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tst.db.mna_io import _sync, from_data, to_data
from tst.db.models import (
    GroupListingRow,
    GroupPitchRow,
    HoldingRow,
    MandateRow,
    OwnershipRow,
    PersonalStakeRow,
    StakeRow,
)
from tst.sim.group.models import (
    GroupListing,
    GroupPitch,
    Holding,
    Mandate,
    Ownership,
    PersonalStake,
    Stake,
)
from tst.sim.state import GameState

KEYS = ("id", "company_id", "owner_id")
STAKE_KEYS = ("id", "owner_id", "company_id")


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
    stakes = tuple(
        from_data(Stake, r.data, id=r.id, owner_id=r.owner_id, company_id=r.company_id)
        for r in session.scalars(select(StakeRow).order_by(StakeRow.id))
    )
    mandates = tuple(
        from_data(Mandate, r.data, company_id=r.company_id)
        for r in session.scalars(select(MandateRow).order_by(MandateRow.company_id))
    )
    pitches = tuple(
        from_data(GroupPitch, r.data, id=r.id, company_id=r.company_id)
        for r in session.scalars(select(GroupPitchRow).order_by(GroupPitchRow.id))
    )
    listings = tuple(
        from_data(GroupListing, r.data, company_id=r.company_id)
        for r in session.scalars(select(GroupListingRow).order_by(GroupListingRow.company_id))
    )
    personal = tuple(
        from_data(PersonalStake, r.data, person_id=r.person_id, company_id=r.company_id)
        for r in session.scalars(
            select(PersonalStakeRow).order_by(
                PersonalStakeRow.person_id, PersonalStakeRow.company_id
            )
        )
    )
    return replace(
        state,
        group_listings=listings,
        personal_stakes=personal,
        ownerships=ownerships,
        holdings=holdings,
        stakes=stakes,
        mandates=mandates,
        group_pitches=pitches,
    )


def sync_group(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    fields = (
        "ownerships",
        "holdings",
        "stakes",
        "mandates",
        "group_pitches",
        "group_listings",
        "personal_stakes",
    )
    if all(getattr(old, f) == getattr(new, f) for f in fields) or not has_table(
        session, OwnershipRow
    ):
        return
    _sync(
        session,
        old.group_listings,
        new.group_listings,
        lambda x: x.company_id,
        lambda x: GroupListingRow(company_id=x.company_id, data=to_data(x, ("company_id",))),
        lambda k: delete(GroupListingRow).where(GroupListingRow.company_id == k),
    )
    _sync(
        session,
        old.personal_stakes,
        new.personal_stakes,
        lambda x: (x.person_id, x.company_id),
        lambda x: PersonalStakeRow(
            person_id=x.person_id,
            company_id=x.company_id,
            data=to_data(x, ("person_id", "company_id")),
        ),
        lambda k: delete(PersonalStakeRow).where(
            PersonalStakeRow.person_id == k[0], PersonalStakeRow.company_id == k[1]
        ),
    )
    _sync(
        session,
        old.mandates,
        new.mandates,
        lambda m: m.company_id,
        lambda m: MandateRow(company_id=m.company_id, data=to_data(m, ("company_id",))),
        lambda k: delete(MandateRow).where(MandateRow.company_id == k),
    )
    _sync(
        session,
        old.group_pitches,
        new.group_pitches,
        lambda p: p.id,
        lambda p: GroupPitchRow(
            id=p.id, company_id=p.company_id, data=to_data(p, ("id", "company_id"))
        ),
        lambda k: delete(GroupPitchRow).where(GroupPitchRow.id == k),
    )
    _sync(
        session,
        old.stakes,
        new.stakes,
        lambda x: x.id,
        lambda x: StakeRow(
            id=x.id, owner_id=x.owner_id, company_id=x.company_id, data=to_data(x, STAKE_KEYS)
        ),
        lambda k: delete(StakeRow).where(StakeRow.id == k),
    )
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
