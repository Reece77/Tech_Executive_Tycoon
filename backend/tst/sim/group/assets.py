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
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.state import (
    GameState,
    group_companies,
    listed_id,
    with_employment,
    with_fab,
    with_facility,
    with_mine,
    with_refinery,
    with_unit,
)


def group_ids(state: GameState) -> set[int]:
    """The player's group (31.1): the listed company and every company it controls."""
    return {c.id for c in group_companies(state, listed_id(state))} | {state.player.id}


def inbox_company(state: GameState, company_id: int) -> int:
    """Where an item about `company_id` is shown: the player's inbox for any company of the
    player's group (M23a routing rule), else the company itself."""
    return state.player.id if company_id in group_ids(state) else company_id


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
            state = with_unit(state, replace(unit, company_id=to, parent_id=None))
            for e in state.employments:
                if e.unit_id == unit.id and e.company_id == seller and e.status == "active":
                    state = with_employment(state, replace(e, company_id=to))
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


__all__ = ["group_ids", "inbox_company", "move_facility"]
