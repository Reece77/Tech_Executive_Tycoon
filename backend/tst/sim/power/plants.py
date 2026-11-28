"""Owned plants (docs/formulas.md 46.2, 46.5; ADR-0022 4-5): quotes, the month's capex,
completion, connection, depreciation and forced outages, and what a plant can generate and what
its energy costs.

A plant is a `Facility` of kind `plant` with a `Plant` record. Its capex is paid in equal
monthly parts (the true capex over the true build months) until paid; the facility's
`capex_cents` carries the hidden overrun and `Plant.complete_turn` the true completion, so the
quote's date slips month by month as the payments run on (46.9: never shown ahead). It
generates from the later of completion and its grid connection (a behind-the-meter plant needs
none) and depreciates straight-line over its type's life from then. Every money figure is in 2010
dollars, as the game's.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from tst.sim.calendar import format_turn
from tst.sim.commodities import power as m17
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.ledger import ACCUMULATED_DEPRECIATION, CASH, DEPRECIATION, PPE, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.power import draws, grid
from tst.sim.power import formulas as pf
from tst.sim.power.config import FUELLED, PlantTypeDef, interp
from tst.sim.power.models import Plant
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility, with_plant

PLANT_KIND: Final = "plant"  # tunable-exempt: balance.facility.kinds key (module power)
OVERRUN_FAMILY, QUEUE_FAMILY, WORLD_FAMILY = 1, 2, 3  # tunable-exempt: stream power families
HISTORY_YEAR: Final = 2025  # tunable-exempt: the data's last year
MONTHS: Final = 12  # tunable-exempt: calendar
CENTS: Final = 100  # tunable-exempt: cents a dollar
NUCLEAR_TYPES: Final = ("nuclear", "smr")  # tunable-exempt: types that need no fuel price


def type_def(data: GameData, key: str) -> PlantTypeDef:
    assert data.power is not None
    return data.power.plant_type(key)


def learning(state: GameState, key: str) -> float:
    return dict(state.power_world.learning).get(key, 0.0)


def capex_kw(state: GameState, key: str, balance: Balance, data: GameData) -> float:
    """This month's published $/kW for a new plant of type `key` (2010 dollars), with the
    owner's premium: the data's to 2025, then the seeded learning curve."""
    t = type_def(data, key)
    year = grid.year_of(state.turn)
    base = t.capex_at(min(year, HISTORY_YEAR))
    learnt = pf.learnt(base, learning(state, key), year - HISTORY_YEAR)
    # money-exact: rate: $/kW in float dollars
    return learnt * balance.power.plants.capex_premium


def gas_usd(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """A site's gas price, $/MMBtu (2010 dollars): the data's to 2025, then 2025's moved with
    the region's power index (M17's path), plus the delivery adder."""
    assert data.power is not None
    pts = data.power.region(region).gas
    year = grid.year_of(state.turn)
    price = interp(pts, min(year, HISTORY_YEAR))
    if year > HISTORY_YEAR and data.power_history is not None:
        last = data.power_history.region(region).years[HISTORY_YEAR][0]
        price *= m17.index(state, region, data) / last if last else 1.0
    return price + balance.power.plants.gas_adder


def capacity_factor(t: PlantTypeDef, region: str) -> float:
    return t.cf(region)


def marginal_usd_mwh(
    state: GameState, key: str, region: str, balance: Balance, data: GameData
) -> float:
    """A MWh's fuel, variable O&M and carbon this month (2010 dollars)."""
    t = type_def(data, key)
    year = grid.year_of(state.turn)
    out = t.variable_om_at(year)
    if key in FUELLED:
        out += pf.gas_fuel_usd_mwh(t.heat_rate_at(year), gas_usd(state, region, balance, data))
        out += t.intensity_at(year) * grid.carbon_price(state, region, data)
    elif key in NUCLEAR_TYPES:
        out += t.fuel_mwh
    return out


def fixed_usd_month(t: PlantTypeDef, mw: float, year: int) -> float:
    return mw * pf.KW_PER_MW * t.fixed_om_at(year) / MONTHS


