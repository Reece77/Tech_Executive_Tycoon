"""Siting (docs/formulas.md 46.6): what the build screens show for each candidate city when
ordering a data centre or fab: the grid price now, the queue wait as a range (when the
facility would queue), the carbon price, the outage rate, whether a plant can sit behind its
meter, and the cheapest new plant's levelised cost there. Published figures only (46.9): no
seeded future price, no queue draw.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.power import grid, outages, plants, queues
from tst.sim.state import GameState

CENTS: Final = 100  # tunable-exempt: cents a dollar
PLANT_CHOICES: Final = ("gas", "solar_storage", "wind")  # tunable-exempt: the cheapest-plant set


@dataclass(frozen=True, slots=True)
class Site:
    city: str
    label: str
    region: str
    region_label: str
    price_usd_mwh: float
    queue_lo: float | None  # months; None when the facility would not queue
    queue_hi: float | None
    carbon_usd_t: float
    outages_a_year: float
    behind_meter: bool
    cheapest_plant: str
    cheapest_usd_mwh: float


def draw_mw(kind: str, capacity: float, balance: Balance, data: GameData) -> float:
    """A planned facility's draw in MW: data centres by their power.yaml draw; a fab by its
    starts x the leading node's MWh a start (fab.power_mwh's base + 2 generations, A)."""
    if data.power is None:
        return 0.0
    hours = balance.power.hours_a_month
    if kind in data.power.draws:
        return capacity * data.power.draws[kind] / hours
    pm = balance.fab.power_mwh
    return capacity * (pm.base + pm.per_generation * 2) / hours


def sites(
    state: GameState,
    company_id: int,
    kind: str,
    capacity: float,
    balance: Balance,
    data: GameData,
) -> list[Site]:
    if data.power is None:
        return []
    mw = draw_mw(kind, capacity, balance, data)
    queues_now = (
        state.turn >= month_to_turn(balance.power.start) and mw > balance.power.queue.min_mw
    )
    btm = plants.plants_unlocked(state, company_id, balance)
    out: list[Site] = []
    per_region: dict[str, tuple[float, float, float, str, float]] = {}
    for r in data.region_keys:
        price = grid.price_cents(state, r, balance, data) / CENTS
        carbon = grid.carbon_price(state, r, data)
        rate = outages.rate(state, r, balance, data)
        costs = {k: plants.levelised(state, k, r, balance, data) for k in PLANT_CHOICES}
        best = min(costs, key=lambda k: costs[k])
        per_region[r] = (price, carbon, rate, best, costs[best])
    for city in data.cities:
        r = city.region
        if r not in per_region:
            continue
        price, carbon, rate, best, cost = per_region[r]
        lo = hi = None
        if queues_now:
            lo, hi = queues.shown_range(queues.median_months(state, r, data), balance)
        out.append(
            Site(
                city=city.key,
                label=city.label,
                region=r,
                region_label=data.region(r).label,
                price_usd_mwh=price,
                queue_lo=lo,
                queue_hi=hi,
                carbon_usd_t=carbon,
                outages_a_year=rate,
                behind_meter=btm,
                cheapest_plant=best,
                cheapest_usd_mwh=cost,
            )
        )
    return out
