"""M22's balance targets (docs/formulas.md 39.4), printed by tools/m22_targets.py.

1. History holds: every dossier 5 rule takes effect on its date on every seed; tension follows
   history to 2025.
2. Controls bite: an AI-accelerator seller with 30% of revenue in China loses 15-30% of total
   revenue in the 12 months after October 2022 (against the same seed with the October 2022
   rules removed), 5-15% with a compliant variant launched that month.
3. Bans hit supply: gallium bought only from China costs 30-80% more in 2024-2025 than with a
   non-China source (an offtake with Dowa).
4. Influence helps licences: at influence 80 a licence is approved at least 1.2x as often as at 0.
5. Tariffs cost: China-assembled devices sold in North America cost 8-20% more from 2019.
6. After 2025: an escalation and a détente in 2026-2039 on 7-10 of 10 seeds.
7. A software-only company in North America and Europe plays exactly as before (the same seed
   with M22's data removed gives the same ledger and snapshots).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

from tst.balance import m12b
from tst.balance.game import Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.chips import chips
from tst.sim.commodities.models import CommodityDeal
from tst.sim.data_models import GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.founder.models import Influence
from tst.sim.geo.models import ProductRegion, RegionalSegment
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics import supply, tariffs, tension
from tst.sim.geopolitics.actions import approval_chance
from tst.sim.geopolitics.models import Licence, Variant
from tst.sim.ledger import REVENUE_SUBSCRIPTIONS
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_company,
    with_influence,
    with_product_region,
    with_product_segment,
    with_regional_segment,
    with_variant,
)

SEEDS = tuple(range(1, 11))
DATA = Path(__file__).resolve().parents[2] / "data"
PLAYER = 1
MONTHS = 12
CHINA_SHARE = 0.30  # target 2: share of revenue in China
OCT_2022 = "us_oct_2022"
SEGMENT = "device_oems"
NA_CUSTOMERS = 20.0  # device makers buying the accelerator in North America at the start
SELLERS = 15  # account executives in each region: demand, not sellers, limits sales
REPLACEMENT = 24  # months: a design win's renewal (categories.yaml)


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


def without_rules(keys: Sequence[str]) -> LoadedData:
    """The data with some historical rules removed (target 2's counterfactual)."""
    base = loaded()
    d = base.game_data
    assert d.controls is not None
    controls = d.controls.model_copy(
        update={"rules": tuple(r for r in d.controls.rules if r.key not in keys)}
    )
    return replace(base, game_data=d.model_copy(update={"controls": controls}))


def without_geopolitics() -> LoadedData:
    base = loaded()
    d = base.game_data.model_copy(update={"countries": None, "controls": None, "tariffs": None})
    return replace(base, game_data=d)


# --- target 1 ---------------------------------------------------------------------------------


def target_1(seeds: Sequence[int] = SEEDS) -> tuple[int, int, bool]:
    """(rules checked, misses, tension follows history) on every seed."""
    data = loaded()
    d = data.game_data
    assert d.controls is not None
    misses = checked = 0
    follows = True
    for seed in seeds:
        state = start_game(data, seed, "funded_spinout").state
        for r in d.controls.rules:
            start = r.start_turn
            on = {a.key for a in gr.in_force(state, d, start)}
            before = {a.key for a in gr.in_force(state, d, start - 1)} if start > 0 else set()
            checked += 1
            suspended = gr.suspension(state, d, r.key, start) is not None
            if (r.key not in on and not suspended) or r.key in before:
                misses += 1
        for month, value in world_history(d):
            if tension.tension_at(state, d, month_to_turn(month)) != value:
                follows = False
    return checked, misses, follows


def world_history(d: GameData) -> tuple[tuple[str, float], ...]:
    assert d.countries is not None
    return d.countries.tension_history


# --- target 2 ---------------------------------------------------------------------------------


def accelerator_company(seed: int, data: LoadedData, start: int) -> tuple[Game, int]:
    """An AI-accelerator seller from `start` (`accelerator_state` on a new game)."""
    g = start_game(data, seed, "funded_spinout")
    g.balances[(PLAYER, "1000_cash")] = g.balances.get((PLAYER, "1000_cash"), 0) + m12b.RICH
    g.state, pid = accelerator_state(replace(g.state, turn=start), data, seed)
    return g, pid


def accelerator_state(state: GameState, data: LoadedData, seed: int) -> tuple[GameState, int]:
    """The player's company as an AI-accelerator seller at the state's month: hardware
    engineers, sellers in North America and (remote, from Shenzhen) East Asia, a quality-80
    accelerator selling to device makers in both, East Asia's customers sized so China (55% of
    East Asia's demand) is 30% of revenue, and a TSMC wafer contract for three times the
    month's replacement demand."""
    m12b._loaded = lambda: data  # type: ignore[assignment]  # the helpers read this data
    start = state.turn
    state = m12b.hire(state, "hardware_engineer", m12b.STAFF, seed)
    before = {p.id for p in state.people}
    state = m12b.hire(state, "account_executive", 2 * SELLERS, seed + 1000)
    sellers = sorted(p.id for p in state.people if p.id not in before)
    east_side = set(sellers[SELLERS:])  # half work remotely from Shenzhen
    state = replace(
        state,
        people=tuple(replace(p, city="shenzhen") if p.id in east_side else p for p in state.people),
    )
    state = with_company(state, replace(state.player, work_policy="remote"))
    seg = data.game_data.category("chips_ai_accelerator").market(SEGMENT)
    price = seg.reference_price_cents
    state, pid = m12b.product(state, "chips_ai_accelerator", SEGMENT, price, "Accel", root=True)
    home = state.product_segment(pid, SEGMENT)
    assert home is not None and data.game_data.countries is not None
    state = with_product_segment(state, replace(home, customers=NA_CUSTOMERS))
    china = data.game_data.countries.country("china")
    # c_ea x 0.55 / (c_na + c_ea) = 0.3  ->  c_ea = 0.3 c_na / (0.55 - 0.3)
    east = NA_CUSTOMERS * CHINA_SHARE / (china.demand_share - CHINA_SHARE)
    state = with_product_region(state, ProductRegion(pid, "east_asia", start - 6, start - 3))
    state = with_regional_segment(state, RegionalSegment(pid, "east_asia", SEGMENT, price, east))
    wafer = chips.index_wafer_cents(state, "ai_accelerator", data.balance, data.game_data, "tsmc")
    t = data.balance.chips.types["ai_accelerator"]
    need = (NA_CUSTOMERS + east) * seg.units_per_customer / REPLACEMENT * 3
    wafers = round(need / (t.per_wafer * data.balance.chips.chip_yield.base))
    state = m12b.contract(state, pid, "wafer", wafers, wafer, start - 1, 36)
    state = replace(
        state,
        products=tuple(replace(x, quality=80.0) if x.id == pid else x for x in state.products),
    )
    return state, pid


def _revenue_12(g: Game) -> int:
    before = g.balances.get((PLAYER, REVENUE_SUBSCRIPTIONS), 0)
    for _ in range(MONTHS):
        g.turn()
    return -(g.balances.get((PLAYER, REVENUE_SUBSCRIPTIONS), 0) - before)


@dataclass(frozen=True, slots=True)
class ControlsRun:
    seed: int
    loss: float  # without a variant
    loss_variant: float


def target_2_run(seed: int) -> ControlsRun:
    start = ym_to_turn(2022, 10)
    out = []
    for data, variant in ((loaded(), False), (loaded(), True), (without_rules([OCT_2022]), False)):
        g, pid = accelerator_company(seed, data, start)
        if variant:
            g.state = with_variant(g.state, Variant(pid, start))
        out.append(_revenue_12(g))
    base = out[2]
    return ControlsRun(seed, 1 - out[0] / base, 1 - out[1] / base)


# --- target 3 ---------------------------------------------------------------------------------


def target_3(seeds: Sequence[int] = SEEDS) -> list[float]:
    """Gallium's price for a US chip maker sourcing only from China over one sourcing from
    Dowa, averaged over 2024-2025, by seed: the premium paid."""
    data = loaded()
    out = []
    for seed in seeds:
        g, pid = accelerator_company(seed, data, ym_to_turn(2024, 1))
        dowa = CommodityDeal(
            id=1,
            company_id=PLAYER,
            kind="offtake",
            good="gallium",
            signed_turn=0,
            end_turn=10_000,
            volume_year=1e9,
            signing_price=1.0,
            floor=0.0,
            ceiling=1e9,
            supplier="dowa",
        )
        china = replace(dowa, supplier="chalco")
        ratios = []
        for t in range(ym_to_turn(2024, 1), ym_to_turn(2026, 1)):
            s = replace(g.state, turn=t)
            pc = supply.exposure(
                replace(s, commodity_deals=(china,)),
                PLAYER,
                "gallium",
                data.balance,
                data.game_data,
                1.0,
            )
            pd = supply.exposure(
                replace(s, commodity_deals=(dowa,)),
                PLAYER,
                "gallium",
                data.balance,
                data.game_data,
                1.0,
            )
            ratios.append(pc.price_factor / pd.price_factor - 1)
        out.append(sum(ratios) / len(ratios))
        del pid
    return out


# --- target 4 ---------------------------------------------------------------------------------


def target_4(n: int = 2000) -> tuple[float, float]:
    """Approval rates at influence 0 and 80 over `n` drawn decisions (Oct 2022's licence)."""
    data = loaded()
    g, pid = accelerator_company(1, data, ym_to_turn(2022, 10))
    rates = []
    for infl in (0.0, 80.0):
        state: GameState = with_influence(g.state, Influence(PLAYER, "north_america", infl))
        hits = 0
        for i in range(n):
            x = Licence(i + 1, PLAYER, pid, OCT_2022, "china", state.turn, state.turn)
            u = float(RngFactory(i + 1).stream(state.turn, "geopolitics", 1, x.id).random())
            hits += u < approval_chance(state, x, data.balance, data.game_data)
        rates.append(hits / n)
    return rates[0], rates[1]


# --- target 5 ---------------------------------------------------------------------------------


def target_5(seed: int = 1) -> list[tuple[int, float]]:
    """(year, tariff over cost) for a China-assembled device sold in North America."""
    data = loaded()
    m12b._loaded = lambda: data  # type: ignore[assignment]
    out = []
    for year in range(2017, 2026):
        g, pid = m12b.device_company(seed, own_chip=False, start=ym_to_turn(year, 1))
        g.turn()
        g.turn()
        state = g.state
        product = state.product(pid)
        row = state.production_of(pid)
        if product is None or row is None or row.cogs_cents <= 0:
            out.append((year, 0.0))
            continue
        cents = tariffs.product_tariff_cents(
            replace(state, turn=state.turn - 1), product, data.balance, data.game_data
        )
        out.append((year, cents / row.cogs_cents))
    return out


# --- target 6 ---------------------------------------------------------------------------------


def target_6(seeds: Sequence[int] = SEEDS) -> list[tuple[int, int, int]]:
    """(seed, escalations, détentes) in 2026-2039."""
    data = loaded()
    out = []
    for seed in seeds:
        state = replace(start_game(data, seed, "funded_spinout").state, turn=ym_to_turn(2025, 12))
        rng = RngFactory(seed)
        esc = det = 0
        while state.turn < ym_to_turn(2039, 12):
            state, kind, _ = tension.next_month(state, rng, data.balance, data.game_data)
            esc += kind == "escalation"
            det += kind == "detente"
            state = replace(state, turn=state.turn + 1)
        out.append((seed, esc, det))
    return out


# --- target 7 ---------------------------------------------------------------------------------


def target_7(seed: int = 1, turns: int = 60, start: int = ym_to_turn(2018, 1)) -> bool:
    """A software company's run with and without M22's data: identical books and snapshots."""
    runs = []
    for data in (loaded(), without_geopolitics()):
        g = start_game(data, seed, "funded_spinout")
        g.state = replace(g.state, turn=start)
        for _ in range(turns):
            g.turn()
        runs.append((dict(g.balances), list(g.snapshots), g.state.events, g.state.products))
    return runs[0] == runs[1]


@dataclass(frozen=True, slots=True)
class Results:
    t1: tuple[int, int, bool]
    t2: list[ControlsRun]
    t3: list[float]
    t4: tuple[float, float]
    t5: list[tuple[int, float]]
    t6: list[tuple[int, int, int]]
    t7: bool


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        t2 = list(pool.map(target_2_run, seeds))
    return Results(
        target_1(seeds), t2, target_3(seeds), target_4(), target_5(), target_6(seeds), target_7()
    )


def report(r: Results) -> str:
    lines = ["M22 balance targets (formulas.md 39.4)"]
    checked, misses, follows = r.t1
    lines.append(
        f"1. rules on their dates: {checked - misses}/{checked}; tension history"
        f" {'holds' if follows else 'MISSES'}"
    )
    loss = [x.loss for x in r.t2]
    var = [x.loss_variant for x in r.t2]
    lines.append(
        f"2. revenue lost Oct 2022-Sep 2023: {min(loss):.1%}-{max(loss):.1%} (15-30%);"
        f" with a variant {min(var):.1%}-{max(var):.1%} (5-15%)"
    )
    lines.append(
        f"3. gallium premium 2024-2025, China-only over Dowa: {min(r.t3):.0%}-{max(r.t3):.0%}"
        " (30-80%)"
    )
    lo, hi = r.t4
    lines.append(
        f"4. licence approval at influence 0: {lo:.1%}, at 80: {hi:.1%}"
        f" (x{hi / lo:.2f}, at least 1.2)"
    )
    lines.append(
        "5. tariffs over cost, China-assembled devices sold in North America: "
        + ", ".join(f"{y} {v:.1%}" for y, v in r.t5)
        + " (8-20% from 2019)"
    )
    both = sum(1 for _, e, d in r.t6 if e and d)
    lines.append(f"6. an escalation and a détente in 2026-2039: {both}/10 seeds (7-10)")
    lines.append(f"7. a software company plays exactly as before: {'yes' if r.t7 else 'NO'}")
    return "\n".join(lines)
