"""M28's balance targets 2-7 (docs/formulas.md 41.8), on games moved to January 2026.

Each target's game is a new ex_big_tech_founders game moved straight to January 2026 (its world
comes into being in that first month), with `WORLD_CASH` so a do-nothing player lives to 2039:
the world's numbers, not the player's survival, are what these targets read. Target 1 (and 7,
the software company's books before 2026) is the history fingerprint in tst.balance.m28.

2. Markets respond: a script that builds 20% of world lithium carbonate capacity by 2030 (the
   game's lithium chemical: 41.8 names hydroxide) sees the 2031-2033 mean price 15-40% below the
   same seed without it, and at least one rival mothballing.
3. The world survives: at least 80% of chain companies alive in December 2039 (median, 10
   seeds); no good under 70% of demand for more than 24 months in a row.
4. Rivals form groups: two or more rival groups holding a chain company by 2035 on 7 of 10
   seeds; rival-on-rival deals at most 3 a year (median).
5. Bids happen when deserved: a listed player held at 0.6x value gets a bid within 3 years on
   at least 5 of 10 seeds; at 1.0x on at most 1.
6. China catches up under controls: SMIC's lag at 2030 at least one generation shorter than
   with the equipment rules removed (same seed).
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from typing import Final

from tst.balance.game import Game, start_game
from tst.balance.m28 import FIRST_YEAR, SEEDS, loaded
from tst.balance.report import Row, table
from tst.loader import LoadedData
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.state import GameState

WORLD_START: Final = 192  # January 2026
WORLD_CASH: Final = 5_000_000_000_000  # $50B
LITHIUM: Final = "lithium_carbonate"
PLANT_T: Final = 50_000  # the largest lithium converter, t a year
BUILD_SHARE: Final = 0.25  # the player's capacity x the chain's: 20% of the world's
GROUP_YEAR: Final = 2035
END_YEAR: Final = 2039
BID_MONTHS: Final = 36
BID_RATIOS: Final = (0.6, 1.0)
CHINA_SEEDS: Final = (1, 2, 3)


def world_game(seed: int, data: LoadedData | None = None, cash: int = WORLD_CASH) -> Game:
    game = start_game(data or loaded(), seed)
    game.balances = {**game.balances, (1, "1000_cash"): game.cash + cash}
    game.state = replace(game.state, turn=WORLD_START)
    return game


def turn_of(year: int, month: int = 1) -> int:
    return (year - FIRST_YEAR) * MONTHS_PER_YEAR + month - 1


# --- Target 2 ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MarketRun:
    seed: int
    built: bool
    price: float  # 2031-2033 mean lithium carbonate price, $/t
    share: float  # the player's share of world lithium capacity in January 2030
    mothballs: int  # rivals' lithium mothballings in the run


def _build_to_share(game: Game) -> float:
    """Each January 2027-2030, enough 50 kt converters for half-way (2027), then all the way
    (2028 on) to 20% of the world's lithium capacity, topped up each year to January 2030 (so
    the plants are past their ramp by 2031); the share reached."""
    from tst.balance import m20

    turn = game.state.turn
    chain = sum(
        f.capacity for f in game.state.world_facilities if f.good == LITHIUM and f.status == "live"
    )
    years = min(1.0, (turn - turn_of(2026)) / (2 * MONTHS_PER_YEAR))
    want = BUILD_SHARE * chain * years
    have = PLANT_T * sum(1 for r in game.state.refineries if r.recipe == "li_converter")
    while have < want:
        m20.build(game, "li_converter", "latin_america", PLANT_T)
        have += PLANT_T
    return have / (have + chain) if have + chain else 0.0


def market_run(job: tuple[int, bool]) -> MarketRun:
    from tst.sim.commodities import commodity

    seed, build = job
    game = world_game(seed)
    prices: dict[int, float] = {}
    mothballs = seen = 0
    share = 0.0
    while game.state.turn <= turn_of(2033, 12):
        turn = game.state.turn
        if build and turn % MONTHS_PER_YEAR == 0 and turn_of(2027) <= turn <= turn_of(2030):
            share = _build_to_share(game)
        game.turn()
        b, d = game.loaded.balance, game.loaded.game_data
        prices[turn] = commodity.price(game.state, LITHIUM, turn, d, b)
        news = game.state.world_news
        mothballs += sum(
            1 for n in news if n.id > seen and n.kind == "mothball" and n.good == LITHIUM
        )
        seen = max((n.id for n in news), default=seen)
    window = [p for t, p in prices.items() if turn_of(2031) <= t <= turn_of(2033, 12)]
    return MarketRun(seed, build, sum(window) / len(window), share, mothballs)


# --- Targets 3 and 4 ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorldRun:
    seed: int
    alive: float  # share of chain companies alive in December 2039
    longest_short: int  # the longest run of months any good was under 70% of demand
    groups_2035: int  # rival owners holding a chain company in December 2035
    deals_by_year: tuple[tuple[int, int], ...]  # (year, rival-on-rival deals agreed)


def groups_holding_chain(state: GameState) -> int:
    return len(
        {
            o.owner_id
            for o in state.ownerships
            if o.is_open
            and state.company(o.company_id).is_chain
            and not state.company(o.owner_id).is_player
        }
    )


def world_run(seed: int) -> WorldRun:
    game = world_game(seed)
    longest = groups = 0
    while game.state.turn <= turn_of(END_YEAR, 12):
        turn = game.state.turn
        game.turn()
        longest = max([longest, *(w.short_months for w in game.state.world_goods)])
        if turn == turn_of(GROUP_YEAR, 12):
            groups = groups_holding_chain(game.state)
    s = game.state
    alive = sum(1 for c in s.companies if c.is_chain and c.alive) / max(1, len(s.chain_companies))
    deals: dict[int, int] = {}
    for x in s.rival_deals:
        if x.status != "blocked":
            year = FIRST_YEAR + x.agreed_turn // MONTHS_PER_YEAR
            deals[year] = deals.get(year, 0) + 1
    return WorldRun(seed, alive, longest, groups, tuple(sorted(deals.items())))


# --- Target 5 ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BidRun:
    seed: int
    ratio: float  # the share price x value a share the player is held at
    bid_month: int | None  # months from January 2026 to the first bid; None: none in 3 years


def bid_run(job: tuple[int, float]) -> BidRun:
    from tst.balance import m13
    from tst.sim.state import listed_id, public_of, with_public

    seed, ratio = job
    game = m13.listed_game(seed)
    game.state = replace(game.state, turn=WORLD_START)
    for k in range(BID_MONTHS):
        public = public_of(game.state, listed_id(game.state))
        if public is None or game.state.ended:
            return BidRun(seed, ratio, None)
        game.state = with_public(game.state, replace(public, sentiment=ratio))
        game.turn()  # a bid's event is answered with its first choice next month (reject)
        if game.state.world_bids:
            return BidRun(seed, ratio, k)
    return BidRun(seed, ratio, None)


# --- Target 6 ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChinaRun:
    seed: int
    controls: bool
    behind_2030: float  # SMIC's lag in generations, December 2030
    reached: tuple[str, ...]


def without_equipment_rules() -> LoadedData:
    """The data with every export rule on the catch-up's goods removed (controls lifted)."""
    base = loaded()
    d = base.game_data
    assert d.controls is not None
    goods = set(base.balance.world.china_control_goods)
    controls = d.controls.model_copy(
        update={"rules": tuple(r for r in d.controls.rules if not goods & set(r.goods))}
    )
    return replace(base, game_data=d.model_copy(update={"controls": controls}))


