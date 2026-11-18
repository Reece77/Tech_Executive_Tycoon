"""M43a's balance runs (docs/formulas.md 54.4; docs/tasks/M43a-market-sizes-and-saturation.md).

`market_run` plays one dynasty game (M37's: a family, full_integrator, dynasty mode from 2040)
to December 2069 and records, after every December, each category's addressable market and
ceiling by region (tst.sim.markets.saturation), the regions' GDP at the game's economy, and the
largest ledger balance. `readings` judges 54.4's targets 1-4 over several seeds; target 2 reads
2025's SERVED revenue (what companies book: customers x price x units a month, plus medical
consumables, x 12; Reece, 2026-11-17) against PUBLISHED (docs/v5-research/market-sizes-
dossier.md), in real dollars (game dollars / economy_scale.money). Target 1's technology share
of world GDP is judged on served revenue too, with the addressable sum printed beside it."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Final

from tst.balance import m30, m37
from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.dynasty.mode import continue_dynasty
from tst.sim.facilities.compute import home_region_of
from tst.sim.markets import saturation as sat
from tst.sim.state import GameState

SEEDS: Final = tuple(range(1, 11))
END: Final = m37.END
STANDARD_END: Final = 360  # December 2039, the standard campaign
START_YEAR: Final = 2026  # balance.yaml markets.ceiling_start_year (checked in readings)
TOLERANCE: Final = 1e-6  # relative slack on A <= C (float rounding)
BAND: Final = (0.5, 2.0)  # 54.4 target 2: x the published 2025 size
GROWTH_MIN: Final = 0.01  # 54.4 target 3: a year, on average through the 2060s
MONEY_LIMIT: Final = m37.MONEY_LIMIT  # 54.4 target 4 (M37.money)

# category -> (published 2025 world size, billions of dollars, source): the dossier's figures
PUBLISHED: Final[dict[str, tuple[float, str]]] = {
    "b2b_saas": (299.0, "Gartner SaaS end-user spending 2025"),
    "dev_tools": (
        25.0,
        "app development and ALM software about $20-30B (judgement; $13-14B narrow)",
    ),
    "consumer_apps": (167.0, "Sensor Tower app-store consumer spending 2025"),
    "cybersecurity": (213.0, "Gartner information security end-user spending 2025"),
    "fintech": (378.0, "BCG/QED fintech revenue 2024"),
    "ai_models": (186.0, "Gartner AI application software $172B + GenAI models $14.2B, 2025"),
    "cloud_hosting": (419.0, "Synergy IaaS + PaaS + hosted private cloud 2025"),
    "devices": (750.0, "IDC smartphones about $550B + PCs about $200B, 2025"),
    "servers": (444.1, "IDC server market 2025"),
    "chips_mobile_soc": (45.0, "smartphone application processors about $40-50B (derived)"),
    "chips_server_cpu": (27.0, "data-centre CPUs about $25-30B (TechInsights, derived)"),
    "chips_ai_accelerator": (230.0, "data-centre accelerators $170-290B (NVIDIA FY26, Omdia)"),
    "contract_manufacturing": (648.0, "EMS and ODM 2024 (New Venture Research)"),
    "vehicles": (600.0, "EVs 20M+ units 2025 (IEA) x about $30k (derived)"),
    "wearables_diagnostics": (14.0, "M41: CGM $11-13B + home diagnostics, 2024"),
    "imaging": (44.0, "M41: medical imaging equipment $42-46B, 2024"),
    "surgical_robotics": (10.0, "M41: GlobalData about $10B, 2024"),
    "implantables": (30.5, "M41: cardiac rhythm $23.5B + neuromodulation $7B, 2024"),
    "samd": (1.5, "M41: AI imaging and diagnostic software about $1-2B, 2024"),
    "launch": (15.0, "M40: launch services about $9-15B, 2024 (SIA, space.yaml)"),
    "satellite_broadband": (11.4, "M40: Starlink revenue 2025 (space.yaml; the largest operator)"),
    "earth_observation": (4.5, "M40: EO data and services about $4-5B, 2023 (Euroconsult, space.yaml)"),
}
# categories reported, not judged, by target 2 (decisions in the M43a brief)
BY_DESIGN: Final[dict[str, str]] = {
    "contract_manufacturing": "a spare-capacity market by design (economy-scale audit §4)",
}


@dataclass(slots=True)
class MarketResult:
    seed: int
    # year -> category -> region -> (A, C), cents a year (C 0 for a category without one)
    years: dict[int, dict[str, dict[str, tuple[float, float]]]] = field(default_factory=dict)
    gdp: dict[int, float] = field(default_factory=dict)  # year -> world GDP, game cents a year
    served: dict[int, dict[str, float]] = field(default_factory=dict)  # year -> category -> cents
    max_balance: int = 0
    max_key: tuple[str, str] = ("", "")


def snapshot(
    state: GameState, balance: Balance, data: GameData
) -> tuple[dict[str, dict[str, tuple[float, float]]], float]:
    home = home_region_of(state, balance, data)
    rows = [(m.category, m.segment, home, m.addressable) for m in state.markets]
    rows += [(r.category, r.segment, r.region, r.addressable) for r in state.regional_markets]
    values = sat.market_values(state, rows, data, home)
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for (cat, region), v in values.items():
        cap = sat.ceiling_cents(state, balance, data, cat, region) if sat.grows(data, cat) else 0.0
        out.setdefault(cat, {})[region] = (v, cap)
    gdp = sum(
        sat.gdp_trend(balance, data, r.key, state.turn) * sat.cycle(state, r.key)
        for r in data.regions
    )
    return out, gdp * sat.TRILLION_CENTS * balance.economy_scale.money


def served(state: GameState, balance: Balance, data: GameData) -> dict[str, float]:
    """Each category's booked revenue a year at this month's rate, cents (module docstring)."""
    from tst.sim.products.formulas import sale_rate
    from tst.sim.score import market_revenue

    out: dict[str, float] = {}
    for (cat, seg, _), by in market_revenue(state, data, balance).items():
        c = data.category(cat)
        m = c.market(seg)
        revenue = sum(by.values())
        month = revenue * sale_rate(c, seg)
        if c.medical:  # installed units x consumables, at the market's own price mix
            units = revenue / m.reference_price_cents * m.units_per_customer
            month += units * sat._consumables(data, cat)
        out[cat] = out.get(cat, 0.0) + 12 * month
    return out


def market_run(seed: int, turns: int = END) -> MarketResult:
    data = m30.loaded()
    g, b = data.game_data, data.balance
    game = m37._family_game(seed)
    game.state = continue_dynasty(game.state, b)
    script = m30.strategy(m37.STRATEGY)
    result = MarketResult(seed)
    while game.state.turn < turns and not game.state.ended:
        script(game)
        game.turn()
        year, month = turn_to_ym(game.state.turn - 1)
        if month == 12:
            result.years[year], result.gdp[year] = snapshot(game.state, b, g)
            result.served[year] = served(game.state, b, g)
    top = max(game.balances, key=lambda k: abs(game.balances[k]), default=None)
    if top is not None:
        result.max_balance = abs(game.balances[top])
        result.max_key = (game.state.company(top[0]).name, top[1])
    return result


def run_all(workers: int, seeds: Sequence[int] = SEEDS, turns: int = END) -> list[MarketResult]:
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(market_run, seeds, [turns] * len(seeds)))


def total(result: MarketResult, year: int, category: str) -> float:
    return sum(a for a, _ in result.years.get(year, {}).get(category, {}).values())


@dataclass(frozen=True, slots=True)
class Readings:
    over_ceiling: list[str]  # target 1: "seed:year:category/region" grown past C
    held: list[str]  # past C from the history (January 2026) and held there: printed (M43)
    tech_share_max: float  # target 1: the largest served tech sum / world GDP in any year
    tech_addressable_max: float  # the same for addressable markets (printed)
    real_2025: dict[str, float]  # target 2: category -> median real 2025 size, $B
    out_of_band: list[str]  # target 2: categories outside BAND, not BY_DESIGN
    growth_2060s: dict[str, float]  # target 3: category -> lowest seed's average growth
    slow: list[str]  # target 3
    data_set: list[str]  # target 3, printed: markets whose demand data sets (not judged)
    max_balance: int  # target 4
    max_where: str


def _non_tech(data: GameData, balance: Balance, category: str) -> bool:
    c = data.category(category)
    return category in balance.markets.non_tech or (c.family or "") in balance.markets.non_tech


def readings(results: Sequence[MarketResult]) -> Readings:
    import statistics

    data = m30.loaded()
    g, b = data.game_data, data.balance
    assert b.markets.ceiling_start_year == START_YEAR
    money = b.economy_scale.money
    over: list[str] = []
    held: set[str] = set()
    share = share_a = 0.0
    for r in results:
        for year, cats in r.years.items():
            tech = 0.0
            for cat, regions in cats.items():
                if not _non_tech(g, b, cat):
                    tech += sum(a for a, _ in regions.values())
                prev = r.years.get(year - 1, {}).get(cat, {})
                for region, (a, c) in regions.items():
                    if c <= 0 or year < START_YEAR or a <= c * (1 + TOLERANCE):
                        continue
                    a0 = prev.get(region, (0.0, 0.0))[0]
                    if a <= a0 * (1 + TOLERANCE):
                        held.add(f"{cat}/{region}")  # past it from the history: held, not grown
                    else:
                        over.append(f"{r.seed}:{year}:{cat}/{region}")
            booked = sum(v for k, v in r.served.get(year, {}).items() if not _non_tech(g, b, k))
            if r.gdp.get(year):
                share_a = max(share_a, tech / r.gdp[year])
                share = max(share, booked / r.gdp[year])
    real: dict[str, float] = {}
    bad: list[str] = []
    for cat, (published, _) in PUBLISHED.items():
        vals = [
            r.served[2025].get(cat, 0.0) / 100 / money / 1e9 for r in results if 2025 in r.served
        ]
        if not vals:
            continue
        real[cat] = statistics.median(vals)
        ratio = real[cat] / published
        if not BAND[0] <= ratio <= BAND[1] and cat not in BY_DESIGN:
            bad.append(f"{cat} {ratio:.2f}x")
    growth: dict[str, float] = {}
    for r in results:
        if 2069 not in r.years or 2059 not in r.years:
            continue
        for cat in r.years[2069]:
            a0, a1 = total(r, 2059, cat), total(r, 2069, cat)
            if a0 <= 0:
                continue
            rate = (a1 / a0) ** 0.1 - 1
            growth[cat] = min(growth.get(cat, rate), rate)
    # demand set from data each month (vehicles, M38) has no growth rate here: printed, not judged
    slow = [f"{k} {v:.2%}" for k, v in sorted(growth.items()) if v < GROWTH_MIN and sat.grows(g, k)]
    data_set = [f"{k} {v:.2%}" for k, v in sorted(growth.items()) if not sat.grows(g, k)]
    worst = max(results, key=lambda x: x.max_balance)
    return Readings(
        over_ceiling=over,
        held=sorted(held),
        tech_share_max=share,
        tech_addressable_max=share_a,
        real_2025=real,
        out_of_band=bad,
        growth_2060s=growth,
        slow=slow,
        data_set=data_set,
        max_balance=worst.max_balance,
        max_where=f"seed {worst.seed}: {worst.max_key[0]} {worst.max_key[1]}",
    )


def report(results: Sequence[MarketResult]) -> str:
    x = readings(results)
    cap = m30.loaded().balance.markets.tech_share_max
    lines = [
        "| Target | Reading | Band | Result |",
        "| --- | --- | --- | --- |",
        f"| 54.4 T1 markets grown past their ceiling | {len(x.over_ceiling)} "
        f"(held past it from the history, printed: {', '.join(x.held) or '-'}) | 0 | "
        f"{'pass' if not x.over_ceiling else 'MISS'} |",
        f"| 54.4 T1 tech share of world GDP, served (largest) | {x.tech_share_max:.2%} "
        f"(addressable {x.tech_addressable_max:.2%}) | <= "
        f"{cap:.0%} | {'pass' if x.tech_share_max <= cap else 'MISS'} |",
        f"| 54.4 T2 2025 within 0.5-2x | {len(x.out_of_band)} outside: "
        f"{', '.join(x.out_of_band) or '-'} | "
        f"0 | {'pass' if not x.out_of_band else 'MISS'} |",
        f"| 54.4 T3 growth 2060s >= 1% | below: {', '.join(x.slow) or 'none'}; demand set by "
        f"data (printed): {', '.join(x.data_set) or '-'} | none below | "
        f"{'pass' if not x.slow else 'MISS'} |",
        f"| 54.4 T4 largest balance | {x.max_balance:.3e} ({x.max_where}) | < {MONEY_LIMIT:.1e} | "
        f"{'pass' if x.max_balance < MONEY_LIMIT else 'MISS'} |",
        "",
        "| Category | 2025 served, real $B (median) | Published $B | Ratio | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for cat, (pub, src) in PUBLISHED.items():
        if cat in x.real_2025:
            v = x.real_2025[cat]
            note = f" ({BY_DESIGN[cat]})" if cat in BY_DESIGN else ""
            lines.append(f"| {cat} | {v:,.1f} | {pub:,.1f} | {v / pub:.2f} | {src}{note} |")
    return "\n".join(lines)
