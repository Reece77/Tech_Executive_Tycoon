"""M55's balance targets (docs/formulas.md 65.8), printed by tools/m55_targets.py.

Each seed's world is played by the engine from January 2010 with the player's company doing nothing
until the script's start (so history holds); then:

2. **Hits rule:** from January 2016 a studio green-lights a slate of titles (series, films and
   premium games at their kinds' typical budgets, each with a signed creative lead) every quarter
   for ten years, licensing series and films out; to December 2039 the titles' booked revenue: the
   top 20% of titles earn at least 60% of it (median of seeds), and at least a third earn less than
   they cost.
3. **Content is capital-heavy:** from January 2026 a new video service in North America (at the
   market's reference price) spends $1B a year (real, x scale) on content: series and films on its
   own service, a twelfth of the year's budget green-lit each month (no leads, no units). The months
   from its launch to its cumulative cash at or above zero (revenue less content, hosting and
   marketing), median at least 60.
4. **Networks tip:** a social network in North America from January 2026, pushed to about 5% of the
   region's users by marketing for two years; then (a) on the format it launched with: it loses
   users in each of the next three years; (b) switched to each new format era when it arrives: it
   grows over the era's advantage years on at least 6 of 10 seeds.
5. **Egos bite:** from January 2026 a studio signs the lead with the highest hidden ego on offer
   (the script reads it; a player never can) and green-lights a series; (a) left alone, (b)
   overruled twice in its first two months: (b)'s quality at release is at least 10% under (a)'s
   (median), and the lead walks on at least 3 of 10 seeds.
6. **Turn time:** the mean wall-clock time of a turn from 2026 to 2030 in target 3's worlds.
"""

from __future__ import annotations

import pickle
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import cache
from itertools import pairwise
from pathlib import Path
from statistics import median
from typing import Final

import tst.sim.actions  # noqa: F401
from tst.balance.game import PLAYER, Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.calendar import turn_to_ym, ym_to_turn
from tst.sim.geo.models import ProductRegion, RegionalSegment
from tst.sim.ledger import CASH
from tst.sim.media import social, streaming, talent, titles
from tst.sim.media.actions import GreenlightTitle, OverruleLead, SetMediaLine, SignLead
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_company, with_person_state, with_product, with_segments

SEEDS: Final = tuple(range(1, 11))
DATA: Final = Path(__file__).resolve().parents[2] / "data"
RICH: Final = 10**15
NA: Final = "north_america"
QUALITY: Final = 70.0
START_2016: Final = ym_to_turn(2016, 1)
START_2026: Final = ym_to_turn(2026, 1)
END: Final = ym_to_turn(2039, 12)
SLATE_END: Final = ym_to_turn(2025, 12)
TOP_SHARE: Final = 0.60
FLOP_SHARE: Final = 1 / 3
PAYBACK_MONTHS: Final = 60
QUALITY_CUT: Final = 0.10
WALKS: Final = 3
GROWS: Final = 6
BUDGET_YEAR_CENTS: Final = 100_000_000_000  # $1B a year, real (target 3)
PUSH_MONTHS: Final = 24
PUSH_BUDGET_CENTS: Final = 2_000_000_000  # a month's marketing on the network (target 4)
TIMING_END: Final = ym_to_turn(2030, 12)


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


@cache
def _world_bytes(seed: int, until: int) -> bytes:
    g = start_game(loaded(), seed, "funded_spinout")
    g.balances[(PLAYER, CASH)] = g.balances.get((PLAYER, CASH), 0) + RICH
    while g.state.turn < until:
        g.turn()
    return pickle.dumps((g.state, g.balances))


def world(seed: int, until: int) -> Game:
    state, balances = pickle.loads(_world_bytes(seed, until))
    g = Game(loaded(), state, balances)
    g.state = with_company(g.state, replace(g.state.player, stage=4))
    return g


def line(
    state: GameState, category: str, name: str, regions: Sequence[str] = (NA,)
) -> tuple[GameState, int]:
    """A live line of the player's (as M53's script's) at the market's reference price."""
    d = loaded().game_data
    pid, ids = state.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name=name,
        status="live",
        quality=QUALITY,
        feature_points=0.0,
        brand=70.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
        held_feature=QUALITY,
    )
    cat = d.category(category)
    segs = [
        ProductSegment(pid, m.segment, m.reference_price_cents, 0.0, False, state.turn)
        for m in cat.markets
    ]
    state = replace(with_product(state, p), next_ids=ids)
    regional = [
        RegionalSegment(pid, r, s.segment, s.price_cents, 0.0, False, state.turn)
        for r in regions
        if r != NA
        for s in segs
    ]
    state = with_segments(state, segs, regional)
    from tst.sim.state import with_product_region

    for r in regions:
        if r != NA:
            state = with_product_region(state, ProductRegion(pid, r, state.turn, state.turn))
    return state, pid