def china_run(job: tuple[int, bool]) -> ChinaRun:
    seed, controls = job
    game = world_game(seed, loaded() if controls else without_equipment_rules())
    while game.state.turn <= turn_of(2030, 12):
        game.turn()
    lag = next(x for x in game.state.china_lags if x.foundry == "smic")
    return ChinaRun(seed, controls, lag.behind, tuple(k for k, _ in lag.reached))


# --- Running and reporting ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    markets: tuple[MarketRun, ...]
    worlds: tuple[WorldRun, ...]
    bids: tuple[BidRun, ...]
    china: tuple[ChinaRun, ...]


def _pool[T, R](fn: Callable[[T], R], jobs: Sequence[T], workers: int) -> list[R]:
    if workers <= 1:
        return [fn(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, jobs))


def run(seeds: Sequence[int] = SEEDS, workers: int = 1) -> Results:
    china = [(s, c) for s in CHINA_SEEDS for c in (True, False)]
    return Results(
        markets=tuple(_pool(market_run, [(s, b) for s in seeds for b in (False, True)], workers)),
        worlds=tuple(_pool(world_run, list(seeds), workers)),
        bids=tuple(_pool(bid_run, [(s, r) for s in seeds for r in BID_RATIOS], workers)),
        china=tuple(_pool(china_run, china, workers)),
    )


