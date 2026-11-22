"""Autonomy's approvals and incidents (docs/formulas.md 49.4).

**Approvals.** To December 2025 a region approves a level in the data's month (vehicles.yaml
regulators). From `vehicles.start`, each December a region that has not approved a level does so
for the next January with `approval_chance[level]` (stream vehicles (0, region_index, 1 + level
index)); approvals are public once made, and the chance is not shown ahead.

**Incidents.** Each month a player line whose cars run L3 or L4 in a region has a Poisson number of
incidents with mean `cars on the road there x incident_rate / 12 / 100,000` (stream vehicles (1,
product_id, region_index), a region's own draw, M43r). An incident recalls the region's cars
running the level (`recall_cents` each, 6900), costs the line `brand_points` of brand, and the
region's regulator suspends the level for the company's cars for `suspend_months`. The draw and
the mean are never stored or shown; the incident is, once it has happened.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.ledger import CASH, GENERAL_ADMIN, LedgerEntry, LedgerLine
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, player_companies, with_product
from tst.sim.vehicles import draws
from tst.sim.vehicles import spec as vs
from tst.sim.vehicles.config import LEVELS
from tst.sim.vehicles.data import is_vehicle
from tst.sim.vehicles.models import Incident, Suspension

DECEMBER: Final = 12  # tunable-exempt: calendar
PER_CARS: Final = 100_000  # tunable-exempt: incident rates are per 100,000 cars a year
MONTHS: Final = 12  # tunable-exempt: calendar


def december_approvals(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    vb = balance.vehicles
    if state.turn < vb.start_turn - 1 or turn_to_ym(state.turn)[1] != DECEMBER:
        return state, []
    approved = list(state.vehicle_world.approved)
    logs: list[LogItem] = []
    for i, region in enumerate(data.region_keys):
        for j, level in enumerate(LEVELS):
            chance = vb.approval_chance.get(level)
            if chance is None or vs.approved(state, region, level, balance, data):
                continue
            if any(r == region and lv == level for r, lv, _ in approved):
                continue
            u = float(draws.gen(rng, state.turn, draws.WORLD, i, 1 + j).random())
            if u < chance:
                approved.append((region, level, state.turn + 1))
                logs.append(
                    inbox_item(
                        state.turn,
                        state.player.id,
                        "autonomy_approved",
                        region=data.region(region).label,
                        level=vb.levels[level].label,
                    )
                )
    world = replace(state.vehicle_world, approved=tuple(approved))
    return replace(state, vehicle_world=world), logs


def cars_on_road(
    state: GameState, product_id: int, region: str, balance: Balance, data: GameData
) -> float:
    home = home_region_of(state, balance, data)
    cat = data.category(balance.vehicles.category)
    total = 0.0
    if region == home:
        for s in state.segments_of(product_id):
            total += s.customers * cat.market(s.segment).units_per_customer
    for rs in state.regional_segments_of(product_id):
        if rs.region == region:
            total += rs.customers * cat.market(rs.segment).units_per_customer
    return total


def incidents_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    vb = balance.vehicles
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    players = {c.id for c in player_companies(state)}
    for product in sorted(state.products, key=lambda p: p.id):
        if product.company_id not in players or not is_vehicle(product, balance):
            continue
        if product.status not in ("live", "sunset"):
            continue
        spec = vs.spec_of(state, product, data)
        capable = vs.capable_level(state, spec, product.company_id, balance)
        if vb.levels[capable].incident_rate <= 0:
            continue
        for i, region in enumerate(data.region_keys):
            level = vs.level_in(state, product, region, balance, data, capable)
            rate = vb.levels[level].incident_rate
            cars = cars_on_road(state, product.id, region, balance, data)
            if rate <= 0 or cars <= 0:
                continue
            gen = draws.gen(rng, state.turn, draws.INCIDENT, product.id, i)
            n = int(gen.poisson(cars * rate / MONTHS / PER_CARS))
            if n <= 0:
                continue
            cost = round(exact(cars) * vb.incident.recall_cents)
            if cost > 0:
                entries.append(
                    LedgerEntry(
                        state.turn,
                        product.company_id,
                        f"Recall: {product.name} ({vb.levels[level].label})",
                        (LedgerLine(GENERAL_ADMIN, cost), LedgerLine(CASH, -cost)),
                    )
                )
            current = state.product(product.id)
            assert current is not None
            state = with_product(
                state, replace(current, brand=max(0.0, current.brand - vb.incident.brand_points))
            )
            world = state.vehicle_world
            sus = Suspension(
                product.company_id, region, level, state.turn + vb.incident.suspend_months
            )
            world = replace(world, suspensions=(*world.suspensions, sus))
            state = replace(
                state,
                vehicle_world=world,
                incidents=(
                    *state.incidents,
                    Incident(state.turn, product.id, product.company_id, region, level, cars, cost),
                )[-vb.history_months :],
            )
            logs.append(
                inbox_item(
                    state.turn,
                    product.company_id,
                    "autonomy_incident",
                    product=product.name,
                    region=data.region(region).label,
                    level=vb.levels[level].label,
                    cars=f"{round(cars):,}",
                    cost_cents=cost,
                    months=vb.incident.suspend_months,
                )
            )
    # suspensions past their end leave the state
    world = state.vehicle_world
    live = tuple(s for s in world.suspensions if s.until_turn > state.turn)
    if live != world.suspensions:
        state = replace(state, vehicle_world=replace(world, suspensions=live))
    return state, entries, logs