def _energy(g: Game) -> None:
    ps = g.state.person_state(g.founder_id)
    g.state = with_person_state(g.state, replace(ps, energy=99))


def sign_best(g: Game, *, by_ego: bool = False) -> int | None:
    """Sign the open lead with the best creative + vision (or the highest hidden ego) for five
    years; the person id."""
    rng = RngFactory(g.state.save_meta.master_seed)
    b, d = loaded().balance, loaded().game_data
    best = None
    for o in g.state.media.offers:
        if o.status != "open":
            continue
        c = talent.candidate(o, rng, b, d)
        score = c.ego if by_ego else c.creative + c.vision
        if best is None or score > best[0]:
            best = (score, o)
    if best is None:
        return None
    _energy(g)
    o = best[1]
    before = {x.person_id for x in g.state.media.leads}
    if not g.act(SignLead(g.founder_id, o.year, o.n, 5)):
        return None
    new = [x.person_id for x in g.state.media.leads if x.person_id not in before]
    return new[0] if new else None


def free_lead(g: Game) -> int | None:
    busy = {t.lead_person_id for t in g.state.media.titles if t.stage == "development"}
    for x in g.state.media.leads:
        if x.company_id == PLAYER and x.person_id not in busy:
            return x.person_id
    return None


def greenlight(
    g: Game, kind: str, budget: int | None = None, lead: int | None = None, **kw: object
) -> int | None:
    b = loaded().balance
    k = b.media.kind(kind)
    cents = budget if budget is not None else titles.typical_budget_cents(k, b)
    _energy(g)
    n = g.state.media.next_title_id()
    name = f"{kind.title()} {n}"
    ok = g.act(
        GreenlightTitle(g.founder_id, name, kind, cents, lead_person_id=lead, **kw)  # type: ignore[arg-type]
    )
    return n if ok else None


# --- target 2 ------------------------------------------------------------------------------------


def hits_run(seed: int) -> list[tuple[int, int]]:
    """Target 2's studio: each title's (revenue booked, cost)."""
    g = world(seed, START_2016)
    kinds = ("series", "film", "game")
    i = 0
    while g.state.turn <= END:
        turn = g.state.turn
        if turn <= SLATE_END and turn_to_ym(turn)[1] in (1, 4, 7, 10):
            lead = free_lead(g) or sign_best(g)
            kind = kinds[i % len(kinds)]
            platforms = ("pc", "console") if kind == "game" else ()
            greenlight(g, kind, lead=lead, platforms=platforms)
            i += 1
        g.turn()
    return [
        (t.revenue_cents, t.budget_cents) for t in g.state.media.titles if t.stage == "released"
    ]


def hits_measure(rows: list[tuple[int, int]]) -> tuple[float, float]:
    """(top 20%'s share of revenue, share of titles under their cost)."""
    revenue = sorted((r for r, _ in rows), reverse=True)
    top = revenue[: max(1, round(len(revenue) * 0.2))]  # tunable-exempt: the top 20%
    share = sum(top) / max(1, sum(revenue))
    flops = sum(1 for r, c in rows if r < c) / max(1, len(rows))
    return share, flops


# --- target 3 ------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Service:
    payback: int | None
    ms_per_turn: float


def service_run(seed: int) -> Service:
    b = loaded().balance
    g = world(seed, START_2026)
    g.state, pid = line(g.state, b.media.streaming, "Nova Stream")
    monthly = BUDGET_YEAR_CENTS * b.media.scale / 12
    series = titles.typical_budget_cents(b.media.kind("series"), b)
    t0 = time.perf_counter()
    timed = 0
    start = g.state.turn
    spent = 0.0
    while g.state.turn <= END:
        spent += monthly
        while spent >= series:
            greenlight(g, "series", budget=series, window="own", service_product_id=pid)
            spent -= series
        g.turn()
        if g.state.turn <= TIMING_END:
            timed += 1
            if g.state.turn == TIMING_END:
                t1 = time.perf_counter()
    pb = next((x.turn for x in g.state.media.paid_back if x.product_id == pid), None)
    ms = (t1 - t0) / max(1, timed) * 1000
    return Service(pb - start if pb is not None else None, ms)


# --- target 4 ------------------------------------------------------------------------------------