def levelised(state: GameState, key: str, region: str, balance: Balance, data: GameData) -> float:
    """46.6: a new plant's levelised cost this month, $/MWh (2010 dollars)."""
    t = type_def(data, key)
    year = grid.year_of(state.turn)
    return pf.levelised_usd_mwh(
        capex_kw(state, key, balance, data),
        t.fixed_om_at(year),
        capacity_factor(t, region),
        marginal_usd_mwh(state, key, region, balance, data),
        balance.power.plants.discount_rate,
        t.life_years,
    )


def available(state: GameState, key: str, data: GameData) -> bool:
    """Whether a type can be ordered this month: an SMR only from its seeded era."""
    t = type_def(data, key)
    if t.era is None:
        return True
    year = state.power_world.smr_year
    return year is not None and grid.year_of(state.turn) >= year


def plants_unlocked(state: GameState, company_id: int, balance: Balance) -> bool:
    """46.2: owned plants from stage 4 (Reece, 2026-11-13)."""
    company = state.company(company_id)
    return company.stage >= balance.power.plants.min_stage


@dataclass(frozen=True, slots=True)
class PlantQuote:
    """What an order would cost and do (46.2, 46.6): the published figures only."""

    type: str
    label: str
    mw: float
    region: str
    capex_cents: int
    monthly_capex_cents: int
    build_months: int
    ready_turn: int
    capacity_factor: float
    mwh_year: float
    levelised_usd_mwh: float
    intensity: float  # tCO2 a MWh
    behind_meter: bool


