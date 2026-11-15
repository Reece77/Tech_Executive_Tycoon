"""Power settlement (docs/formulas.md 46.2, ADR-0022 3): the end of phase 6, after every
facility has posted its energy at the grid price.

For each company and region, the month's metered energy (tst.sim.power.demand) is matched to
supply in order:

1. behind-the-meter plants, each to the load of the facility it sits behind (its surplus is
   curtailed: it has no grid connection);
2. the company's other live, connected plants in the region (their energy pays the grid's
   network charges, `power.grid_charge_share` of the price; gas runs only while its marginal
   cost is under the grid price); their surplus sells to the grid at the price x
   (1 - `power.export_discount`) when it beats their marginal cost;
3. running PPAs, in signing order, up to their volume (the untaken volume pays the
   take-or-pay share, 33.3);
4. the grid, for the rest.

Energy balances per company and region: demand = plants used + PPAs used + grid; each plant's
output = used + exported + curtailed. The money is one entry a company and region: matched energy
was already charged at the grid price, so it is credited back to `5950 energy` ("displaced");
plants' fuel, operating cost, carbon and grid charges and PPAs' payments debit it; exports credit
`4950 energy sales`; cash balances the entry. A live plant pays its fixed O&M every month,
running or not, and so does a built plant waiting for its connection (46.3's holding cost).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, ENERGY, ENERGY_SALES, LedgerEntry, LedgerLine
from tst.sim.power import demand, grid, plants
from tst.sim.power.models import Plant, PlantMonth, PowerMonth, Ppa
from tst.sim.state import GameState, with_plant, with_ppa

CENTS: Final = 100  # tunable-exempt: cents a dollar
TINY: Final = 1e-9  # tunable-exempt: energy below this is none
FOSSIL_INTENSITY: Final = {"coal": 0.95, "gas": 0.37}  # tunable-exempt: A, tCO2 a MWh by fleet type


@dataclass(slots=True)
class _Plant:
    plant: Plant
    region: str
    site_id: int | None
    available: float  # MWh it can generate
    marginal: float  # cents a MWh
    fixed: float  # cents this month
    intensity: float  # tCO2 a MWh
    used: float = 0.0
    exported: float = 0.0
    curtailed: float = 0.0
    used_offsite: float = 0.0


@dataclass(slots=True)
class _Book:
    """A company's region this month."""

    demand: float = 0.0
    grid_cents: int = 0
    peak: float = 0.0
    loads: dict[int, float] = field(default_factory=dict)  # facility id -> MWh still to supply
    plant_mwh: float = 0.0
    ppa_mwh: float = 0.0
    exported: float = 0.0
    displaced: Fraction = Fraction(0)  # cents
    charges: Fraction = Fraction(0)  # cents
    sales: Fraction = Fraction(0)  # cents
    scope1: float = 0.0
    scope2: float = 0.0


def producer_intensity(data: GameData, key: str) -> float:
    """A PPA's tCO2 a MWh: its producer's fleet mix (A: coal 0.95, gas 0.37, the rest 0)."""
    assert data.power is not None
    p = next((x for x in data.power.producers if x.key == key), None)
    if p is None:
        return 0.0
    return sum(share * FOSSIL_INTENSITY.get(tech, 0.0) for tech, share in p.mix.items())


def _plant_rows(state: GameState, balance: Balance, data: GameData) -> list[_Plant]:
    rows = []
    year = grid.year_of(state.turn)
    for p in state.plants:
        f = plants.facility_of(state, p)
        if f.status == "closed":
            continue
        t = plants.type_def(data, p.type)
        built = f.capex_paid_cents >= f.capex_cents and state.turn >= p.complete_turn
        fixed = (
            plants.fixed_usd_month(t, p.mw, year) * CENTS if (p.live(state.turn) or built) else 0.0
        )
        rows.append(
            _Plant(
                plant=p,
                region=f.region,
                site_id=p.site_id,
                available=plants.energy_mwh(state, p, balance, data),
                marginal=plants.marginal_usd_mwh(state, p.type, f.region, balance, data) * CENTS,
                fixed=fixed,
                intensity=t.intensity_at(year),
            )
        )
    return rows


