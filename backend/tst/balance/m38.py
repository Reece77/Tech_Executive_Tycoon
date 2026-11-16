"""M38's balance targets (docs/formulas.md 49.6), printed by tools/m38_targets.py.

Each seed's world is played by the engine from January 2010 to December 2025 with the player's
company doing nothing (so history holds); the targets then branch from that month:

2. **The S-curve:** the world's EV share of new cars in 2035 (sales-weighted over regions), and
   the same seed with the learning rate at its range's top against its bottom ("faster with
   cheaper batteries").
3. **Integration pays in cars:** a car maker from January 2026 (a stage-4 company with 20 senior
   hardware engineers, a car at 0.9 x the reference price assembled under a 3,000-car contract
   in San Francisco, $1M a month of marketing) buying LFP cells from CATL, against the same maker
   on its own cells: a 100 MWh-a-month LFP plant (the smallest, sized to the line) and a 10,000
   t/yr lithium converter, both already running (built in 2024-2025, staffed). The car line's
   gross margin in 2034: its revenue less its cars' cost by line (the pack at the plant's cost a
   kWh, depreciation included, for its own cells), from its VehicleMonths; the plants' sales of
   surplus cells and lithium are a business of their own and left out.
4. **Software matters:** the first maker with its own OS and L2+ (an autonomy lead topped up to
   20 each January, as a player funding the research would hold): software's share of the line's
   revenue from 2026 to 2035.
5. **Tariffs bite:** the same maker assembling in Shenzhen and selling in North America, priced
   at its landed cost (with the tariff) over 0.82: its share of North America's EV buyers in
   2025-2030 while the 100% tariff holds (it does on every seed: no seeded rule lifts it).
6. **Turn time:** the mean wall-clock time of a turn from 2026 to 2035 on these worlds (the
   guards themselves are M30's `make check-timing`).
"""

from __future__ import annotations

import os
import pickle
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from statistics import median
from typing import Final

from tst.balance import fixtures, m12b
from tst.balance.game import PLAYER, Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.actions.facilities import StaffFacility
from tst.sim.calendar import ym_to_turn
from tst.sim.hardware.models import ProductionContract
from tst.sim.ledger import CASH
from tst.sim.money import to_millicents
from tst.sim.products.models import Product, ProductSegment
from tst.sim.refining.actions import BuildRefinery
from tst.sim.research.models import ResearchLead
from tst.sim.state import (
    with_company,
    with_facility,
    with_person_state,
    with_product,
    with_product_segment,
    with_production_contract,
    with_research_lead,
)
from tst.sim.vehicles import demand
from tst.sim.vehicles.models import CellPlant, VehicleSpec

SEEDS: Final = tuple(range(1, 11))
DATA: Final = Path(__file__).resolve().parents[2] / "data"
RICH: Final = 10**13
START: Final = 192  # January 2026
END_2034: Final = ym_to_turn(2034, 12)
END_2035: Final = ym_to_turn(2035, 12)
PRICE: Final = 0.9
STAFF: Final = 20
CONTRACT_UNITS: Final = 3_000
CONTRACT_MONTHS: Final = 240
MARKETING: Final = 100_000_000  # $1M a month
CELL_MWH: Final = 100  # the smallest plant: about 1,600 cars of 60 kWh a month
LI_TONNES: Final = 10_000
LEAD: Final = 20.0
LANDED_MARGIN: Final = 0.82  # a sensible price: cost / 0.82 (cars' 18% gross margin)
SOFTWARE_MEMO: Final = "Car software"
ROLE: Final = "process_engineer"  # who staffs the converter and the cell plant


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


@cache
def _world_bytes(seed: int) -> bytes:
    """The seed's world to December 2025, the player doing nothing (history holds)."""
    g = start_game(loaded(), seed, "funded_spinout")
    g.balances[(PLAYER, CASH)] = g.balances.get((PLAYER, CASH), 0) + RICH
    while g.state.turn < START:
        g.turn()
    return pickle.dumps((g.state, g.balances))


def world(seed: int) -> Game:
    state, balances = pickle.loads(_world_bytes(seed))
    g = Game(loaded(), state, balances)
    g.state = with_company(g.state, replace(g.state.player, stage=4))
    return g


