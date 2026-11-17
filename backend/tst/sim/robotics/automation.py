"""Robots in the player's own plants (docs/formulas.md 53.1).

A plant of a kind in `automation.plant_kinds` (assembly and vehicle plants) can install robots,
the group's own (an own live industrial robot line: its unit cost plus integration) or bought
(the market's system price: robotics.yaml's robot price x `system_mult`). For a plant of capacity
C (units a month) in region r:

    line workers at full capacity  W = C x workers_per_unit[kind]
    labour replaced                D = min(robots x labour_per_robot, W x max_share)
    automation level               a = D / W
    saving a unit run              s = a x min(variable_cents x labour_share[kind],
                                               workers_per_unit[kind] x wage(r) x hours_per_month)

so a robot saves a worker's labour at the region's wage (robotics.yaml labour cost an hour), never
more than the plant's line labour: automation pays where labour is dear (53.4 target 2). The plant
cost model reads `s` (`unit_saving_cents`, tst.sim.hardware.production): it comes off the
variable cost of every unit the plant runs. Robots depreciate over `life_months` (6700 against
1510) and cost `service_share` of the robot's price a year (5000). Full automation removes
`defect_cut` of the plant's yield loss (output consistency). A plant without robots is untouched.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.models import Facility
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    COGS,
    DEPRECIATION,
    LedgerEntry,
    LedgerLine,
)
from tst.sim.money import exact
from tst.sim.robotics.data import MONTHS, TINY, file, year_at
from tst.sim.robotics.models import AutomationMonth, PlantAutomation
from tst.sim.state import GameState, with_facility

YIELD_CAP: Final = 0.995  # tunable-exempt: a yield stays below 1


def wage_month_cents(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """A line worker's labour cost a month in the region (2010 cents)."""
    hours = balance.robotics.automation.hours_per_month
    return file(data).region(region).labour_at(year_at(state.turn)) * hours


def line_workers(facility: Facility, balance: Balance) -> float:
    ab = balance.robotics.automation
    return facility.capacity * ab.workers_per_unit.get(facility.kind, 0.0)


def level_of(facility: Facility, robots: int, balance: Balance) -> float:
    ab = balance.robotics.automation
    workers = line_workers(facility, balance)
    if workers <= TINY:
        return 0.0
    replaced = min(robots * ab.labour_per_robot, workers * ab.max_share)
    return replaced / workers


