"""Battery cells (docs/formulas.md 49.2): the market price, its learning curve after 2025, and the
player's own cell plants.

**The market price** is the `battery_cells` commodity's (M17, 33.1), a kWh in 2010 dollars: the
history is BNEF's pack price x the cells' share of a pack (vehicles.yaml, checked at load). From
`vehicles.start` the commodity's seeded path reverts to the learning curve (`learning_level`)
instead of its history's mean:

    level = p_2025 x ((1 - m) x (C / C_2025) ^ log2(1 - rate) + m x metals now / metals 2025)

with `C` the world's cumulative EV cells (vehicles.yaml to 2025, then growing with the world's
EV sales), `rate` drawn once (stream vehicles (0, n_regions)), `m` = `learning.metals_share` and
the metals an NMC kWh's lithium, nickel and cobalt at this month's prices; never below
`learning.floor_cents`.

**An own cell plant** (a facility of kind `cell_plant`, stage 4; generic capex, depreciation and
staff) makes `capacity (MWh/month) x 1,000 x staff coverage x yield` kWh a month, with yield
learning as a fab's (38.2): `mature - (mature - start) x (1 - learn x skill / skill_ref) ^ months`.
Each kWh made takes its chemistry's materials / yield, bought at spot (the group's refineries and
mines supply them first through M20's own supply: a cell plant's inputs count as its company's
commodity use), power at the region's grid price, other costs at `other_share` x the market price,
and fixed costs a year of `fixed_share` x capex; all post to 5000 in the month. Its output goes to
the group's car lines on own cells (`CellLot`s for the kWh their last month's cars took), and the
rest sells at spot (4410). After the month's sales (`settle`) a lot is taken up to the kWh its
line's cars used: the car paid the market price for its cells at sale, which is reversed, and a
sister company pays the transfer price (5900/4300, consolidated away); what is not taken sells at
spot.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Final

from tst.sim import dmath
from tst.sim.commodities import commodity
from tst.sim.commodities.offtake import usd_per_unit
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.lifecycle import facility_name, staffing
from tst.sim.facilities.models import Facility
from tst.sim.ledger import CASH, COGS, MATERIALS_SALES, LedgerEntry, LedgerLine
from tst.sim.log import LogItem
from tst.sim.money import exact
from tst.sim.refining import goods as rg
from tst.sim.refining import plants as refinery
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, group_companies
from tst.sim.vehicles import draws
from tst.sim.vehicles.config import OWN, interp
from tst.sim.vehicles.data import MONTHS, TINY, file, year_at
from tst.sim.vehicles.models import CellLot, CellPlant, CellPlantMonth

KWH_PER_MWH: Final = 1000  # tunable-exempt: unit conversion
GWH_PER_KWH: Final = 1e-6  # tunable-exempt: unit conversion
METALS: Final = ("lithium_carbonate", "nickel", "cobalt")  # tunable-exempt: 49.2's metals
NMC: Final = "nmc"  # tunable-exempt: the metals basket is an NMC kWh's
CENTS: Final = 100  # tunable-exempt: dollars to cents
MAX_RATE: Final = 0.99  # tunable-exempt: learning never takes the whole gap in a month
MIN_YIELD: Final = 0.05  # tunable-exempt: a plant's yield floor after noise


def history_cell_cents(turn: int, data: GameData) -> float:
    """A kWh of cells in the history (2010 cents): pack price x cell share."""
    b = file(data).battery
    year = year_at(turn)
    return b.pack_at(year) * b.cell_share_at(year)


def market_cents(state: GameState, balance: Balance, data: GameData) -> float:
    """This month's market price of a kWh of cells (cents, 2010 dollars)."""
    return rg.price_cents(state, balance.vehicles.cell_good, balance, data)


def history_cumulative_gwh(data: GameData) -> float:
    """The world's EV cells made 2010-2025, GWh (vehicles.yaml, linear between its years)."""
    points = file(data).world_cells_gwh
    return sum(interp(points, y) for y in range(min(points), max(points) + 1))


def year_gwh(state: GameState, balance: Balance, data: GameData) -> float:
    """The world's EV cells a year after 2025: 2025's x the world's EV sales over 2025's."""
    from tst.sim.vehicles import demand

    v = file(data)
    base_year = max(v.world_cells_gwh)
    now = sum(demand.ev_sales_year(state, r, balance, data) for r in data.region_keys)
    then = sum(
        demand.car_sales(r, balance.vehicles.start_turn - 1, data)
        * balance.vehicles.scale
        * v.region(r).share_at(year_at(balance.vehicles.start_turn - 1))
        for r in data.region_keys
    )
    return v.world_cells_gwh[base_year] * (now / then if then > TINY else 1.0)


def metals_cents(
    state: GameState, balance: Balance, data: GameData, turn: int | None = None
) -> float:
    """An NMC kWh's lithium, nickel and cobalt (cents): at a history month's prices with `turn`,
    else at this month's."""
    chem = file(data).battery.chemistries[NMC]
    total = 0.0
    for good in METALS:
        q = chem.inputs.get(good, 0.0)
        if not q:
            continue
        if turn is None:
            total += q * rg.price_cents(state, good, balance, data)
        else:
            price = commodity.price(state, good, turn, data, balance)
            total += q * price * usd_per_unit(good, data) * CENTS
    return total


