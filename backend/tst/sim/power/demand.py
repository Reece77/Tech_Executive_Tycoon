"""Demand (docs/formulas.md 46.1, ADR-0022 1): every metered facility's energy this month.

A meter reading is a facility's MWh and what it paid for them at the grid price, read from the
records its own phase wrote this month (phases 4-6), so it is exactly what was charged:

- data centres (`power.paid_by` kinds): live units x the kind's draw (power.yaml `draws`), paid
  live units x opex x the grid multiple (phase 6's operating cost, `operating_lines`);
- fabs: the month's starts run x the node's MWh a start (`FabMonth.energy_mwh`, phase 5);
- refineries: output x the recipe's MWh a unit (`PlantMonth.energy_mwh`, phase 4);
- mines: the energy part of variable cost / the reference price (`MineMonth.energy_mwh`, phase 5).

Assembly plants and offices are not metered: their power is inside their fixed costs (M32
decision, the history guard). Pure functions of the state and data.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Final

from tst.sim.commodities.power import opex_cents
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.models import Facility
from tst.sim.power import grid
from tst.sim.state import GameState

FAB: Final = "fab"  # tunable-exempt: the fab facility kind (38.2)
TINY: Final = 1e-9  # tunable-exempt: energy below this is none


@dataclass(frozen=True, slots=True)
class Meter:
    """One facility's energy this month."""

    facility_id: int
    company_id: int
    region: str
    city: str | None
    kind: str
    mwh: float
    grid_cents: int  # what its phase charged for that energy at the grid price


def _centre(state: GameState, f: Facility, balance: Balance, data: GameData) -> Meter | None:
    pf = data.power
    live = f.live_capacity(state.turn)
    if pf is None or live <= 0 or f.kind not in balance.power.paid_by:
        return None
    kind = balance.facility.kinds[f.kind]
    mult = grid.kind_multiplier(state, f.kind, f.region, balance, data)
    cents = round(opex_cents(live * kind.opex_per_unit_cents, mult))  # as operating_cents
    return Meter(f.id, f.company_id, f.region, f.city, f.kind, live * pf.draws[f.kind], cents)


def meters(state: GameState, balance: Balance, data: GameData) -> list[Meter]:
    """Every metered facility's reading this month, by facility id."""
    if data.power is None:
        return []
    turn = state.turn
    out: list[Meter] = []
    by_id = {f.id: f for f in state.facilities}
    for fac in state.facilities:
        m = _centre(state, fac, balance, data)
        if m is not None:
            out.append(m)
    for fab in state.fabs:
        month = fab.month
        f = by_id.get(fab.facility_id)
        if f is None or month is None or month.turn != turn or month.energy_mwh <= TINY:
            continue
        out.append(
            Meter(f.id, f.company_id, f.region, f.city, f.kind, month.energy_mwh, month.power_cents)
        )
    for ref in state.refineries:
        pm = ref.month
        f = by_id.get(ref.facility_id)
        if f is None or pm is None or pm.turn != turn or pm.energy_mwh <= TINY:
            continue
        out.append(
            Meter(f.id, f.company_id, f.region, f.city, f.kind, pm.energy_mwh, pm.power_cents)
        )
    for mine in state.mines:
        last = mine.history[-1] if mine.history else None
        f = by_id.get(mine.id)
        if last is None or last.turn != turn or last.energy_mwh <= TINY:
            continue
        city = f.city if f is not None else None
        kind = f.kind if f is not None else "mine"
        out.append(
            Meter(
                mine.id, mine.company_id, mine.region, city, kind, last.energy_mwh, last.power_cents
            )
        )
    return sorted(out, key=lambda m: m.facility_id)


def by_company_region(readings: list[Meter]) -> dict[tuple[int, str], list[Meter]]:
    out: dict[tuple[int, str], list[Meter]] = defaultdict(list)
    for m in readings:
        out[(m.company_id, m.region)].append(m)
    return dict(sorted(out.items()))


def mw(mwh: float, balance: Balance) -> float:
    """A month's MWh as an average draw in MW."""
    return mwh / balance.power.hours_a_month


def facility_mw(state: GameState, f: Facility, balance: Balance, data: GameData) -> float:
    """A facility's draw in MW at full capacity (the queue's and siting's size, 46.3): data
    centres at their whole capacity, fabs at their starts' energy, others none."""
    pf = data.power
    if pf is None:
        return 0.0
    if f.kind in pf.draws:
        return mw(f.capacity * pf.draws[f.kind], balance)
    if f.kind == FAB:
        fab = next((x for x in state.fabs if x.facility_id == f.id), None)
        if fab is None:
            return 0.0
        from tst.sim.fabs.plants import power_mwh

        return mw(f.capacity * power_mwh(state, fab, balance, data), balance)
    return 0.0