def _live(g: Game, fid: int) -> None:
    f = g.state.facility(fid)
    assert f is not None
    turn = g.state.turn
    g.state = with_facility(
        g.state,
        replace(
            f,
            ordered_turn=turn - 24,
            ready_turn=turn,
            late_turn=turn,
            status="live",
            capex_paid_cents=f.capex_cents,
        ),
    )
    g.balances[(PLAYER, CASH)] -= f.capex_cents - f.capex_paid_cents
    g.balances[(PLAYER, "1500_ppe")] = (
        g.balances.get((PLAYER, "1500_ppe"), 0) + f.capex_cents - f.capex_paid_cents
    )


def _staff(g: Game, fid: int, role: str, n: int, sub: int) -> None:
    state, _ = fixtures.hire(g.state, g.loaded, role, "senior", n, f"site {fid}", 12_000_000, sub)
    g.state = state
    unit = next(u.id for u in g.state.units if u.name == f"site {fid}")
    _energise(g)
    assert g.act(StaffFacility(g.founder_id, fid, unit)), g.refused
    g.notes[f"site:{fid}"] = 1  # its role is ROLE


def keep_staffed(g: Game) -> None:
    """A sensible player replaces the plants' leavers (as M21's fab script does)."""
    from tst.sim.facilities.lifecycle import staffing

    for f in list(g.state.facilities):
        if f"site:{f.id}" not in g.notes or f.status == "closed":
            continue
        s = staffing(g.state, f, g.loaded.balance)
        if s.staff < s.needed:
            state, _ = fixtures.hire(
                g.state, g.loaded, ROLE, "senior", s.needed - s.staff, f"site {f.id}",
                12_000_000, 100 + g.state.turn,
            )  # fmt: skip
            g.state = state


def _energise(g: Game) -> None:
    ps = g.state.person_state(g.founder_id)
    g.state = with_person_state(g.state, replace(ps, energy=100))


