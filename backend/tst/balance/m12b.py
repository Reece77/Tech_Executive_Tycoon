"""docs/formulas.md 26.6 targets 2-6 (M12b), measured on the engine.

1. Without hardware, nothing moves: the earlier targets' own tests (no new xfails).
2. Devices can work: a 15-person devices company (14 senior hardware engineers and the
   founder) with a live device on a Shenzhen contract, priced at 0.8 x reference in the
   consumer segment, from January 2010; its gross margin in year 3 (2012).
3. Plants need volume: a 20,000 units-a-month plant built in January 2013, staffed at
   manufacturing skill 14 (yield from the engine's formula), cost per good unit against the
   $13 contract fee at 75%, 80% and 30% use.
4. Own chips pay off: (a) the year-3 device company of target 2, with its own live mobile
   SoC on a wafer contract, against the same company buying its SoCs: the device's gross
   margin (cost of goods per unit) after 3 years; (b) the engine's GPU data-centre quote with
   and without an own AI accelerator.
5. History bites: a device company whose demand is above its 4,000-unit contract, signed in
   December 2020, against one that signs the same contract in January 2021 (inside the
   shortage), both to December 2022: units shipped in 2021-2022.
6. Incumbents hold: do-nothing runs, NVIDIA's share of hyperscaler AI-accelerator units sold
   in 2023.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

from tst.balance.game import Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.chips import chips
from tst.sim.facilities import formulas as ff
from tst.sim.facilities import goods, lifecycle
from tst.sim.hardware import formulas as hf
from tst.sim.hardware.models import ProductionContract
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import COGS, COMPUTE, REVENUE_SUBSCRIPTIONS
from tst.sim.money import to_millicents
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_company,
    with_employment,
    with_person,
    with_person_state,
    with_product,
    with_product_segment,
    with_production_contract,
)

SEEDS = tuple(range(1, 11))
DATA = Path(__file__).resolve().parents[2] / "data"
PLAYER = 1
RICH = 10**13
PRICE = 0.8  # x the consumer reference price
STAFF = 14  # hardware engineers, with the founder 15 people
CONTRACT_UNITS = 20_000
T5_UNITS = 4_000  # a contract below demand: the company ships what it is allocated
MARKETING = 10_000_000  # $100,000 a month on the device
MONTHS_PER_YEAR = 12
YEARS = 3
T3_SKILL = 14.0
T3_UNITS = 20_000


@cache
def _loaded() -> LoadedData:
    return load_all(DATA)


# --- helpers ----------------------------------------------------------------------------------


def _game(seed: int, turn: int = 0) -> Game:
    g = start_game(_loaded(), seed, "funded_spinout")
    g.balances[(PLAYER, "1000_cash")] = g.balances.get((PLAYER, "1000_cash"), 0) + RICH
    g.state = replace(g.state, turn=turn)
    return g


def hire(state: GameState, role: str, n: int, seed: int) -> GameState:
    """`n` senior people in `role` in the company root (they build its root product)."""
    loaded = _loaded()
    rng = RngFactory(seed)
    r = loaded.game_data.role(role)
    for i in range(n):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(0, "misc", 100 + i),
            loaded.game_data,
            loaded.balance,
            state.turn,
            r,
            "senior",
            "north_america",
            person_id=pid,
        )
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=eid,
                person_id=pid,
                company_id=PLAYER,
                role=role,
                level="senior",
                salary_cents=12_000_000,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    return state


def product(
    state: GameState, category: str, segment: str, price: int, name: str, *, root: bool
) -> tuple[GameState, int]:
    pid, ids = state.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name=name,
        status="live",
        quality=60.0,
        feature_points=_loaded().game_data.category(category).features_at_start * 0.9,
        brand=40.0,
        marketing_budget_cents=MARKETING,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    state = replace(with_product(state, p), next_ids=ids)
    state = with_product_segment(state, ProductSegment(pid, segment, price, 0.0))
    if root:
        state = with_company(state, replace(state.player, root_product_id=pid))
    return state, pid


def contract(
    state: GameState, pid: int, kind: str, units: int, price: float, signed: int, months: int
) -> GameState:
    cid, ids = state.next_ids.take("production_contract")
    c = ProductionContract(
        id=cid,
        company_id=PLAYER,
        product_id=pid,
        kind=kind,  # type: ignore[arg-type]
        supplier="foxconn" if kind == "assembly" else "tsmc",
        units=units,
        price_millicents=to_millicents(price),
        signed_turn=signed,
        end_turn=signed + months - 1,
        city="shenzhen" if kind == "assembly" else None,
    )
    return with_production_contract(replace(state, next_ids=ids), c)


def device_company(
    seed: int, *, own_chip: bool, start: int = 0, units: int = CONTRACT_UNITS
) -> tuple[Game, int]:
    """Target 2's company: a live device on a 36-month contract, 14 hardware engineers."""
    loaded = _loaded()
    g = _game(seed, start)
    state = hire(g.state, "hardware_engineer", STAFF, seed)
    ref = loaded.game_data.category("devices").market("consumer").reference_price_cents
    state, pid = product(state, "devices", "consumer", round(ref * PRICE), "Device", root=True)
    fee = loaded.balance.hardware.bom["devices"].contract_fee_cents
    state = contract(state, pid, "assembly", units, fee, start, YEARS * MONTHS_PER_YEAR)
    if own_chip:
        soc_ref = loaded.game_data.category("chips_mobile_soc").market("device_oems")
        state, chip = product(
            state,
            "chips_mobile_soc",
            "device_oems",
            soc_ref.reference_price_cents * 10,
            "SoC",
            root=False,
        )  # priced out of the market: every chip goes into the device
        wafer = chips.index_wafer_cents(
            state, "mobile_soc", loaded.balance, loaded.game_data, "tsmc"
        )
        wafers = round(CONTRACT_UNITS * 1.1 / (600 * loaded.balance.chips.chip_yield.base))
        state = contract(state, chip, "wafer", wafers, wafer, start, YEARS * MONTHS_PER_YEAR)
    g.state = state
    return g, pid