def learning_level(state: GameState, balance: Balance, data: GameData) -> float | None:
    """The learning curve's price a kWh (module docstring); None before it starts."""
    vb = balance.vehicles
    world = state.vehicle_world
    if state.turn < vb.start_turn or world.learning_rate is None:
        return None
    last = vb.start_turn - 1
    base = history_cell_cents(last, data)
    cum = max(world.cumulative_gwh, world.base_cumulative_gwh)
    exp = dmath.log2(1 - world.learning_rate)
    learned = (
        dmath.pow(cum / world.base_cumulative_gwh, exp) if world.base_cumulative_gwh > 0 else 1.0
    )
    m = vb.learning.metals_share
    then = metals_cents(state, balance, data, last)
    now = metals_cents(state, balance, data)
    metals = now / then if then > TINY else 1.0
    return max(vb.learning.floor_cents, base * ((1 - m) * learned + m * metals))


def commodity_level(
    state: GameState, mean: float, balance: Balance, data: GameData
) -> float | None:
    """M17's AR(1) reversion level for battery cells (the hook in commodity_month): the learning
    curve's price over the history's mean, in the history's unit ($ a kWh)."""
    level = learning_level(state, balance, data)
    return None if level is None or mean <= 0 else level / 100 / mean


# --- Own cell plants ------------------------------------------------------------------------------


def plant_yield(
    cp: CellPlant, facility: Facility, state: GameState, z: float, balance: Balance
) -> float:
    cb = balance.vehicles.cell_plant
    skill = staffing(state, facility, balance).mean_skill
    rate = min(MAX_RATE, cb.learn * max(skill, 1.0) / cb.skill_ref)
    y = cb.yield_mature - (cb.yield_mature - cb.yield_start) * dmath.pow(1 - rate, cp.months_run)
    return max(MIN_YIELD, min(cb.yield_mature, y * (1 + cb.noise_sd * z)))


def _want(state: GameState, product_id: int, data: GameData) -> float:
    """kWh a car line on own cells wants this month: last month's cars x its pack."""
    spec = state.vehicle_spec(product_id)
    if spec is None or spec.cells != OWN:
        return 0.0
    last = [m for m in state.vehicle_months if m.product_id == product_id]
    units = last[-1].units if last else 0.0
    return units * spec.pack_kwh


def _entry(turn: int, company: int, memo: str, account: str, amount: int) -> LedgerEntry:
    return LedgerEntry(
        turn, company, memo, (LedgerLine(account, amount), LedgerLine(CASH, -amount))
    )


