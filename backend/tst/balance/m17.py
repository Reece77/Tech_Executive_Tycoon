"""docs/formulas.md 33.6 targets (M17), measured on the engine.

1. History holds: every good's monthly price equals the history file through 2025 on every
   seed (seeds 1-10, every month), and nothing after the current month reaches the API (the
   hidden-value test, tests/integration/test_api_commodities.py).
2. Shocks hurt devices: the reference phone (formulas 26.7's: a $180 BOM at components index
   1.0, a $40 SoC and a $13 Shenzhen fee) at the 2021-2022 lithium peak against the same phone
   with its commodities at their 2020 mean (M17 decision: the components index is held at the
   reference's 1.0, so the 2021 chip shortage does not count as the lithium spike).
3. Hedging pays: M12b's 15-person device company from January 2020 (a 36-month Shenzhen
   contract) with 5-year lithium and cobalt offtakes signed after its first month, sized to 12
   times that month's use, against the same company on spot: gross margin in 2022, seeds
   1-10.
4. Power spreads: a GPU data centre's operating cost per CU by region in 2023, against North
   America; M12a's 22.7 target 4 is re-run by its own test (unchanged for North America).
5. After 2025: for each good, the seeds (1-10) with at least one shock starting in 2026-2039,
   and the longest run of months any good's index stays above 3.0.
6. Nothing else moves for software companies: the golden snapshots (tests/golden).
"""

from __future__ import annotations

import os
import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import cache

from tst.balance import m12b
from tst.balance.game import start_game
from tst.loader import LoadedData
from tst.sim.actions.commodities import SignOfftake
from tst.sim.calendar import format_turn, ym_to_turn
from tst.sim.chips import chips
from tst.sim.commodities import commodity, costs, power
from tst.sim.ledger import COGS, COMPUTE, REVENUE_SUBSCRIPTIONS
from tst.sim.rng import RngFactory

SEEDS = tuple(range(1, 11))
START = ym_to_turn(2020, 1)
LAST_HISTORY = ym_to_turn(2025, 12)
END = ym_to_turn(2039, 12)
HEDGED = ("lithium_carbonate", "cobalt")
OFFTAKE_YEARS = 5
SUPPLIERS = {"lithium_carbonate": "sqm", "cobalt": "glencore"}
INDEX_CAP = 3.0
REFERENCE_INDEX = 1.0  # 26.7's reference phone
PLAYER = m12b.PLAYER
MONTHS = 12


@cache
def _loaded() -> LoadedData:
    return m12b._loaded()


# --- target 1 ---------------------------------------------------------------------------------


def history_mismatches(seed: int) -> int:
    """Months (2010-2025) where a good's price differs from the history file."""
    loaded = _loaded()
    d, b = loaded.game_data, loaded.balance
    assert d.commodity_history is not None
    state = start_game(loaded, seed).state
    rng = RngFactory(seed)
    bad = 0
    for turn in range(LAST_HISTORY + 1):
        state = replace(state, turn=turn)
        state = replace(state, supply=commodity.months(state, rng, b, d))
        for g in d.commodity_history.goods:
            month = state.good_month(g.key)
            assert month is not None
            if abs(month.index * g.mean_2010_2019 - g.value_at(turn)) > 1e-6 * g.value_at(turn):
                bad += 1
    return bad


# --- target 2 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PhonePeak:
    month: str
    base_cents: float  # with commodities at their 2020 mean
    peak_cents: float
    rise: float


def target_2() -> PhonePeak:
    loaded = _loaded()
    b, d = loaded.balance, loaded.game_data
    bom = b.hardware.bom["devices"]
    mix = b.commodity.mixes[bom.good]
    chip = chips.bought_price_cents(d, b, bom.chip_type)
    state = start_game(loaded, 1).state
    mean_2020 = statistics.fmean(
        costs.mix_index(replace(state, turn=t), mix, d) for t in range(START, START + 12)
    )
    best = PhonePeak("", 0.0, 0.0, -1.0)
    for t in range(ym_to_turn(2021, 1), ym_to_turn(2022, 12) + 1):
        s = replace(state, turn=t)
        own = REFERENCE_INDEX
        peak = bom.base_cents * costs.apply_mix(own, mix, costs.mix_index(s, mix, d))
        base = bom.base_cents * costs.apply_mix(own, mix, mean_2020)
        unit_peak = peak + chip + bom.contract_fee_cents
        unit_base = base + chip + bom.contract_fee_cents
        rise = unit_peak / unit_base - 1
        if rise > best.rise:
            best = PhonePeak(format_turn(t), unit_base, unit_peak, rise)
    return best


# --- target 3 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HedgeRun:
    seed: int
    margin_spot: float
    margin_hedged: float
    breached: int

    @property
    def gap(self) -> float:
        return self.margin_hedged - self.margin_spot


