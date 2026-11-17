"""Charging (docs/formulas.md 49.5): public coverage and the player's charging networks.

**Public chargers** in a region are the data's to 2025 (thousands, vehicles.yaml), then grow with
the region's EV sales against December 2025's; companies' own networks add their chargers at the
real world's scale (game chargers / vehicles.scale), since the data counts real ones.

**A charging network** (a facility of kind `charging_network`; generic capex, opex and staff) in
a region sells `chargers x kwh_per_charger_month x use` kWh a month at the region's price, with
`use` = the region's base x the EV share over 2024's (within 0.2-2), x `exclusive_use` when it is
exclusive to the owner's cars. Its energy is bought at the region's grid price (refining's power
index, 46.2). Revenue posts to 4440 charging sales and energy to 5000. An exclusive network gives
the owner's cars `exclusive_points` in the region; once it holds `scrutiny_share` of the region's
public chargers the region's automotive regulator orders it opened (it becomes open the next
month, with an inbox note).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.lifecycle import facility_name
from tst.sim.ledger import CASH, COGS, LedgerEntry, LedgerLine
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.refining import plants as refinery
from tst.sim.state import GameState
from tst.sim.vehicles.data import TINY, file, year_at
from tst.sim.vehicles.models import ChargingMonth, ChargingNetwork

CHARGING_SALES: Final = "4440_charging_sales"
THOUSAND: Final = 1000  # tunable-exempt: vehicles.yaml chargers are thousands
KWH_PER_MWH: Final = 1000  # tunable-exempt: unit conversion
REF_YEAR: Final = 2024  # tunable-exempt: charging.use is 2024's
USE_BOUNDS: Final = (0.2, 2.0)  # tunable-exempt: the use multiple's bounds


def own_chargers(state: GameState, region: str, balance: Balance) -> float:
    return float(
        sum(
            f.live_capacity(state.turn)
            for n in state.charging_networks
            if n.region == region and (f := state.facility(n.facility_id)) is not None
        )
    )


def public_chargers(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """Public chargers in the region, real world (module docstring)."""
    from tst.sim.vehicles import demand

    vb = balance.vehicles
    r = file(data).region(region)
    if state.turn < vb.start_turn:
        base = r.chargers_at(year_at(state.turn)) * THOUSAND
    else:
        last = vb.start_turn - 1
        base = r.chargers_at(year_at(last)) * THOUSAND
        then = demand.car_sales(region, last, data) * r.share_at(year_at(last))
        now = demand.ev_sales_year(state, region, balance, data) / vb.scale
        base *= now / then if then > TINY else 1.0
    return base + own_chargers(state, region, balance) / vb.scale


def use_of(state: GameState, network: ChargingNetwork, balance: Balance, data: GameData) -> float:
    from tst.sim.vehicles import demand

    cb = balance.vehicles.charging
    r = file(data).region(network.region)
    ref = r.share_at(REF_YEAR)
    share = demand.ev_share(state, network.region, balance, data)
    mult = min(USE_BOUNDS[1], max(USE_BOUNDS[0], share / ref)) if ref > TINY else USE_BOUNDS[0]
    use = cb.use.get(network.region, 0.0) * mult
    return use * (cb.exclusive_use if network.exclusive else 1.0)


def exclusive_in(state: GameState, company_id: int, region: str) -> bool:
    return any(
        n.company_id == company_id
        and n.region == region
        and n.exclusive
        and (f := state.facility(n.facility_id)) is not None
        and f.live_capacity(state.turn) > 0
        for n in state.charging_networks
    )


def networks_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Phase 5: every live network's sales and energy (module docstring)."""
    if not state.charging_networks:
        return state, [], []
    cb = balance.vehicles.charging
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    out = []
    for n in state.charging_networks:
        f = state.facility(n.facility_id)
        live = f.live_capacity(state.turn) if f is not None else 0
        if f is None or live <= 0:
            out.append(n)
            continue
        use = use_of(state, n, balance, data)
        kwh = live * cb.kwh_per_charger_month * use
        revenue = round(exact(kwh) * exact(cb.price_cents_kwh.get(n.region, 0.0)))
        energy = round(
            exact(kwh / KWH_PER_MWH)
            * exact(balance.refining.power_cents_per_mwh)
            * exact(refinery.power_index(state, n.region, balance, data))
        )
        name = facility_name(f, balance, data)
        if revenue > 0:
            entries.append(
                LedgerEntry(
                    state.turn,
                    n.company_id,
                    f"Charging sales: {name}",
                    (LedgerLine(CASH, revenue), LedgerLine(CHARGING_SALES, -revenue)),
                )
            )
        if energy > 0:
            entries.append(
                LedgerEntry(
                    state.turn,
                    n.company_id,
                    f"Charging energy: {name}",
                    (LedgerLine(COGS, energy), LedgerLine(CASH, -energy)),
                )
            )
        month = ChargingMonth(state.turn, kwh, revenue, energy, use)
        history = (*n.history, month)[-balance.vehicles.history_months :]
        exclusive = n.exclusive
        if exclusive:
            share = (
                live
                / balance.vehicles.scale
                / max(1.0, public_chargers(state, n.region, balance, data))
            )
            if share >= cb.scrutiny_share:
                exclusive = False
                logs.append(
                    inbox_item(
                        state.turn,
                        n.company_id,
                        "charging_opened",
                        network=name,
                        region=data.region(n.region).label,
                        share=f"{share:.0%}",
                    )
                )
        out.append(replace(n, month=month, history=history, exclusive=exclusive))
    return replace(state, charging_networks=tuple(out)), entries, logs