def car_maker(g: Game, *, cells: str = "catl", platform: str = "licensed", level: str = "l2",
              city: str = "san_francisco") -> int:  # fmt: skip
    """A car line from this month (module docstring); its product id."""
    lg = g.loaded
    state = m12b.hire(g.state, "hardware_engineer", STAFF, 38)
    pid, ids = state.next_ids.take("product")
    cat = lg.game_data.category("vehicles")
    ref = cat.market("consumer").reference_price_cents
    expected = cat.features_at_start + cat.features_per_month * state.turn
    car = Product(
        id=pid,
        company_id=PLAYER,
        category="vehicles",
        name="Volta One",
        status="live",
        quality=70.0,
        feature_points=expected,
        brand=50.0,
        marketing_budget_cents=MARKETING,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    state = replace(with_product(state, car), next_ids=ids)
    state = with_product_segment(state, ProductSegment(pid, "consumer", round(ref * PRICE), 0.0))
    state = with_company(state, replace(state.player, root_product_id=pid))
    os_id = None
    if platform == "own":
        os_id, ids = state.next_ids.take("product")
        state = replace(state, next_ids=ids)
        state = with_product(
            state,
            Product(
                id=os_id,
                company_id=PLAYER,
                category="os",
                name="Volta OS",
                status="live",
                quality=70.0,
                feature_points=100.0,
                brand=40.0,
                marketing_budget_cents=0,
                created_turn=state.turn,
                launched_turn=state.turn,
            ),
        )
    spec = VehicleSpec(pid, 60.0, "lfp", 150.0, level, platform, cells, os_product_id=os_id)  # type: ignore[arg-type]
    state = replace(state, vehicle_specs=(spec,))
    cid, ids = state.next_ids.take("production_contract")
    fee = lg.balance.hardware.bom["vehicles"].contract_fee_cents
    if city != lg.balance.hardware.contract.cheap_city:
        fee = round(fee * lg.balance.hardware.contract.city_fee_mult)
    state = with_production_contract(
        replace(state, next_ids=ids),
        ProductionContract(
            id=cid,
            company_id=PLAYER,
            product_id=pid,
            kind="assembly",
            supplier="foxconn",
            units=CONTRACT_UNITS,
            price_millicents=to_millicents(fee),
            signed_turn=state.turn,
            end_turn=state.turn + CONTRACT_MONTHS - 1,
            city=city,
        ),
    )
    g.state = state
    return pid


def own_cells(g: Game) -> None:
    """A running lithium converter and LFP cell plant in North America (module docstring)."""
    _energise(g)
    before = {f.id for f in g.state.facilities}
    assert g.act(BuildRefinery(g.founder_id, "li_converter", "north_america", LI_TONNES)), g.refused
    (conv,) = {f.id for f in g.state.facilities} - before
    _live(g, conv)
    _staff(g, conv, "process_engineer", 4, 1)
    kind = g.loaded.balance.facility.kinds["cell_plant"]
    fid = g.state.next_ids.facility
    from tst.sim.facilities import lifecycle

    q = lifecycle.quote(g.state, PLAYER, "cell_plant", "north_america", CELL_MWH, g.loaded.balance,
                        g.loaded.game_data, None)  # fmt: skip
    g.state, f = lifecycle.order_build(g.state, PLAYER, q)
    assert f.id == fid
    g.state = replace(
        g.state,
        cell_plants=(CellPlant(fid, PLAYER, "lfp", estimate_cents=q.capex_cents, months_run=24),),
    )
    _live(g, fid)
    _staff(g, fid, "process_engineer", -(-CELL_MWH // int(kind.staff_per)), 2)


def _delta(g: Game, before: dict[tuple[int, str], int], accounts: Sequence[str]) -> int:
    return sum(g.balances.get((PLAYER, a), 0) - before.get((PLAYER, a), 0) for a in accounts)


def _car_margin(g: Game, since: int) -> float:
    """The car line's gross margin from `since`: revenue less its cars' cost by line."""
    revenue = cost = 0.0
    for m in g.state.vehicle_months:
        if m.turn < since:
            continue
        p = g.state.product(m.product_id)
        assert p is not None
        price = next(s.price_cents for s in g.state.segments_of(p.id) if s.price_cents)
        revenue += m.units * (price or 0) + m.software_cents
        cost += m.units * (
            m.battery_cents + m.drive_cents + m.chips_cents + m.body_cents + m.assembly_cents
        )
    return (revenue - cost) / revenue if revenue > 0 else 0.0


def _play_to(g: Game, turn: int, top_up: bool = False) -> None:
    domain = g.loaded.balance.vehicles.domain
    while g.state.turn < turn:
        keep_staffed(g)
        if top_up and g.state.turn % 12 == 0:
            lead = g.state.research_lead(PLAYER, domain)
            if lead < LEAD:
                g.state = with_research_lead(g.state, ResearchLead(PLAYER, domain, LEAD))
        g.turn()


# --- Target 2 --------------------------------------------------------------------------------


def global_share(g: Game) -> float:
    b, d = g.loaded.balance, g.loaded.game_data
    cars = {r: demand.car_sales(r, g.state.turn, d) for r in d.region_keys}
    total = sum(cars.values())
    return sum(demand.ev_share(g.state, r, b, d) * n for r, n in cars.items()) / total


def _with_rate(g: Game, rate: float) -> Game:
    """December 2025's world with its drawn learning rate replaced."""
    w = g.state.vehicle_world
    assert w.learning_rate is not None  # drawn in December 2025's phase 9
    g.state = replace(g.state, vehicle_world=replace(w, learning_rate=rate))
    return g


# --- One seed's runs --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeedRun:
    seed: int
    share_2035: float
    share_fast: float  # the learning rate at its top
    share_slow: float  # at its bottom
    margin_bought: float
    margin_own: float
    software_share: float
    china_share_us: float
    turn_seconds: float


def run_seed(seed: int) -> SeedRun:
    b = loaded().balance
    rate = b.vehicles.learning.rate
    # 2: the S-curve, and faster with cheaper batteries
    base = world(seed)
    t0 = time.perf_counter()
    _play_to(base, END_2035 + 1)
    seconds = (time.perf_counter() - t0) / (END_2035 + 1 - START)
    share = global_share(base)
    fast = _with_rate(world(seed), rate.hi)
    _play_to(fast, END_2035 + 1)
    slow = _with_rate(world(seed), rate.lo)
    _play_to(slow, END_2035 + 1)
    # 3: integration pays
    bought = world(seed)
    car_maker(bought, cells="catl")
    _play_to(bought, ym_to_turn(2034, 1))
    _play_to(bought, END_2034 + 1)
    own = world(seed)
    own_cells(own)
    car_maker(own, cells="own")
    _play_to(own, ym_to_turn(2034, 1))
    _play_to(own, END_2034 + 1)
    # 4: software matters
    sw = world(seed)
    pid = car_maker(sw, platform="own", level="l2_plus")
    start = dict(sw.balances)
    software = 0
    while sw.state.turn <= END_2035:
        _play_to(sw, sw.state.turn + 1, top_up=True)
        row = next(
            (
                m
                for m in sw.state.vehicle_months
                if m.product_id == pid and m.turn == sw.state.turn - 1
            ),
            None,
        )
        software += row.software_cents if row is not None else 0
    revenue = -_delta(sw, start, ("4000_revenue_subscriptions",))
    # 5: tariffs bite
    cn = world(seed)
    pid_cn = car_maker(cn, city="shenzhen")
    shares = []
    while cn.state.turn <= ym_to_turn(2030, 12):
        _price_landed(cn, pid_cn)
        cn.turn()
        shares.append(_us_share(cn, pid_cn))
    return SeedRun(
        seed=seed,
        share_2035=share,
        share_fast=global_share(fast),
        share_slow=global_share(slow),
        margin_bought=_car_margin(bought, ym_to_turn(2034, 1)),
        margin_own=_car_margin(own, ym_to_turn(2034, 1)),
        software_share=software / revenue if revenue > 0 else 0.0,
        china_share_us=max(shares) if shares else 0.0,
        turn_seconds=seconds,
    )


def _price_landed(g: Game, pid: int) -> None:
    """A sensible price for a China-made car in the US: its landed cost (the tariff on the cost
    of goods included) over LANDED_MARGIN, set each January."""
    if g.state.turn % 12 != 0:
        return
    from tst.sim.vehicles import spec as vs

    b, d = g.loaded.balance, g.loaded.game_data
    p = g.state.product(pid)
    assert p is not None
    cost = vs.unit_cost(g.state, p, b, d).total + b.hardware.bom["vehicles"].contract_fee_cents
    rate = max(
        (s.rate_at(g.state.turn) for s in d.tariffs.schedules  # type: ignore[union-attr]
         if "vehicles" in s.goods and s.origin == "china" and s.market == "us"),
        default=0.0,
    )  # fmt: skip
    price = round(cost * (1 + rate) / LANDED_MARGIN)
    seg = g.state.segments_of(pid)[0]
    g.state = with_product_segment(g.state, replace(seg, price_cents=price))


def _us_share(g: Game, pid: int) -> float:
    market = next(
        m for m in g.state.markets if m.category == "vehicles" and m.segment == "consumer"
    )
    mine = sum(s.customers for s in g.state.segments_of(pid) if s.segment == "consumer")
    return mine / market.addressable if market.addressable > 0 else 0.0


@dataclass(frozen=True, slots=True)
class Results:
    runs: tuple[SeedRun, ...]

    @property
    def share_median(self) -> float:
        return median(r.share_2035 for r in self.runs)

    @property
    def margin_gap_median(self) -> float:
        return median(r.margin_own - r.margin_bought for r in self.runs)

    @property
    def software_median(self) -> float:
        return median(r.software_share for r in self.runs)

    @property
    def china_max(self) -> float:
        return max(r.china_share_us for r in self.runs)

    @property
    def faster(self) -> int:
        return sum(r.share_fast > r.share_slow for r in self.runs)


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    if jobs <= 1:
        return Results(tuple(run_seed(s) for s in seeds))
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return Results(tuple(pool.map(run_seed, seeds)))


def report(r: Results) -> str:
    lines = [
        "M38 balance targets (formulas.md 49.6), seeds " + ", ".join(str(x.seed) for x in r.runs)
    ]
    for x in r.runs:
        lines.append(
            f"  seed {x.seed}: EV share 2035 {x.share_2035:.1%} (fast {x.share_fast:.1%}, slow"
            f" {x.share_slow:.1%}); gross margin 2034 own cells {x.margin_own:.1%} vs bought"
            f" {x.margin_bought:.1%}; software {x.software_share:.1%}; China-made share of US EV"
            f" buyers at most {x.china_share_us:.2%}; {x.turn_seconds * 1000:.0f} ms a turn"
        )
    ok2 = 0.35 <= r.share_median <= 0.65
    lines += [
        f"2. S-curve: median global EV share 2035 {r.share_median:.1%} (35-65%):"
        f" {'met' if ok2 else 'MISSED'}; faster with cheaper batteries on {r.faster} of"
        f" {len(r.runs)} seeds",
        f"3. Integration pays: median gross-margin gap {r.margin_gap_median * 100:.1f} points"
        f" (>= 4): {'met' if r.margin_gap_median >= 0.04 else 'MISSED'}",
        f"4. Software matters: median software share {r.software_median:.1%} (>= 10%):"
        f" {'met' if r.software_median >= 0.10 else 'MISSED'}",
        f"5. Tariffs bite: China-made car's US share at most {r.china_max:.2%} (< 2%):"
        f" {'met' if r.china_max < 0.02 else 'MISSED'}",
        f"6. Turn time: median {median(x.turn_seconds for x in r.runs) * 1000:.0f} ms a turn"
        " (2026-2035; the guards are make check-timing)",
    ]
    return "\n".join(lines)