def settle(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    """The month's settlement (module docstring): entries, plants' and PPAs' months, and each
    company's power month."""
    if data.power is None:
        return state, []
    pb = balance.power
    turn = state.turn
    readings = demand.meters(state, balance, data)
    books: dict[tuple[int, str], _Book] = defaultdict(_Book)
    for m in readings:
        b = books[(m.company_id, m.region)]
        b.demand += m.mwh
        b.grid_cents += m.grid_cents
        b.loads[m.facility_id] = b.loads.get(m.facility_id, 0.0) + m.mwh
    rows = _plant_rows(state, balance, data)
    for r in rows:
        books.setdefault((r.plant.company_id, r.region), _Book())
    ppas = sorted((p for p in state.ppas if p.running(turn)), key=lambda p: p.id)
    for ppa in ppas:
        books.setdefault((ppa.company_id, ppa.region), _Book())
    price: dict[str, float] = {}

    def grid_price(region: str) -> float:
        if region not in price:
            price[region] = grid.price_cents(state, region, balance, data)
        return price[region]

    # 1. behind the meter: each plant to its site's load
    for r in rows:
        if r.site_id is None or r.available <= TINY:
            continue
        b = books[(r.plant.company_id, r.region)]
        p = grid_price(r.region)
        need = b.loads.get(r.site_id, 0.0)
        runs = r.plant.type not in ("gas",) or r.marginal < p
        take = min(need, r.available) if runs else 0.0
        r.used = take
        b.loads[r.site_id] = need - take
        r.curtailed = r.available - take if r.plant.type != "gas" else 0.0
    # 2. other plants, to the rest of the region's load, then exports
    for r in rows:
        if r.site_id is not None or r.available <= TINY or not r.plant.connected:
            continue
        b = books[(r.plant.company_id, r.region)]
        p = grid_price(r.region)
        if r.plant.type == "gas" and r.marginal >= p:
            continue
        left = r.available
        for fid in sorted(b.loads):
            take = min(left, b.loads[fid])
            if take <= TINY:
                continue
            b.loads[fid] -= take
            left -= take
            r.used += take
            r.used_offsite += take
        sell = p * (1 - pb.export_discount)
        if left > TINY and (r.plant.type != "gas" or r.marginal < sell):
            r.exported = left
    # 3. PPAs in signing order; 4. the grid
    ppa_rows: list[tuple[Ppa, float]] = []
    for ppa in ppas:
        b = books[(ppa.company_id, ppa.region)]
        left = ppa.mwh_month
        used = 0.0
        for fid in sorted(b.loads):
            take = min(left, b.loads[fid])
            if take <= TINY:
                continue
            b.loads[fid] -= take
            left -= take
            used += take
        ppa_rows.append((ppa, used))
    # money and emissions
    for r in rows:
        b = books[(r.plant.company_id, r.region)]
        exact_p = Fraction(grid_price(r.region))
        gen = r.used + r.exported
        b.plant_mwh += r.used
        b.exported += r.exported
        b.displaced += Fraction(r.used) * exact_p
        b.charges += Fraction(gen) * Fraction(r.marginal) + Fraction(r.fixed)
        b.charges += Fraction(r.used_offsite) * exact_p * Fraction(pb.grid_charge_share)
        b.sales += Fraction(r.exported) * exact_p * Fraction(1 - pb.export_discount)
        b.scope1 += gen * r.intensity
    paid: dict[int, int] = {}
    for ppa, used in ppa_rows:
        b = books[(ppa.company_id, ppa.region)]
        untaken = max(0.0, ppa.mwh_month - used)
        cost = Fraction(used) * Fraction(ppa.price_cents) + Fraction(untaken) * Fraction(
            ppa.price_cents
        ) * Fraction(pb.ppa.take_or_pay)
        b.ppa_mwh += used
        b.displaced += Fraction(used) * Fraction(grid_price(ppa.region))
        b.charges += cost
        b.scope2 += used * producer_intensity(data, ppa.producer)
        paid[ppa.id] = round(cost)
    entries: list[LedgerEntry] = []
    months: list[PowerMonth] = []
    for (company, region), b in sorted(books.items()):
        g = grid_price(region) if b.demand > TINY or b.plant_mwh or b.exported else 0.0
        grid_mwh = max(0.0, b.demand - b.plant_mwh - b.ppa_mwh)
        b.scope2 += grid_mwh * grid.intensity(state, region, data)
        net_energy = round(b.charges - b.displaced)
        sales = round(b.sales)
        lines = []
        if net_energy:
            lines.append(LedgerLine(ENERGY, net_energy))
        if sales:
            lines.append(LedgerLine(ENERGY_SALES, -sales))
        cash = -(net_energy - sales)
        if cash:
            lines.append(LedgerLine(CASH, cash))
        if len(lines) >= 2:
            entries.append(
                LedgerEntry(
                    turn=turn,
                    company_id=company,
                    memo=f"Power settlement: {data.region(region).label}",
                    lines=tuple(lines),
                )
            )
        months.append(
            PowerMonth(
                company_id=company,
                region=region,
                turn=turn,
                demand_mwh=b.demand,
                plant_mwh=b.plant_mwh,
                ppa_mwh=b.ppa_mwh,
                grid_mwh=grid_mwh,
                exported_mwh=b.exported,
                grid_price_cents=g,
                grid_cents=b.grid_cents,
                net_cents=b.grid_cents + net_energy - sales,
                scope1_tonnes=b.scope1,
                scope2_tonnes=b.scope2,
                peak_mw=demand.mw(b.demand, balance),
            )
        )
    for r in rows:
        p = grid_price(r.region)
        gen = r.used + r.exported
        pm = PlantMonth(
            turn=turn,
            output_mwh=gen,
            used_mwh=r.used,
            exported_mwh=r.exported,
            curtailed_mwh=r.curtailed,
            fuel_cents=round(gen * r.marginal) if r.plant.type in ("gas", "nuclear", "smr") else 0,
            om_cents=round(r.fixed),
            carbon_cents=round(
                gen * r.intensity * grid.carbon_price(state, r.region, data) * CENTS
            ),
            grid_charge_cents=round(r.used_offsite * p * pb.grid_charge_share),
            export_cents=round(r.exported * p * (1 - pb.export_discount)),
            displaced_cents=round(r.used * p),
            tonnes=gen * r.intensity,
            offline=r.plant.offline(turn),
        )
        state = with_plant(state, replace(r.plant, month=pm))
    for ppa, used in ppa_rows:
        state = with_ppa(state, replace(ppa, used_mwh=used, paid_cents=paid[ppa.id]))
    keep = turn - pb.history_months
    old = [m for m in state.power_months if m.turn > keep and m.turn != turn]
    outages = {o.region for o in state.grid_outages if o.turn == turn}
    months = [replace(m, outage=m.region in outages) for m in months]
    lost = _wafers_lost(state)
    months = [replace(m, wafers_lost=lost.get((m.company_id, m.region), 0.0)) for m in months]
    state = replace(
        state,
        power_months=tuple(sorted([*old, *months], key=lambda m: (m.company_id, m.region, m.turn))),
    )
    return state, entries


def _wafers_lost(state: GameState) -> dict[tuple[int, str], float]:
    out: dict[tuple[int, str], float] = defaultdict(float)
    for fab in state.fabs:
        m = fab.month
        if m is None or m.turn != state.turn or m.outage_starts <= 0:
            continue
        f = state.facility(fab.facility_id)
        if f is not None:
            out[(f.company_id, f.region)] += m.outage_starts
    return out