def _margin_2022(seed: int, hedge: bool) -> tuple[float, int]:
    loaded = _loaded()
    b, d = loaded.balance, loaded.game_data
    g, pid = m12b.device_company(seed, own_chip=False, start=START)
    g.turn()  # January 2020: the first month's sales show what the company uses
    if hedge:
        use = costs.company_use(g.state, PLAYER, b, d)
        for good in HEDGED:
            signed = g.act(
                SignOfftake(
                    g.founder_id,
                    good,
                    SUPPLIERS[good],
                    OFFTAKE_YEARS,
                    volume_year=use[good] * MONTHS,
                )
            )
            assert signed, f"the {good} offtake was refused"
    year = (m12b.YEARS - 1) * m12b.MONTHS_PER_YEAR  # 2022, as M12b's device_run
    before: dict[tuple[int, str], int] = {}
    for t in range(1, m12b.YEARS * m12b.MONTHS_PER_YEAR):
        if t == year:
            before = dict(g.balances)
        g.turn()
    revenue = -m12b._lines(g, before, REVENUE_SUBSCRIPTIONS)
    cost = m12b._lines(g, before, COGS) + m12b._lines(g, before, COMPUTE)
    breached = sum(1 for x in g.state.commodity_deals if x.status == "breached")
    del pid
    return ((revenue - cost) / revenue if revenue else 0.0), breached


def hedge_run(seed: int) -> HedgeRun:
    spot, _ = _margin_2022(seed, False)
    hedged, breached = _margin_2022(seed, True)
    return HedgeRun(seed, spot, hedged, breached)


# --- target 4 ---------------------------------------------------------------------------------


def target_4() -> dict[str, float]:
    """A GPU data centre's operating cost per CU by region in 2023, x North America."""
    loaded = _loaded()
    b, d = loaded.balance, loaded.game_data
    kind = "data_centre_gpu"
    state = replace(start_game(loaded, 1).state, turn=ym_to_turn(2023, 6))
    base = b.facility.kinds[kind].opex_per_unit_cents
    na = power.opex_cents(base, power.kind_index(state, kind, b.power.base_region, b, d))
    return {
        r: power.opex_cents(base, power.kind_index(state, kind, r, b, d)) / na
        for r in d.region_keys
    }


# --- target 5 ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FutureRun:
    seed: int
    shocked: frozenset[str]  # goods with a shock starting in 2026-2039
    longest_above: dict[str, int]  # good -> longest run of months above the cap


def future_run(seed: int) -> FutureRun:
    loaded = _loaded()
    d, b = loaded.game_data, loaded.balance
    state = start_game(loaded, seed).state
    rng = RngFactory(seed)
    shocked: set[str] = set()
    run: dict[str, int] = {}
    longest: dict[str, int] = {}
    for turn in range(LAST_HISTORY, END + 1):
        state = replace(state, turn=turn)
        state = replace(state, supply=commodity.months(state, rng, b, d))
        for g in state.supply:
            if commodity.is_power(g.good):
                continue
            if turn > LAST_HISTORY and g.shock_turn == turn and g.shock_kind is not None:
                shocked.add(g.good)
            run[g.good] = run.get(g.good, 0) + 1 if g.index > INDEX_CAP else 0
            longest[g.good] = max(longest.get(g.good, 0), run[g.good])
    return FutureRun(seed, frozenset(shocked), longest)


# --- the report -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    mismatches: int
    phone: PhonePeak
    hedges: tuple[HedgeRun, ...]
    power: dict[str, float]
    futures: tuple[FutureRun, ...]


def _map[T](fn: object, seeds: Sequence[int]) -> list[T]:
    workers = min(len(seeds), os.cpu_count() or 1)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, seeds))  # type: ignore[arg-type]


def run(seeds: Sequence[int] = SEEDS) -> Results:
    mismatches = sum(_map(history_mismatches, seeds))
    hedges: tuple[HedgeRun, ...] = tuple(_map(hedge_run, seeds))
    futures: tuple[FutureRun, ...] = tuple(_map(future_run, seeds))
    return Results(mismatches, target_2(), hedges, target_4(), futures)


def shocked_seeds(results: Results) -> dict[str, int]:
    d = _loaded().game_data
    assert d.commodities is not None
    return {g.key: sum(g.key in f.shocked for f in results.futures) for g in d.commodities.goods}


def report(results: Results) -> str:
    lines = ["M17 targets (formulas.md 33.6)", ""]
    lines.append(f"1. History holds: {results.mismatches} months off the history file")
    p = results.phone
    lines.append(
        f"2. Phone at the lithium peak ({p.month}): ${p.peak_cents / 100:.2f} against "
        f"${p.base_cents / 100:.2f} with 2020 commodities: +{p.rise:.1%} (band 3-8%)"
    )
    gaps = [h.gap for h in results.hedges]
    lines.append(
        "3. Hedging pays (2022 gross margin, hedged - spot, points): "
        + ", ".join(f"{100 * g:.1f}" for g in gaps)
        + f"; min {100 * min(gaps):.1f} (target >= 3); breaches "
        + str(sum(h.breached for h in results.hedges))
    )
    cheapest = min(results.power, key=lambda r: results.power[r])
    lines.append(
        "4. Power (GPU opex per CU, 2023, x North America): "
        + ", ".join(f"{r} {v:.2f}" for r, v in results.power.items())
        + f"; cheapest {cheapest} {results.power[cheapest]:.2f} (target <= 0.85)"
    )
    counts = shocked_seeds(results)
    longest = max(max(f.longest_above.values(), default=0) for f in results.futures)
    lines.append(
        "5. After 2025, seeds with a shock (of 10): "
        + ", ".join(f"{k} {v}" for k, v in counts.items())
        + f" (target 6-10 each); longest run above 3.0: {longest} months (target <= 36)"
    )
    lines.append("6. Software companies: golden snapshots (tests/golden)")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(run()))