def quote(
    state: GameState,
    key: str,
    mw: float,
    region: str,
    behind_meter: bool,
    balance: Balance,
    data: GameData,
) -> PlantQuote:
    t = type_def(data, key)
    year = grid.year_of(state.turn)
    capex = round(capex_kw(state, key, balance, data) * mw * pf.KW_PER_MW * CENTS)
    cf = capacity_factor(t, region)
    return PlantQuote(
        type=key,
        label=t.label,
        mw=mw,
        region=region,
        capex_cents=capex,
        monthly_capex_cents=-(-capex // t.build_months),
        build_months=t.build_months,
        ready_turn=state.turn + t.build_months,
        capacity_factor=cf,
        mwh_year=mw * pf.HOURS_A_YEAR * cf,
        levelised_usd_mwh=levelised(state, key, region, balance, data),
        intensity=t.intensity_at(year),
        behind_meter=behind_meter,
    )


def draw_overrun(rng: RngFactory, turn: int, facility_id: int, key: str, balance: Balance) -> float:
    """The hidden overrun (stream power (1, facility) in the order month)."""
    span = balance.power.plants.overrun[key]
    u = float(draws.gen(rng, turn, OVERRUN_FAMILY, facility_id).random())
    return pf.overrun(span.lo, span.hi, u, balance.power.plants.overrun_skew)


def true_months(key: str, build_months: int, overrun: float, balance: Balance) -> int:
    return max(1, round(build_months * (1 + overrun * balance.power.plants.overrun_delay[key])))


def plant_of(state: GameState, facility_id: int) -> Plant | None:
    return next((p for p in state.plants if p.facility_id == facility_id), None)


def facility_of(state: GameState, plant: Plant) -> Facility:
    f = state.facility(plant.facility_id)
    assert f is not None
    return f


def plant_name(state: GameState, plant: Plant, data: GameData) -> str:
    f = facility_of(state, plant)
    where = (
        data.city(f.city).label if f.city and data.has_city(f.city) else data.region(f.region).label
    )
    return f"{type_def(data, plant.type).label} plant, {where} ({plant.mw:,.0f} MW)"


def energy_mwh(state: GameState, plant: Plant, balance: Balance, data: GameData) -> float:
    """What a live plant can generate this month: MW x hours x its capacity factor (none in a
    forced outage). Gas is dispatchable up to this (settle decides)."""
    if not plant.live(state.turn) or plant.offline(state.turn):
        return 0.0
    f = facility_of(state, plant)
    cf = capacity_factor(type_def(data, plant.type), f.region)
    return plant.mw * balance.power.hours_a_month * cf


def plants_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Phase 4 (before production): every plant's capex, completion, connection, depreciation
    and forced-outage draw."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    turn = state.turn
    pb = balance.power.plants
    for plant in state.plants:
        f = facility_of(state, plant)
        if f.status == "closed":
            continue
        name = plant_name(state, plant, data)
        t = type_def(data, plant.type)
        # capex: equal parts until paid (the overrun runs the payments on)
        if f.capex_paid_cents < f.capex_cents:
            pay = min(plant.monthly_capex_cents, f.capex_cents - f.capex_paid_cents)
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=f.company_id,
                    memo=f"Capex: {name}",
                    debit=PPE,
                    credit=CASH,
                    amount=pay,
                )
            )
            f = replace(f, capex_paid_cents=f.capex_paid_cents + pay)
            if f.capex_paid_cents < f.capex_cents and f.ready_turn <= turn:
                f = replace(f, ready_turn=turn + 1, late_turn=turn + 1)  # the date slips
        built = f.capex_paid_cents >= f.capex_cents and turn >= plant.complete_turn
        if built and plant.live_turn is None:
            if plant.connected:
                plant = replace(plant, live_turn=turn)
                f = replace(f, status="live", ready_turn=turn, late_turn=turn)
                logs.append(inbox_item(turn, f.company_id, "plant_live", plant=name))
            elif f.ready_turn <= turn:
                f = replace(f, ready_turn=turn + 1, late_turn=turn + 1)  # waiting for the grid
        if plant.live(turn):
            life = t.life_years * MONTHS
            months = turn - (plant.live_turn if plant.live_turn is not None else turn) + 1
            total = min(f.capex_paid_cents, f.capex_paid_cents * months // life)
            charge = total - f.depreciated_cents
            if charge > 0:
                entries.append(
                    LedgerEntry.transfer(
                        turn=turn,
                        company_id=f.company_id,
                        memo=f"Depreciation: {name}",
                        debit=DEPRECIATION,
                        credit=ACCUMULATED_DEPRECIATION,
                        amount=charge,
                    )
                )
                f = replace(f, depreciated_cents=total)
            if not plant.offline(turn) and plant.live_turn is not None and plant.live_turn < turn:
                gen = draws.gen(rng, turn, OVERRUN_FAMILY, plant.facility_id)
                u, v = (float(x) for x in gen.random(2))
                if u < pb.outages_a_year[plant.type] / MONTHS:
                    span = pb.outage_months[plant.type]
                    n = int(span.lo) + min(int(span.hi - span.lo), int(v * (span.hi - span.lo + 1)))
                    plant = replace(plant, outage_until=turn + n - 1)
                    logs.append(
                        inbox_item(
                            turn,
                            f.company_id,
                            "plant_outage",
                            plant=name,
                            until=format_turn(turn + n - 1),
                        )
                    )
        state = with_facility(state, f)
        state = with_plant(state, plant)
    return state, entries, logs


def draw_world(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """The game-wide draws at power.plants.smr_start (stream power (3, type_index)): each type's
    yearly learning after 2025 and the SMR era's first year (46.2). Drawn once."""
    if data.power is None or state.power_world.learning:
        return state
    if state.turn < month_to_turn(balance.power.plants.smr_start):
        return state
    learning_: list[tuple[str, float]] = []
    smr_year = None
    for i, t in enumerate(data.power.plant_types):
        gen = draws.gen(rng, state.turn, WORLD_FAMILY, i)
        u, v = (float(x) for x in gen.random(2))
        span = balance.power.plants.learning[t.key]
        learning_.append((t.key, span.lo + (span.hi - span.lo) * u))
        if t.era is not None:
            lo, hi = t.era
            smr_year = lo + min(hi - lo, int(v * (hi - lo + 1)))
    return replace(
        state,
        power_world=replace(state.power_world, learning=tuple(learning_), smr_year=smr_year),
    )
