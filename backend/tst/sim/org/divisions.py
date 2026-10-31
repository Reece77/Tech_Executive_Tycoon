"""Divisions, the layer tax and support pools (docs/formulas.md 18.1, 18.2, 18.4).

Everything here is derived from the state. A division is an org unit of kind `division`
whose parent is the company root; departments and teams under it belong to it. Corporate is
the root and every unit outside a division (division id None).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from tst.sim.data_models import Balance, GameData
from tst.sim.org.formulas import coverage, support_need
from tst.sim.org.models import OrgUnit
from tst.sim.org.rules import OrgView
from tst.sim.products.models import Product
from tst.sim.snapshot import DivisionMonth
from tst.sim.state import CompanyState, GameState

NONE_FUNCTION = "none"  # roles.yaml product_function of support staff (18.4)


def is_scaleup(company: CompanyState, balance: Balance) -> bool:
    """18.1-18.5 apply: the player's company at stage 3 or later. Rivals never use them."""
    return company.is_player and company.stage >= balance.org.division_stage


def company_divisions(state: GameState, company_id: int) -> tuple[OrgUnit, ...]:
    return tuple(u for u in state.active_units(company_id) if u.kind == "division")


def division_of_unit(units: Mapping[int, OrgUnit], unit_id: int | None) -> int | None:
    """The division containing `unit_id` (itself if it is one); None for corporate."""
    seen: set[int] = set()
    while unit_id is not None and unit_id in units and unit_id not in seen:
        seen.add(unit_id)
        unit = units[unit_id]
        if unit.kind == "division":
            return unit.id
        unit_id = unit.parent_id
    return None


def unit_depth(units: Mapping[int, OrgUnit], unit_id: int | None) -> int:
    """Root 0, a division or a unit under the root 1, a department under a division 2, a
    team under that 3 (18.2)."""
    depth = 0
    seen: set[int] = set()
    while unit_id is not None and unit_id in units and unit_id not in seen:
        seen.add(unit_id)
        depth += 1
        unit_id = units[unit_id].parent_id
    return depth


def person_division(view: OrgView, person_id: int) -> int | None:
    return division_of_unit(view.units, view.unit_of.get(person_id))


def product_division_spread(state: GameState, view: OrgView, product: Product) -> set[int | None]:
    """The divisions (None = corporate) of the units assigned to a product (18.2)."""
    from tst.sim.products.team import assigned_units

    return {division_of_unit(view.units, u) for u in assigned_units(state, product)}


def is_support(state: GameState, person_id: int, data: GameData) -> bool:
    """Support staff: an employee whose role's product function is none, or a seat holder
    (18.4). The founder is not."""
    person = state.person(person_id)
    if person.is_founder:
        return False
    if state.seat_of(person_id) is not None:
        return True
    employment = state.employment_of(person_id)
    return employment is not None and data.role(employment.role).product_function == NONE_FUNCTION


@dataclass(frozen=True, slots=True)
class SupportPool:
    """One pool (18.4): corporate with every central division (key None), or one embedded
    division (its id)."""

    key: int | None
    headcount: int
    support: int
    need: int
    coverage: float


def pool_of(view: OrgView, person_id: int) -> int | None:
    """The person's support pool: their division if it is embedded, else the central pool."""
    division = person_division(view, person_id)
    if division is not None and view.units[division].embedded:
        return division
    return None


def product_pool(state: GameState, product: Product) -> int | None:
    """The pool of the product's division (18.4): embedded division, else central."""
    division = state.unit(product.division_id) if product.division_id is not None else None
    if division is not None and division.status == "active" and division.embedded:
        return division.id
    return None


def support_pools(
    state: GameState, view: OrgView, balance: Balance, data: GameData
) -> dict[int | None, SupportPool]:
    """Coverage of every pool, the central pool (None) always first."""
    heads: dict[int | None, int] = defaultdict(int)
    support: dict[int | None, int] = defaultdict(int)
    heads[None] = 0
    for unit in view.units.values():
        if unit.embedded:
            heads[unit.id] = 0
    for person_id in view.unit_of:
        pool = pool_of(view, person_id)
        heads[pool] += 1
        if is_support(state, person_id, data):
            support[pool] += 1
    org = balance.org
    return {
        key: SupportPool(
            key=key,
            headcount=h,
            support=support[key],
            need=support_need(h, org),
            coverage=coverage(h, support[key], org),
        )
        for key, h in heads.items()
    }


def division_headcounts(view: OrgView) -> dict[int | None, int]:
    """Staff per division, corporate (None, founder included) first."""
    heads: dict[int | None, int] = {None: 0}
    for unit in sorted(view.units.values(), key=lambda u: u.id):
        if unit.kind == "division":
            heads[unit.id] = 0
    for person_id in view.unit_of:
        heads[person_division(view, person_id)] = heads.get(person_division(view, person_id), 0) + 1
    return heads


CORPORATE = "Corporate"  # the name shown for the company root's own P&L column (18.1)


def division_months(state: GameState) -> tuple[DivisionMonth, ...]:
    """Corporate and each division's headcount this month, for the player when it has
    divisions (18.1)."""
    from tst.sim.org.rules import org_view

    player = state.player
    divisions = company_divisions(state, player.id)
    if not divisions:
        return ()
    heads = division_headcounts(org_view(state, player.id))
    rows = [DivisionMonth(state.turn, player.id, None, CORPORATE, heads[None], False)]
    rows += [
        DivisionMonth(state.turn, player.id, d.id, d.name, heads.get(d.id, 0), d.embedded)
        for d in divisions
    ]
    return tuple(rows)
