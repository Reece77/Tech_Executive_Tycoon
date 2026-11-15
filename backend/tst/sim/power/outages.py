"""Grid outages (docs/formulas.md 46.5), from `power.start`: each month each region has an
outage with chance rate / 12, the rate its data's interruptions a year (power.yaml
`outages_a_year`) x (1 + `outage.tight_factor` x (the region's power balance factor - 1)) when its
market is tight, capped at `outage.max_rate` (stream power (0, region_index), one uniform).

A fab in an outage region loses `outage.wafer_loss` x its exposure of the month's starts (phase
4, tst.sim.fabs.plants); a data centre has a 22.5 outage with chance its exposure (phase 6,
tst.sim.facilities.outages, on the facility's own draw). Exposure is 1 less the share of its load
its behind-the-meter plants hold through an outage: each live plant's MW x its type's
`firm_share`, over the facility's draw in MW. Plants' own forced outages are in
tst.sim.power.plants.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.log import LogItem, inbox_item
from tst.sim.power import demand, draws
from tst.sim.power.models import GridOutage
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

REGION_FAMILY: Final = 0  # tunable-exempt: stream power family (0, region_index)
OUTAGE_TAG: Final = 0  # tunable-exempt: the third key part for a region's monthly outage draw
MONTHS: Final = 12  # tunable-exempt: calendar


def power_factor(state: GameState, region: str) -> float:
    """M28's balance factor for the region's power good (1 before the world runs)."""
    from tst.sim.world import query as wq

    return wq.factor(state, f"power_{region}")


def rate(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    assert data.power is not None
    ob = balance.power.outage
    base = data.power.region(region).outages_a_year
    tight = max(0.0, power_factor(state, region) - 1)
    return min(ob.max_rate, base * (1 + ob.tight_factor * tight))


def grid_outage(state: GameState, region: str) -> bool:
    return any(o.turn == state.turn and o.region == region for o in state.grid_outages)


def outages_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Phase 4 (before production): the month's grid outages; the window kept trimmed."""
    if data.power is None or state.turn < month_to_turn(balance.power.start):
        return state, []
    hit: list[GridOutage] = []
    for i, r in enumerate(data.power.regions):
        u = float(draws.gen(rng, state.turn, REGION_FAMILY, i, OUTAGE_TAG).random())
        if u < rate(state, r.key, balance, data) / MONTHS:
            hit.append(GridOutage(state.turn, r.key))
    keep = state.turn - balance.power.history_months
    kept = tuple(o for o in state.grid_outages if o.turn > keep)
    state = replace(state, grid_outages=(*kept, *hit))
    logs = []
    regions = {o.region for o in hit}
    for company in sorted({f.company_id for f in state.facilities if f.region in regions}):
        if not state.company(company).is_player:
            continue
        for region in sorted(regions):
            if any(
                f.company_id == company and f.region == region and f.status != "closed"
                for f in state.facilities
            ):
                logs.append(
                    inbox_item(state.turn, company, "grid_outage", region=data.region(region).label)
                )
    return state, logs


def firm_share(state: GameState, facility: Facility, balance: Balance, data: GameData) -> float:
    """The share of a facility's load its live behind-the-meter plants hold through an outage."""
    load = demand.facility_mw(state, facility, balance, data)
    if load <= 0:
        return 0.0
    firm = sum(
        p.mw * balance.power.plants.firm_share[p.type]
        for p in state.plants
        if p.site_id == facility.id and p.live(state.turn) and not p.offline(state.turn)
    )
    return min(1.0, firm / load)


def exposure(state: GameState, facility: Facility, balance: Balance, data: GameData) -> float:
    """0 when no grid outage hits the facility's region this month, else 1 less its firm share."""
    if not grid_outage(state, facility.region):
        return 0.0
    return 1.0 - firm_share(state, facility, balance, data)
