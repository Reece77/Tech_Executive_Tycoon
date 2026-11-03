"""docs/formulas.md 25.9 targets 2-5 (M13), printed with their values.

- T2 IPOs happen: steady and blitzscale (with their "IPO when eligible" step) over 180 months
  on 10 seeds each; seeds that list by turn 180 and the median first-day return.
- T3 guidance matters: a listed company guiding 10% above the consensus against one guiding
  at it, 36 months on 10 seeds: the share of quarters missed, and the median price ratio.
- T4 prices are believable: the price-to-sales multiple at listing for a reference listing
  (the T2 listings' median growth and margin, the mean book at that month's climate) in each
  month of history, and the T2 listings themselves.
- T5 the CEO runs things: a stage-4 company run 36 months by a CEO of score 14 with full
  authority against the same company run by the steady script; median ARR and the Chair's
  energy spent.
"""

from __future__ import annotations

import os
import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.strategies import STRATEGIES, steady
from tst.loader import LoadedData, load_all
from tst.sim.actions import AppointCeo, SetGuidance
from tst.sim.calendar import turn_to_ym
from tst.sim.finance.macro import history_month
from tst.sim.hiring.models import PersonState
from tst.sim.markets_public import formulas as pf
from tst.sim.markets_public.public import consensus
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import (
    listing_of,
    public_of,
    reach_stage,
    with_company,
    with_employment,
    with_person,
    with_person_state,
    with_product,
    with_product_segment,
)

SEEDS: tuple[int, ...] = tuple(range(1, 11))
SCENARIO = "funded_spinout"
T2_TURNS = 180
T3_MONTHS = 36
T3_ABOVE = 1.10
T5_MONTHS = 36
T5_SCORE = 14.0
CEO_ROLE = "product_manager"
MRR = 9_000_000_00
MID_MARKET = 18_000.0
PRICE = 50_000
BANK = "morgan_stanley"


@cache
def _loaded(data_dir: str = "data") -> LoadedData:
    return load_all(Path(data_dir))


# --- T2 ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Ipo:
    strategy: str
    seed: int
    listed_turn: int | None
    first_day: float | None
    ps: float | None  # market cap at the first close / ARR
    growth: float | None
    margin: float | None


def target_2_run(job: tuple[str, int]) -> Ipo:
    strategy, seed = job
    loaded = _loaded()
    game = start_game(loaded, seed, SCENARIO, "standard")
    script = STRATEGIES[strategy]
    growth = margin = None
    for _ in range(T2_TURNS):
        if game.state.ended:
            break
        before = listing_of(game.state, PLAYER)
        script(game)
        if before is None or before.status != "priced":
            company = game.state.player
            history = company.mrr_history
            if len(history) > 12:  # tunable-exempt: a year
                growth = history[-1] / history[-13] - 1 if history[-13] else None
            ops = company.op_history[-12:]  # tunable-exempt: a year
            revs = history[-len(ops) :] if ops else ()
            margin = sum(ops) / sum(revs) if ops and sum(revs) else None
        game.turn()
        if public_of(game.state, PLAYER) is not None:
            break
    listing = listing_of(game.state, PLAYER)
    if listing is None or listing.status != "listed":
        return Ipo(strategy, seed, None, None, None, None, None)
    arr = game.state.player.mrr_history[-1] * 12  # tunable-exempt: months
    cap = listing.close_cents * (listing.shares_before + listing.new_shares)
    return Ipo(
        strategy,
        seed,
        listing.listed_turn,
        listing.first_day_return,
        cap / arr if arr else None,
        growth,
        margin,
    )


# --- A scale-up to list (T3, T5) --------------------------------------------------------------