def _lines(g: Game, before: dict[tuple[int, str], int], account: str) -> int:
    return g.balances.get((PLAYER, account), 0) - before.get((PLAYER, account), 0)


# --- target 2 and 4a --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeviceRun:
    seed: int
    margin: float  # the company's gross margin in year 3
    device_cogs_per_unit: float  # year 3, cents
    device_revenue_per_unit: float


def device_run(seed: int, own_chip: bool = False) -> DeviceRun:
    g, pid = device_company(seed, own_chip=own_chip)
    year = (YEARS - 1) * MONTHS_PER_YEAR
    before: dict[tuple[int, str], int] = {}
    units = cogs = 0.0
    for t in range(YEARS * MONTHS_PER_YEAR):
        if t == year:
            before = dict(g.balances)
        g.turn()
        if t >= year:
            row = g.state.production_of(pid)
            if row is not None:
                units += row.units
                cogs += row.cogs_cents
    revenue = -_lines(g, before, REVENUE_SUBSCRIPTIONS)
    cost = _lines(g, before, COGS) + _lines(g, before, COMPUTE)
    margin = (revenue - cost) / revenue if revenue else 0.0
    seg = g.state.product_segment(pid, "consumer")
    price = float(seg.price_cents or 0) if seg else 0.0
    return DeviceRun(seed, margin, cogs / units if units else 0.0, price)


def device_run_own(seed: int) -> DeviceRun:
    return device_run(seed, True)


# --- target 3 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlantRatios:
    index: float
    plant_yield: float
    at_75: float
    at_80: float
    at_30: float


def target_3() -> PlantRatios:
    loaded = _loaded()
    b = loaded.balance
    kind = b.facility.kinds[b.hardware.plant_kind]
    built = ym_to_turn(2013, 1)
    state = replace(_game(1).state, turn=built)
    index = goods.index_now(state, kind.input_good, loaded.game_data)
    capex = ff.capex_cents(T3_UNITS, kind.capex_per_unit_cents, index)
    y = b.hardware.plant_yield
    plant_yield = hf.plant_yield(y.base, y.skill_share, T3_SKILL)
    fee = b.hardware.bom["devices"].contract_fee_cents

    def ratio(use: float) -> float:
        cost = hf.plant_cost_per_good_unit(
            T3_UNITS,
            T3_UNITS * use,
            plant_yield,
            kind.fixed_opex_cents,
            kind.variable_cents,
            capex,
            kind.life_months,
        )
        assert cost is not None
        return cost / fee

    return PlantRatios(index, plant_yield, ratio(0.75), ratio(0.80), ratio(0.30))


# --- target 4b --------------------------------------------------------------------------------


def target_4b() -> tuple[float, int, int]:
    """(cut, capex without, capex with) for 500 GPU CU in January 2018."""
    loaded = _loaded()
    b, d = loaded.balance, loaded.game_data
    state = replace(_game(1).state, turn=ym_to_turn(2018, 1))
    before = lifecycle.quote(state, PLAYER, "data_centre_gpu", "north_america", 500, b, d)
    ref = d.category("chips_ai_accelerator").market("hyperscalers").reference_price_cents
    state, chip = product(state, "chips_ai_accelerator", "hyperscalers", ref, "TPU", root=False)
    wafer = chips.index_wafer_cents(state, "ai_accelerator", b, d, "tsmc")
    state = contract(state, chip, "wafer", 100, wafer, state.turn, 24)
    after = lifecycle.quote(state, PLAYER, "data_centre_gpu", "north_america", 500, b, d)
    return 1 - after.capex_cents / before.capex_cents, before.capex_cents, after.capex_cents


# --- target 5 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ShortageRun:
    seed: int
    before: float  # units shipped in 2021-2022, contract signed December 2020
    during: float  # signed January 2021

    @property
    def fewer(self) -> float:
        return 1 - self.during / self.before if self.before else 0.0