def t2_drops(r: Results) -> list[tuple[int, float, int, float]]:
    """(seed, price drop, mothballings, the player's share) per seed."""
    base = {m.seed: m for m in r.markets if not m.built}
    return sorted(
        (m.seed, 1 - m.price / base[m.seed].price, m.mothballs, m.share)
        for m in r.markets
        if m.built
    )


def t3(r: Results) -> tuple[float, int]:
    return statistics.median(w.alive for w in r.worlds), max(w.longest_short for w in r.worlds)


def t4(r: Results) -> tuple[int, float]:
    seeds = sum(1 for w in r.worlds if w.groups_2035 >= 2)
    years = [dict(w.deals_by_year).get(y, 0) for w in r.worlds for y in range(2026, END_YEAR + 1)]
    return seeds, statistics.median(years)


def t5(r: Results) -> dict[float, int]:
    return {
        x: sum(1 for b in r.bids if b.ratio == x and b.bid_month is not None) for x in BID_RATIOS
    }


def t6(r: Results) -> list[tuple[int, float, float]]:
    by = {(c.seed, c.controls): c for c in r.china}
    return [(s, by[(s, True)].behind_2030, by[(s, False)].behind_2030) for s in CHINA_SEEDS]


def rows(r: Results) -> list[Row]:
    drops = t2_drops(r)
    drop = statistics.median(d for _, d, _, _ in drops)
    mothballed = sum(1 for _, _, m, _ in drops if m > 0)
    alive, longest = t3(r)
    groups, deals = t4(r)
    bids = t5(r)
    china = t6(r)
    n = len(r.worlds)
    lags = ", ".join(f"{a:.1f}/{b:.1f}" for _, a, b in china)
    spec = [
        ("T2", "lithium price 2031-33, built vs not", f"-{drop:.0%}", "15-40% lower",
         0.15 <= drop <= 0.40),
        ("T2b", "seeds with a rival mothballing", f"{mothballed}/{len(drops)}", "every seed",
         mothballed == len(drops)),
        ("T3", "chain companies alive Dec 2039", f"{alive:.0%}", ">= 80% median",
         alive >= 0.80),
        ("T3b", "longest run under 70% of demand", f"{longest} months", "<= 24", longest <= 24),
        ("T4", "seeds with 2+ groups holding chain cos, 2035", f"{groups}/{n}", ">= 7 of 10",
         groups >= 0.7 * n),
        ("T4b", "rival-on-rival deals a year", f"{deals:g}", "<= 3 median", deals <= 3),
        ("T5", "bids within 3 years at 0.6x", f"{bids[0.6]}/{n}", ">= 5 of 10",
         bids[0.6] >= 0.5 * n),
        ("T5b", "bids within 3 years at 1.0x", f"{bids[1.0]}/{n}", "<= 1 of 10",
         bids[1.0] <= max(1, n // 10)),
        ("T6", "SMIC lag 2030, controls/lifted", lags, ">= 1 gen shorter",
         all(b - a >= 1 for _, a, b in china)),
    ]  # fmt: skip
    return [Row(f"41.8 {t}", m, v, band, ok) for t, m, v, band, ok in spec]


def report(r: Results) -> str:
    lines = [table(rows(r)), "", "T2 per seed (drop, mothballings, the player's 2030 share):"]
    lines += [f"  {s}: -{d:.0%}, {m}, {sh:.0%}" for s, d, m, sh in t2_drops(r)]
    lines.append("T3/T4 per seed (alive, longest shortage, groups 2035, deals):")
    lines += [
        f"  {w.seed}: {w.alive:.0%}, {w.longest_short}, {w.groups_2035}, "
        f"{sum(v for _, v in w.deals_by_year)}"
        for w in r.worlds
    ]
    lines.append("T5 per seed (ratio: months to the first bid):")
    lines += [f"  {b.seed} @ {b.ratio}: {b.bid_month}" for b in r.bids]
    lines.append("T6 per seed: lag in generations, nodes reached after 2025")
    lines += [
        f"  {c.seed} {'controls' if c.controls else 'lifted'}: {c.behind_2030:.2f} {c.reached}"
        for c in r.china
    ]
    return "\n".join(lines)