def network_run(seed: int, switch: bool) -> tuple[list[float], bool]:
    """A North American network's users each January after its push, and whether it grew over an
    advantage window (arm b)."""
    b, d = loaded().balance, loaded().game_data
    g = world(seed, START_2026)
    g.state, pid = line(g.state, b.media.social, "Nova Social")
    product = g.state.product(pid)
    assert product is not None
    g.state = with_product(g.state, replace(product, marketing_budget_cents=PUSH_BUDGET_CENTS))
    users: list[float] = []
    grew = False
    window_start: float | None = None
    window_end: int | None = None
    while g.state.turn <= END:
        if g.state.turn == START_2026 + PUSH_MONTHS:
            p = g.state.product(pid)
            assert p is not None
            g.state = with_product(g.state, replace(p, marketing_budget_cents=0))
        if switch and g.state.turn > START_2026 + PUSH_MONTHS:
            eras = social.eras(g.state, d)
            p = g.state.product(pid)
            assert p is not None
            newest, since = eras[-1]
            if since == g.state.turn and social.line_format(p, g.state, d) != newest:
                _energy(g)
                g.act(SetMediaLine(g.founder_id, pid, format=newest))
                window_start = streaming.customers(g.state, p)
                window_end = since + round(b.media.social_network.advantage_years * 12)
        p = g.state.product(pid)
        assert p is not None
        if window_end is not None and g.state.turn == window_end and window_start is not None:
            grew = grew or streaming.customers(g.state, p) > window_start
            window_end = None
        if turn_to_ym(g.state.turn)[1] == 1 and g.state.turn > START_2026 + PUSH_MONTHS:
            users.append(streaming.customers(g.state, p))
        g.turn()
    return users, grew


# --- target 5 ------------------------------------------------------------------------------------


def ego_run(seed: int, overrule: bool) -> tuple[float, bool]:
    """(the series' quality at release, the lead walked)."""
    g = world(seed, START_2026)
    lead = sign_best(g, by_ego=True)
    tid = greenlight(g, "series", lead=lead)
    walked = False
    while g.state.turn <= END:
        t = g.state.media.title(tid) if tid is not None else None
        if t is None:
            break
        if overrule and t.overrules < 2 and t.stage == "development":  # tunable-exempt: twice
            _energy(g)
            g.act(OverruleLead(g.founder_id, t.id))
            t = g.state.media.title(t.id)
            assert t is not None
        if t.walked_turn is not None:
            walked = True
        if t.stage == "released":
            return t.quality or 0.0, walked
        g.turn()
    return 0.0, walked


# --- the table ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeedResult:
    seed: int
    hits: tuple[float, float]
    service: Service
    network_a: tuple[list[float], bool]
    network_b: tuple[list[float], bool]
    ego_a: tuple[float, bool]
    ego_b: tuple[float, bool]


def _seed(seed: int) -> SeedResult:
    return SeedResult(
        seed=seed,
        hits=hits_measure(hits_run(seed)),
        service=service_run(seed),
        network_a=network_run(seed, False),
        network_b=network_run(seed, True),
        ego_a=ego_run(seed, False),
        ego_b=ego_run(seed, True),
    )


def run(seeds: Sequence[int] = SEEDS, workers: int = 4) -> list[SeedResult]:
    with ProcessPoolExecutor(workers) as pool:
        return list(pool.map(_seed, seeds))


def _yes(ok: bool) -> str:
    return "yes" if ok else "no"


def _falls(users: list[float]) -> bool:
    """The network's users fell in each of the three years after its push."""
    years = users[:4]  # tunable-exempt: the push's end and three Januaries after
    return len(years) == 4 and all(b < a for a, b in pairwise(years))  # tunable-exempt: as above


def table(rows: list[SeedResult]) -> str:
    top = median(r.hits[0] for r in rows)
    flops = median(r.hits[1] for r in rows)
    pays = [r.service.payback for r in rows]
    pay = median(p if p is not None else 10**6 for p in pays)
    ms = median(r.service.ms_per_turn for r in rows)
    falls = sum(1 for r in rows if _falls(r.network_a[0]))
    grows = sum(1 for r in rows if r.network_b[1])
    qa = median(r.ego_a[0] for r in rows)
    qb = median(r.ego_b[0] for r in rows)
    walks = sum(1 for r in rows if r.ego_b[1])
    cut = 1 - qb / qa if qa else 0.0
    n = len(rows)
    lines = [
        "| Target | Band | Reading | Met |",
        "| --- | --- | --- | --- |",
        f"| 2a top 20% of titles' revenue | >= 60% | {top:.0%} | {_yes(top >= TOP_SHARE)} |",
        f"| 2b titles under their cost | >= 33% | {flops:.0%} | {_yes(flops >= FLOP_SHARE)} |",
        f"| 3 a $1B-a-year service's payback | >= 60 months | {pay} months ({pays}) "
        f"| {_yes(pay >= PAYBACK_MONTHS)} |",
        f"| 4a a small network on its old format loses users each year | most seeds "
        f"| {falls} of {n} | {_yes(falls > n / 2)} |",
        f"| 4b with a format advantage it grows | >= 6 of 10 | {grows} of {n} "
        f"| {_yes(grows >= GROWS)} |",
        f"| 5a two overrules' quality cut | >= 10% | {cut:.0%} ({qa:.2f} to {qb:.2f}) "
        f"| {_yes(cut >= QUALITY_CUT)} |",
        f"| 5b the lead walks | >= 3 of 10 | {walks} of {n} | {_yes(walks >= WALKS)} |",
        f"| 6 turn time | the guards | {ms:.0f} ms a turn (2026-2030, a video service) "
        "| see make check-timing |",
    ]
    return "\n".join(lines)