def run_plants(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Phase 4: every live cell plant's month and its lots (module docstring)."""
    if not state.cell_plants:
        return state, [], []
    entries: list[LedgerEntry] = []
    turn = state.turn
    cb = balance.vehicles.cell_plant
    market = market_cents(state, balance, data)
    plants: list[CellPlant] = []
    lots: list[CellLot] = []
    wanted: dict[int, float] = {}
    for cp in sorted(state.cell_plants, key=lambda c: c.facility_id):
        f = state.facility(cp.facility_id)
        if f is None or f.status == "closed":
            continue
        live = f.live_capacity(turn)
        if live <= 0:
            plants.append(cp)
            continue
        z = float(draws.gen(rng, turn, draws.CELL_PLANT, f.id).standard_normal())
        y = plant_yield(cp, f, state, z, balance)
        cover = staffing(state, f, balance).coverage
        capacity = live * KWH_PER_MWH * cover
        made = capacity * y
        chem = file(data).battery.chemistries[cp.chemistry]
        inputs = tuple((g, q * made / y) for g, q in sorted(chem.inputs.items()) if y > 0)
        input_cents = round(
            sum(
                (exact(vol) * exact(rg.price_cents(state, g, balance, data)) for g, vol in inputs),
                exact(0),
            )
        )
        power = round(
            exact(made * cb.mwh_per_kwh)
            * exact(balance.refining.power_cents_per_mwh)
            * exact(refinery.power_index(state, f.region, balance, data))
        )
        other = round(exact(made) * exact(market) * exact(cb.other_share))
        fixed = round(exact(f.capex_paid_cents) * exact(cb.fixed_share) / MONTHS)
        name = facility_name(f, balance, data)
        for memo, amount in (
            (f"Cell materials: {name}", input_cents),
            (f"Cell plant power: {name}", power),
            (f"Cell plant running costs: {name}", other + fixed),
        ):
            if amount > 0:
                entries.append(_entry(turn, cp.company_id, memo, COGS, amount))
        life = balance.facility.kinds[f.kind].life_months
        # money-exact: rate (a kWh's cost for the Vehicles screen and the transfer price)
        depreciation = f.capex_paid_cents / life if life else 0.0
        total = input_cents + power + other + fixed + depreciation
        unit = total / made if made > TINY else 0.0
        month = CellPlantMonth(
            turn=turn,
            capacity_kwh=capacity,
            made_kwh=made,
            inputs=inputs,
            input_cents=input_cents,
            power_cents=power,
            other_cents=other,
            fixed_cents=fixed,
            unit_cents=unit,
            yield_rate=y,
        )
        # lots to the group's lines on own cells, product id order
        left = made
        group = [c.id for c in group_companies(state, cp.company_id)]
        for cid in group:
            for p in sorted(state.company_products(cid), key=lambda p: p.id):
                if left <= TINY or p.status != "live":
                    continue
                want = _want(state, p.id, data) - wanted.get(p.id, 0.0)
                take = min(left, max(0.0, want))
                if take <= TINY:
                    continue
                price = refinery.transfer_cents(state, cp.company_id, cid, unit, market, balance)
                lots.append(CellLot(turn, f.id, cp.company_id, cid, p.id, take, price, market))
                wanted[p.id] = wanted.get(p.id, 0.0) + take
                left -= take
        month = replace(month, to_group=made - left)
        plants.append(replace(cp, months_run=cp.months_run + 1, yield_rate=y, month=month))
    others = {c.facility_id for c in plants}
    kept = tuple(c for c in state.cell_plants if c.facility_id not in others)
    return (
        replace(
            state,
            cell_plants=tuple(sorted((*kept, *plants), key=lambda c: c.facility_id)),
            cell_lots=tuple(lots),
        ),
        entries,
        [],
    )


def kwh_used(state: GameState, product_id: int) -> float:
    """kWh in this month's cars of the line (from its vehicle month)."""
    spec = state.vehicle_spec(product_id)
    row = next(
        (m for m in state.vehicle_months if m.product_id == product_id and m.turn == state.turn),
        None,
    )
    if spec is None or row is None:
        return 0.0
    return row.units * spec.pack_kwh


def settle(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    """Phase 5 after the cars' month: lots taken, the market price reversed, transfers and spot
    sales (module docstring)."""
    turn = state.turn
    entries: list[LedgerEntry] = []
    left: dict[int, float] = {}
    settled: list[CellLot] = []
    spot: dict[int, Fraction] = {}
    for lot in state.cell_lots:
        if lot.turn != turn:
            continue
        if lot.product_id not in left:
            left[lot.product_id] = kwh_used(state, lot.product_id)
        taken = min(lot.kwh, left[lot.product_id])
        left[lot.product_id] -= taken
        at_market = round(exact(taken) * exact(lot.market_cents))
        if at_market > 0:  # the car paid the market price for these cells at sale
            entries.append(
                LedgerEntry(
                    turn,
                    lot.buyer_id,
                    "Own cells in cars",
                    (LedgerLine(CASH, at_market), LedgerLine(COGS, -at_market)),
                )
            )
        entries += refinery.intercompany(
            turn,
            lot.seller_id,
            lot.buyer_id,
            "Own-group cells",
            round(exact(taken) * exact(lot.unit_cents)),
        )
        spot[lot.facility_id] = spot.get(lot.facility_id, Fraction()) + exact(
            lot.kwh - taken
        ) * exact(lot.market_cents)
        settled.append(replace(lot, taken=taken))
    # every plant's kWh not lotted sells at spot too
    plants = []
    for cp in state.cell_plants:
        m = cp.month
        if m is None or m.turn != turn:
            plants.append(cp)
            continue
        unlotted = m.made_kwh - m.to_group
        back = sum(x.kwh - x.taken for x in settled if x.facility_id == cp.facility_id)
        cents = spot.get(cp.facility_id, Fraction()) + exact(unlotted) * exact(
            market_cents(state, balance, data)
        )
        amount = round(cents)
        f = state.facility(cp.facility_id)
        if amount > 0 and f is not None:
            entries.append(
                LedgerEntry(
                    turn,
                    cp.company_id,
                    f"Cells sold: {facility_name(f, balance, data)}",
                    (LedgerLine(CASH, amount), LedgerLine(MATERIALS_SALES, -amount)),
                )
            )
        m = replace(m, to_group=m.to_group - back, to_spot=unlotted + back, revenue_cents=amount)
        history = (*cp.history, m)[-balance.vehicles.history_months :]
        plants.append(replace(cp, month=m, history=history))
    state = replace(state, cell_lots=tuple(settled), cell_plants=tuple(plants))
    return state, entries


def own_kwh(state: GameState, product_id: int) -> float:
    return sum(
        lot.taken
        for lot in state.cell_lots
        if lot.product_id == product_id and lot.turn == state.turn
    )


def company_use(state: GameState, company_id: int) -> dict[str, float]:
    """The company's cell plants' commodity use in their latest month (M20's group supply)."""
    out: dict[str, float] = {}
    for cp in state.cell_plants:
        if cp.company_id != company_id or cp.month is None:
            continue
        for good, vol in cp.month.inputs:
            out[good] = out.get(good, 0.0) + vol
    return out


def cell_sources(data: GameData) -> tuple[str, ...]:
    return (*(m.key for m in file(data).cell_makers), OWN)
