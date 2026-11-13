"""One company owns an asset while its group uses it (M23a; ADR-0020 1-2, docs/formulas.md 31.1,
35.1): the shared group-ownership layer.

- **Moving a facility** between two companies of the group (`move_facility`): the facility row
  and every kind-specific record (a mine, a refinery, a fab) change owner together, so each later
  month's operations, staffing and depreciation post to the new owner. The **crew** moves with it:
  a unit of the old owner that staffs only this facility, with its active people, becomes the new
  owner's (their pay follows, on the new owner's payroll); a unit that staffs anything else of
  the old owner stays, and the facility is left unstaffed. The books (book value against cash)
  are the caller's (`mining.actions.transfer_asset`).
- **Routing** (`inbox_company`): a group company's critical events and inbox items go to the
  player's inbox; the record that raised them names the affected company and facility.
- **Managing** (M23r, Codex review 6 finding 2): the founder manages every facility of the group
  (`managed_facility`): staffs, converts and sells it, and its owner pays and is paid. A unit of
  another group company that the founder puts on a facility moves to the facility's owner with
  its active people (`crew_to`, the transfer's crew rule), so the owner's payroll carries the
  crew that its facility counts (`lifecycle.staff_of` counts only the owner's employees).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import GameData
from tst.sim.errors import InvalidActionError
from tst.sim.facilities.models import Facility
from tst.sim.geopolitics.models import Site, SiteKind
from tst.sim.org.models import OrgUnit
from tst.sim.state import (
    GameState,
    group_companies,
    listed_id,
    with_employment,
    with_fab,
    with_facility,
    with_mine,
    with_refinery,
    with_site,
    with_unit,
)


def group_ids(state: GameState) -> set[int]:
    """The player's group (31.1): the listed company and every company it controls."""
    return {c.id for c in group_companies(state, listed_id(state))} | {state.player.id}


def inbox_company(state: GameState, company_id: int) -> int:
    """Where an item about `company_id` is shown: the player's inbox for any company of the
    player's group (M23a routing rule), else the company itself."""
    return state.player.id if company_id in group_ids(state) else company_id


def check_country(data: GameData, region: str, country: str | None) -> None:
    """A chosen country must sit in the region (M23a: a country choice for new facilities and
    subsidiaries)."""
    if country is None or data.countries is None:
        return
    if not any(c.key == country and c.region == region for c in data.countries.countries):
        raise InvalidActionError(f"{country!r} is not a country of {data.region(region).label}")


def place(state: GameState, kind: SiteKind, item_id: int, country: str | None) -> GameState:
    """Record where a new company or facility sits when a country was chosen (39.1's sites)."""
    if country is None:
        return state
    return with_site(state, Site(kind, item_id, country))


def crew_to(state: GameState, unit_id: int, to: int) -> GameState:
    """A unit and its active people to company `to` (their pay follows, on its payroll)."""
    unit = state.unit(unit_id)
    assert unit is not None
    if unit.company_id == to:
        return state
    seller = unit.company_id
    state = with_unit(state, replace(unit, company_id=to, parent_id=None))
    for e in state.employments:
        if e.unit_id == unit.id and e.company_id == seller and e.status == "active":
            state = with_employment(state, replace(e, company_id=to))
    return state


def managed_facility(state: GameState, actor_id: int, facility_id: int, own: int) -> Facility:
    """A facility the actor manages (module docstring): one of `own` (the actor's company), or,
    for the founder, of any company of the player's group. Closed or unknown ones raise."""
    from tst.sim.errors import UnknownFacilityError

    facility = state.facility(facility_id)
    founder = state.founder_of(state.player.id)
    allowed = {own}
    if founder is not None and founder.id == actor_id:
        allowed |= group_ids(state)
    if facility is None or facility.company_id not in allowed or facility.status == "closed":
        raise UnknownFacilityError(f"no facility {facility_id}")
    return facility


def staff_unit(state: GameState, actor_id: int, unit_id: int, own: int) -> OrgUnit:
    """A unit the actor may put on a facility: an active unit of `own`, or (the founder) of any
    company of the group."""
    from tst.sim.errors import UnknownUnitError

    unit = state.unit(unit_id)
    founder = state.founder_of(state.player.id)
    allowed = {own}
    if founder is not None and founder.id == actor_id:
        allowed |= group_ids(state)
    if unit is None or unit.company_id not in allowed or unit.status != "active":
        raise UnknownUnitError(f"no unit {unit_id}")
    return unit


def move_facility(state: GameState, facility_id: int, to: int) -> GameState:
    """Every record of a facility to company `to`, its crew with it (module docstring)."""
    facility = state.facility(facility_id)
    assert facility is not None
    seller = facility.company_id
    unit_id = facility.unit_id
    if unit_id is not None:
        unit = state.unit(unit_id)
        shared = any(
            f.unit_id == unit_id and f.id != facility_id and f.status != "closed"
            for f in state.facilities
        )
        if unit is None or unit.company_id != seller or shared:
            unit_id = None  # the old owner keeps its unit: the new owner staffs the facility
        else:
            state = crew_to(state, unit_id, to)
    state = with_facility(state, replace(facility, company_id=to, unit_id=unit_id))
    mine = state.mine(facility_id)
    if mine is not None:
        state = with_mine(state, replace(mine, company_id=to))
    ref = next((r for r in state.refineries if r.facility_id == facility_id), None)
    if ref is not None:
        state = with_refinery(state, replace(ref, company_id=to))
    fab = next((f for f in state.fabs if f.facility_id == facility_id), None)
    if fab is not None:
        state = with_fab(state, replace(fab, company_id=to))
    return state


__all__ = [
    "check_country",
    "crew_to",
    "group_ids",
    "inbox_company",
    "managed_facility",
    "move_facility",
    "place",
    "staff_unit",
]