def scaleup(game: Game, stage: int = 3) -> None:
    """The e2e fixture's Kestrel in memory: a live B2B SaaS product earning ~$9M a month with
    a year of growing, profitable history, and an executive-level product lead."""
    loaded, state = game.loaded, game.state
    pid, ids = state.next_ids.take("product")
    product = Product(
        id=pid,
        company_id=PLAYER,
        category="b2b_saas",
        name="Pipeline",
        status="live",
        quality=75.0,
        feature_points=400.0,
        brand=60.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    state = replace(with_product(state, product), next_ids=ids)
    state = with_product_segment(
        state, ProductSegment(pid, "mid_market", PRICE, MID_MARKET, False, 0)
    )
    history = tuple(round(MRR / 1.035**k) for k in range(12, -1, -1))
    company = reach_stage(state.player, stage, state.turn)
    company = replace(
        company, mrr_history=history, op_history=(1_000_000_00,) * 12, root_product_id=pid
    )
    state = with_company(state, company)
    game.state = state
    game.balances = {**game.balances, (PLAYER, "1000_cash"): 100_000_000_00}
    del loaded


def add_ceo(game: Game, score: float) -> int:
    """An executive-level product lead whose CEO score is `score` (every weighted skill)."""
    loaded, state = game.loaded, game.state
    person_id, ids = state.next_ids.take("person")
    eid, ids = ids.take("employment")
    state = replace(state, next_ids=ids)
    gen = RngFactory(state.save_meta.master_seed).stream(0, "misc", 13)
    person = generate_person(
        gen,
        loaded.game_data,
        loaded.balance,
        state.turn,
        loaded.game_data.role(CEO_ROLE),
        "principal",
        "north_america",
        person_id=person_id,
    )
    person = replace(
        person, skills=person.skills.updated({k: score for k in loaded.balance.ceo.weights})
    )
    state = with_person(state, person)
    state = with_employment(
        state,
        Employment(
            id=eid,
            person_id=person_id,
            company_id=PLAYER,
            role=CEO_ROLE,
            level="principal",
            salary_cents=30_000_000,
            equity_bp=0,
            start_turn=state.turn,
            end_turn=None,
            status="active",
        ),
    )
    game.state = with_person_state(state, PersonState(person_id=person_id, morale=70.0))
    return person_id


def listed_game(seed: int) -> Game:
    from tst.sim.actions import HireBanks

    game = start_game(_loaded(), seed, SCENARIO, "standard")
    scaleup(game)
    game.act(HireBanks(game.founder_id, BANK))
    for _ in range(12):  # tunable-exempt: the chain takes 4-5 months
        steady(game)
        game.turn()
        if public_of(game.state, PLAYER) is not None:
            break
    while game.state.turn % 3:  # tunable-exempt: to a quarter start
        steady(game)
        game.turn()
    return game


# --- T3 ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GuidanceRun:
    above: bool
    seed: int
    quarters: int
    misses: int
    price_cents: int


def target_3_run(job: tuple[bool, int]) -> GuidanceRun:
    above, seed = job
    game = listed_game(seed)
    start = game.state.turn
    for _ in range(T3_MONTHS):
        state = game.state
        if state.turn % 3 == 0:  # tunable-exempt: a quarter's first month
            rev, margin = consensus(state, PLAYER)
            game.act(
                SetGuidance(game.founder_id, round(rev * (T3_ABOVE if above else 1.0)), margin)
            )
        steady(game)
        game.turn()
    reported = [
        g
        for g in game.state.guidance
        if g.company_id == PLAYER and g.quarter_turn >= start and g.reported
    ]
    public = public_of(game.state, PLAYER)
    return GuidanceRun(
        above,
        seed,
        len(reported),
        sum(1 for g in reported if g.result == "miss"),
        public.price_cents if public else 0,
    )


# --- T4 ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Multiples:
    growth: float
    margin: float
    early: float  # median P/S at listing, 2012-2019
    late: float  # 2020-2021
    jan_2022: float
    dec_2022: float


def reference_ps(turn: int, growth: float, margin: float, loaded: LoadedData) -> float:
    """P/S at the first close of a middle-ambition listing with Morgan Stanley and the
    mean book at that month's climate (25.2-25.3)."""
    b = loaded.balance
    month = history_month(turn, loaded.game_data)
    assert month is not None
    m = pf.multiple(growth, margin, month.base_rate, month.climate, b.public.multiple)
    d = pf.book_demand(0.0, month.climate, b.ipo.demand)
    quality = loaded.game_data.bank(BANK).quality
    r = pf.first_day_return(d, quality * b.ipo.ambition["middle"], b.ipo.first_day)
    return m * quality * b.ipo.ambition["middle"] * (1 + r)


def target_4(ipos: Sequence[Ipo]) -> Multiples:
    loaded = _loaded()
    growths = [i.growth for i in ipos if i.growth is not None and i.margin is not None]
    margins = [i.margin for i in ipos if i.growth is not None and i.margin is not None]
    growth: float = statistics.median(growths) if growths else 0.4  # tunable-exempt
    margin: float = statistics.median(margins) if margins else 0.0

    def ps(turn: int) -> float:
        return reference_ps(turn, growth, margin, loaded)

    def turns(y0: int, y1: int) -> list[int]:
        return [(y - 2010) * 12 + m for y in range(y0, y1 + 1) for m in range(12)]  # tunable-exempt

    return Multiples(
        growth=growth,
        margin=margin,
        early=statistics.median(ps(t) for t in turns(2012, 2019)),
        late=statistics.median(ps(t) for t in turns(2020, 2021)),
        jan_2022=ps((2022 - 2010) * 12),
        dec_2022=ps((2022 - 2010) * 12 + 11),
    )


# --- T5 ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CeoRun:
    ceo: bool
    seed: int
    arr_cents: int
    chair_spent: float  # share of the Chair's energy the founder spent


def target_5_run(job: tuple[bool, int]) -> CeoRun:
    with_ceo, seed = job
    game = start_game(_loaded(), seed, SCENARIO, "standard")
    scaleup(game, stage=4)
    ceo = add_ceo(game, T5_SCORE)
    if with_ceo:
        assert game.act(AppointCeo(game.founder_id, ceo))
    spent = available = 0
    for _ in range(T5_MONTHS):
        if with_ceo:
            before = game.energy()
            available += before
            if game.state.turn % 3 == 0 and public_of(game.state, PLAYER) is not None:
                rev, margin = consensus(game.state, PLAYER)
                game.act(SetGuidance(game.founder_id, rev, margin))
            spent += before - game.energy()
        else:
            steady(game)
        game.turn()
    arr = game.state.player.mrr_history[-1] * 12  # tunable-exempt: months
    return CeoRun(with_ceo, seed, arr, spent / available if available else 0.0)


# --- Run and report -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Results:
    t2: tuple[Ipo, ...]
    t3: tuple[GuidanceRun, ...]
    t4: Multiples
    t5: tuple[CeoRun, ...]


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    with ProcessPoolExecutor(max(1, jobs)) as pool:
        t2 = tuple(
            pool.map(target_2_run, [(s, n) for s in ("steady", "blitzscale") for n in seeds])
        )
        t3 = tuple(pool.map(target_3_run, [(a, n) for a in (False, True) for n in seeds]))
        t5 = tuple(pool.map(target_5_run, [(c, n) for c in (False, True) for n in seeds]))
    return Results(t2, t3, target_4(t2), t5)


def _median(xs: Sequence[float]) -> float:
    return statistics.median(xs) if xs else float("nan")


def t2_listed(r: Results, strategy: str) -> list[Ipo]:
    return [i for i in r.t2 if i.strategy == strategy and i.listed_turn is not None]


def t2_first_day(r: Results) -> float:
    return _median([i.first_day for i in r.t2 if i.first_day is not None])


def t3_miss_share(r: Results) -> float:
    high = [x for x in r.t3 if x.above]
    quarters = sum(x.quarters for x in high)
    return sum(x.misses for x in high) / quarters if quarters else 0.0


def t3_price_ratio(r: Results) -> float:
    high = _median([x.price_cents for x in r.t3 if x.above])
    trend = _median([x.price_cents for x in r.t3 if not x.above])
    return high / trend if trend else float("nan")


def t5_arr_ratio(r: Results) -> float:
    ceo = _median([x.arr_cents for x in r.t5 if x.ceo])
    script = _median([x.arr_cents for x in r.t5 if not x.ceo])
    return ceo / script if script else float("nan")


def t5_spent(r: Results) -> float:
    return max((x.chair_spent for x in r.t5 if x.ceo), default=0.0)


def report(r: Results) -> str:
    def year(turn: int | None) -> str:
        return str(turn_to_ym(turn)[0]) if turn is not None else "-"

    rows = []
    for strategy in ("steady", "blitzscale"):
        listed = t2_listed(r, strategy)
        rows.append(
            f"T2 {strategy}: listed by turn {T2_TURNS} on {len(listed)}/"
            f"{sum(1 for i in r.t2 if i.strategy == strategy)} seeds (>= 4); years "
            f"{[year(i.listed_turn) for i in listed]}; P/S "
            f"{[round(i.ps, 1) for i in listed if i.ps is not None]}"
        )
    rows.append(f"T2 median first-day return {t2_first_day(r):+.1%} (0% to 30%)")
    rows.append(
        f"T3 guiding 10% above trend misses {t3_miss_share(r):.0%} of quarters (>= 60%); median "
        f"price after 3 years {t3_price_ratio(r):.2f} x guiding at trend (<= 0.85)"
    )
    m = r.t4
    drop = 1 - m.dec_2022 / m.jan_2022
    rows.append(
        f"T4 reference listing (growth {m.growth:.0%}, margin {m.margin:+.0%}): median P/S "
        f"{m.early:.1f}x 2012-2019 (4-15), {m.late:.1f}x 2020-2021 (8-25); Jan 2022 "
        f"{m.jan_2022:.1f}x, Dec 2022 {m.dec_2022:.1f}x, fall {drop:.0%} (>= 30%)"
    )
    rows.append(
        f"T5 CEO score {T5_SCORE:g} with full authority: median ARR {t5_arr_ratio(r):.2f} x the "
        f"steady script's over {T5_MONTHS} months (0.85-1.15); the Chair spent at most "
        f"{t5_spent(r):.0%} of their energy (<= 40%)"
    )
    return "\n".join(rows)