def robots_for(facility: Facility, level: float, balance: Balance) -> int:
    """Robots a plant needs for an automation level (the most `max_share` allows)."""
    ab = balance.robotics.automation
    level = min(level, ab.max_share)
    return int(-(-line_workers(facility, balance) * level // ab.labour_per_robot))


def saving_cents(
    state: GameState, facility: Facility, level: float, balance: Balance, data: GameData
) -> float:
    """Line labour saved a unit run at an automation level (module docstring)."""
    ab = balance.robotics.automation
    kind = balance.facility.kinds[facility.kind]
    plant_labour = kind.variable_cents * ab.labour_share.get(facility.kind, 0.0)
    regional = ab.workers_per_unit.get(facility.kind, 0.0) * wage_month_cents(
        state, facility.region, balance, data
    )
    return level * min(plant_labour, regional)


def robot_price_cents(state: GameState, data: GameData) -> float:
    """A bought robot's price (arm and controller) this month, 2010 cents."""
    return file(data).prices.robot_at(year_at(state.turn))


def system_cents(state: GameState, data: GameData) -> float:
    """A bought robot installed: its price x the system multiple (integration, tooling)."""
    # money-exact: rate (a robot's installed price, rounded where an order is posted)
    return robot_price_cents(state, data) * file(data).prices.system_mult


def unit_saving_cents(state: GameState, facility_id: int) -> float:
    """The plant hook (53.1): line labour the plant's robots save a unit run this month."""
    a = state.plant_automation(facility_id)
    return a.unit_saving_cents if a is not None else 0.0


def production_month(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Phase 4, after the plants' yields: each automated plant's saving a unit and its yield."""
    if not state.plant_automations:
        return state
    cut = balance.robotics.automation.defect_cut
    out = []
    for a in state.plant_automations:
        f = state.facility(a.facility_id)
        if f is None or f.status != "live":
            out.append(replace(a, unit_saving_cents=0.0))
            continue
        level = level_of(f, a.robots, balance)
        saving = saving_cents(state, f, level, balance, data)
        out.append(replace(a, unit_saving_cents=saving))
        if f.yield_rate > 0 and level > 0:
            better = f.yield_rate + cut * level * (1 - f.yield_rate)
            state = with_facility(state, replace(f, yield_rate=min(YIELD_CAP, better)))
    return replace(state, plant_automations=tuple(out))


def after_sales(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    """After the month's sales: each automated plant's month (units run, labour saved), its
    robots' service and depreciation; a plant that is gone writes its robots off."""
    if not state.plant_automations:
        return state, []
    ab = balance.robotics.automation
    keep = balance.robotics.history_months
    entries: list[LedgerEntry] = []
    out: list[PlantAutomation] = []
    for a in state.plant_automations:
        f = state.facility(a.facility_id)
        book = a.capex_cents - a.depreciated_cents
        if f is None or f.status == "closed":
            if book > 0:
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn,
                        company_id=a.company_id,
                        memo="Robots written off with their plant",
                        debit=DEPRECIATION,
                        credit=ACCUMULATED_DEPRECIATION,
                        amount=book,
                    )
                )
            continue
        name = f"plant {f.id}"
        units = float(f.run_units) + float(f.sold_units)
        saved = round(exact(units) * exact(a.unit_saving_cents))
        service = round(
            exact(a.robots)
            * exact(robot_price_cents(state, data))
            * exact(file(data).prices.service_share)
            / MONTHS
        )
        dep = min(book, round(exact(a.capex_cents) / exact(ab.life_months)))
        if service > 0:
            entries.append(
                LedgerEntry(
                    state.turn,
                    a.company_id,
                    f"Robot service: {name}",
                    (LedgerLine(COGS, service), LedgerLine(CASH, -service)),
                )
            )
        if dep > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=a.company_id,
                    memo=f"Depreciation: robots in {name}",
                    debit=DEPRECIATION,
                    credit=ACCUMULATED_DEPRECIATION,
                    amount=dep,
                )
            )
        month = AutomationMonth(
            turn=state.turn,
            units=units,
            saved_cents=saved,
            service_cents=service,
            depreciation_cents=dep,
            level=level_of(f, a.robots, balance),
        )
        history = tuple(m for m in a.history if m.turn > state.turn - keep)
        out.append(
            replace(
                a,
                depreciated_cents=a.depreciated_cents + dep,
                month=month,
                history=(*history, month)[-keep:],
            )
        )
    return replace(state, plant_automations=tuple(out)), entries


def unit_cost_report(
    state: GameState, facility: Facility, robots: int, balance: Balance, data: GameData
) -> dict[str, float]:
    """A plant's conversion cost a unit at full use with `robots` robots (53.4 target 2, the
    Explain panel): line labour, fixed cost, plant depreciation, and the robots' share."""
    kind = balance.facility.kinds[facility.kind]
    cap = max(1, facility.capacity)
    level = level_of(facility, robots, balance)
    saved = saving_cents(state, facility, level, balance, data)
    # money-exact: estimate (the Explain panel's and 53.4's cost a unit; nothing posts from it)
    plant_dep = facility.capex_cents / kind.life_months / cap if kind.life_months else 0.0
    price = robot_price_cents(state, data)
    service_share = file(data).prices.service_share / MONTHS
    life = balance.robotics.automation.life_months
    # money-exact: estimate (as above)
    dep = system_cents(state, data) / life
    # money-exact: estimate (as above)
    service = price * service_share
    robot_month = robots * (dep + service)
    return {
        "labour": kind.variable_cents - saved,
        # money-exact: estimate (as above)
        "fixed": kind.fixed_opex_cents / cap,
        "depreciation": plant_dep,
        "robots": robot_month / cap,
        "level": level,
        "saved": saved,
    }