def _shipped(seed: int, signed: int) -> float:
    start = ym_to_turn(2020, 12)
    g, pid = device_company(seed, own_chip=False, start=start, units=T5_UNITS)
    end = ym_to_turn(2022, 12)  # both cover 2021-2022 to the end
    g.state = replace(
        g.state,
        production_contracts=tuple(
            replace(c, signed_turn=signed, end_turn=end) for c in g.state.production_contracts
        ),
    )
    first, last = ym_to_turn(2021, 1), ym_to_turn(2022, 12)
    shipped = 0.0
    while g.state.turn <= last:
        turn = g.state.turn
        g.turn()
        row = g.state.production_of(pid)
        if row is not None and first <= turn <= last:
            shipped += row.units
    return shipped


def target_5_run(seed: int) -> ShortageRun:
    return ShortageRun(
        seed, _shipped(seed, ym_to_turn(2020, 12)), _shipped(seed, ym_to_turn(2021, 1))
    )


# --- target 6 ---------------------------------------------------------------------------------


def target_6_run(seed: int) -> float:
    """NVIDIA's share of hyperscaler AI-accelerator units sold in 2023 (do-nothing): new
    customers x units per customer, from the month-end history rows."""
    loaded = _loaded()
    g = _game(seed)
    upc = loaded.game_data.category("chips_ai_accelerator").market("hyperscalers")
    first, last = ym_to_turn(2023, 1), ym_to_turn(2023, 12)
    owner = {p.id: p.company_id for p in g.state.products}
    nvidia = next(c.id for c in g.state.companies if c.name == "NVIDIA")
    units: dict[int, float] = {}
    while g.state.turn <= last:
        turn = g.state.turn
        g.turn()
        owner.update({p.id: p.company_id for p in g.state.products})
        if turn < first:
            continue
        for row in g.last_product_months:
            if row.segment != "hyperscalers":
                continue
            p = g.state.product(row.product_id)
            if p is None or p.category != "chips_ai_accelerator":
                continue
            company = owner[row.product_id]
            units[company] = units.get(company, 0.0) + row.new * upc.units_per_customer
    total = sum(units.values())
    return units.get(nvidia, 0.0) / total if total else 0.0


# --- the runner -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    t2: tuple[DeviceRun, ...]
    t3: PlantRatios
    t4_own: tuple[DeviceRun, ...]
    t4b: tuple[float, int, int]
    t5: tuple[ShortageRun, ...]
    t6: tuple[float, ...]

    @property
    def t4_gaps(self) -> tuple[float, ...]:
        """Device gross-margin points gained with the own SoC, per seed."""
        return tuple(
            100
            * (o.device_cogs_per_unit and (b.device_cogs_per_unit - o.device_cogs_per_unit))
            / b.device_revenue_per_unit
            for b, o in zip(self.t2, self.t4_own, strict=True)
        )


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    with ProcessPoolExecutor(max(1, jobs)) as pool:
        t2 = pool.map(device_run, seeds)
        t4 = pool.map(device_run_own, seeds)
        t5 = pool.map(target_5_run, seeds)
        t6 = pool.map(target_6_run, seeds)
        return Results(tuple(t2), target_3(), tuple(t4), target_4b(), tuple(t5), tuple(t6))


def report(r: Results) -> str:
    in_band = sum(0.30 <= x.margin <= 0.45 for x in r.t2)
    gaps = r.t4_gaps
    t5_band = sum(0.15 <= x.fewer <= 0.35 for x in r.t5)
    t6_ok = sum(s >= 0.5 for s in r.t6)
    rows = [
        f"T2 15-person devices company on contract, gross margin year 3: {in_band}/{len(r.t2)}"
        f" seeds in 30-45% (>= 6/10); by seed {[round(x.margin, 3) for x in r.t2]}",
        f"T3 plant built Jan 2013 (equipment index {r.t3.index:.2f}, yield {r.t3.plant_yield:.3f})"
        f": cost per good unit / $13 fee at 75% {r.t3.at_75:.2f}, 80% {r.t3.at_80:.2f}"
        f" (<= 0.70), at 30% {r.t3.at_30:.2f} (>= 1.30)",
        f"T4a own mobile SoC: device margin points gained after 3 years, by seed "
        f"{[round(g, 1) for g in gaps]} (>= 8 on every seed)",
        f"T4b own AI accelerators: GPU capex per CU cut {r.t4b[0]:.0%} (>= 20%;"
        f" ${r.t4b[1] / 100:,.0f} -> ${r.t4b[2] / 100:,.0f} for 500 CU, Jan 2018)",
        f"T5 no contract before the 2021 shortage ships fewer units in 2021-2022: {t5_band}/"
        f"{len(r.t5)} seeds in 15-35%; by seed {[round(x.fewer, 3) for x in r.t5]}",
        f"T6 NVIDIA share of hyperscaler AI-accelerator units in 2023: {t6_ok}/{len(r.t6)} seeds"
        f" >= 50% (>= 7/10); by seed {[round(s, 2) for s in r.t6]}",
    ]
    return "\n".join(rows)
