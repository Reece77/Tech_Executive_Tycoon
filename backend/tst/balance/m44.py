"""M44's balance targets (docs/formulas.md 57.6), printed by tools/m44_targets.py.

Each seed's world is played by the engine from January 2010 to December 2025 with the player's
company doing nothing (so history holds), then:

1. **History holds** (printed): the player doing nothing, the same seed's 24 months from January
   2026 with government.yaml and without it give identical books for every company and identical
   player snapshots (a company that never bids plays exactly as before).
2. **A real but slow customer:** from January 2026, a US company (stage 4) with live cloud, AI and
   cyber products of quality 80, a data centre in the US, a cleared facility, six staff cleared at
   Top Secret and three sellers on every capture team bids on every announced US-aligned tender
   in those areas for 36 months at 90% of the tender's value. "Veteran": with three completed
   contracts at performance 90 (past performance); "newcomer": without. The veteran's share of
   decided bids won (median over seeds) must be at least 25%; the newcomer's share of large
   tenders won (`government.tenders.large_cents`, all seeds pooled) at most 10%.
3. **Clearances take time:** January 2027, every person in the world asked for (Top Secret and
   Secret): the median months to a decision must be 6-15 and at least 5% must never clear.
4. **It costs something:** January 2026, a consumer-heavy company (a live consumer app and a
   device of brand 60, a stage-3 core team) wins a US defence award: its consumer lines' brand
   loss must be 1-3 points and an open letter must follow on at least 5 of 10 seeds.
5. **Turn time:** the mean wall-clock time of a turn in target 2's veteran run (the guards
   themselves are M30's `make check-timing`).
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

import tst.sim.actions  # noqa: F401  (government.actions is imported through the actions package)
from tst.balance.fixtures import add_team, hire
from tst.balance.game import PLAYER, Game, start_game
from tst.loader import LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.government import clearances as gc
from tst.sim.government import reputation
from tst.sim.government.actions import PlaceBid
from tst.sim.government.data import announced, area_of, file, is_large
from tst.sim.government.models import Clearance, Contract, FacilityClearance
from tst.sim.ledger import CASH
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_company, with_facility, with_person_state, with_product

SEEDS: Final = tuple(range(1, 11))
DATA: Final = Path(__file__).resolve().parents[2] / "data"
RICH: Final = 10**13
START: Final = ym_to_turn(2026, 1)
CLEARANCE_TURN: Final = ym_to_turn(2027, 1)
BID_MONTHS: Final = 36
SAME_MONTHS: Final = 24
AREAS: Final = ("cloud", "ai", "cyber")
QUALITY: Final = 80.0
PRICE: Final = 0.9
CLEARED: Final = 6
SELLERS: Final = 3
VETERAN_PP: Final = 90.0
WIN_FLOOR: Final = 0.25  # 57.6 target 2
NEWCOMER_LARGE_CAP: Final = 0.10
CLEAR_MONTHS: Final = (6.0, 15.0)  # target 3
NEVER_FLOOR: Final = 0.05
BRAND_BAND: Final = (1.0, 3.0)  # target 4
LETTER_SEEDS: Final = 5
DC_ID: Final = 10**6 + 44


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


def world(seed: int, *, without_government: bool = False) -> Game:
    state, balances = pickle.loads(_world_bytes(seed))
    data = loaded()
    if without_government:
        data = replace(data, game_data=data.game_data.model_copy(update={"government": None}))
    return Game(data, state, balances)


def product(
    state: GameState, category: str, name: str, quality: float, brand: float = 50.0
) -> tuple[GameState, int]:
    pid, ids = state.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name=name,
        status="live",
        quality=quality,
        feature_points=500.0,
        brand=brand,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    return replace(with_product(state, p), next_ids=ids), pid


def data_centre(state: GameState) -> GameState:
    return with_facility(
        state,
        Facility(
            id=DC_ID,
            company_id=PLAYER,
            kind="data_centre_general",
            region="north_america",
            capacity=1000,
            on_time=1000,
            ordered_turn=state.turn,
            ready_turn=state.turn,
            late_turn=state.turn,
            capex_cents=10**9,
            input_index=1.0,
            capex_paid_cents=10**9,
            status="live",
        ),
    )


def bidder(g: Game, *, veteran: bool) -> tuple[list[int], dict[str, int]]:
    """Target 2's company (module docstring): its sellers and its products by area."""
    s = with_company(g.state, replace(g.state.player, stage=4))
    products = {}
    for area, cat, name in (
        ("cloud", "cloud_hosting", "GovCloud"),
        ("ai", "ai_models", "Analyst"),
        ("cyber", "cybersecurity", "Shield"),
    ):
        s, products[area] = product(s, cat, name, QUALITY)
    s = data_centre(s)
    s, sellers = hire(
        s, g.loaded, "account_executive", "senior", SELLERS, "Capture", 15_000_000, 44
    )
    s, cleared = hire(
        s, g.loaded, "software_engineer", "senior", CLEARED, "Cleared", 16_000_000, 45
    )
    s = replace(
        s,
        clearances=tuple(
            Clearance(
                pid, PLAYER, "top_secret", s.turn - 12, s.turn - 1, "cleared", "cleared", s.turn - 1
            )
            for pid in cleared
        ),
        facility_clearances=(FacilityClearance(DC_ID, PLAYER, s.turn - 12, s.turn - 1, "cleared"),),
    )
    if veteran:
        s = replace(
            s,
            gov_contracts=tuple(
                Contract(
                    id=90 + i,
                    tender_id=0,
                    company_id=PLAYER,
                    product_id=products["cloud"],
                    government="us",
                    area="cloud",
                    buyer="civil",
                    contract="fixed_price",
                    value_cents=10**9,
                    start_turn=s.turn - 60,
                    base_end_turn=s.turn - 24,
                    end_turn=s.turn - 24,
                    status="completed",
                    performance=VETERAN_PP,
                    months=36,
                )
                for i in range(3)
            ),
        )
    g.state = s
    return sellers, products


def _refill(g: Game) -> None:
    founder = g.state.founder_of(PLAYER)
    if founder is None:
        return
    ps = g.state.person_state(founder.id)
    if ps.energy is not None:
        g.state = with_person_state(
            g.state, replace(ps, energy=g.loaded.balance.founder.energy_per_month)
        )


@dataclass(frozen=True, slots=True)
class BidRun:
    won: int
    decided: int
    large_won: int
    large_decided: int
    turn_seconds: float


def bid_run(seed: int, *, veteran: bool) -> BidRun:
    g = world(seed)
    sellers, products = bidder(g, veteran=veteran)
    d = g.loaded.game_data
    f = file(d)
    b = g.loaded.balance
    times = []
    for _ in range(BID_MONTHS):
        _refill(g)
        founder = g.state.founder_of(PLAYER)
        assert founder is not None
        for t in g.state.tenders:
            if t.area not in AREAS or not announced(t, g.state.turn) or t.status != "open":
                continue
            if (
                g.state.turn >= t.close_turn
                or "us_aligned" not in f.government(t.government).open_to
            ):
                continue
            if any(x.tender_id == t.id for x in g.state.gov_bids):
                continue
            pid = products[t.area]
            g.act(PlaceBid(founder.id, t.id, pid, round(t.value_cents * PRICE), tuple(sellers)))
        t0 = time.perf_counter()
        g.turn()
        times.append(time.perf_counter() - t0)
    tenders = {t.id: t for t in g.state.tenders}
    won = decided = lw = ld = 0
    for x in g.state.gov_bids:
        if x.status not in ("won", "lost", "disqualified"):
            continue
        decided += 1
        won += x.status == "won"
        tender = tenders.get(x.tender_id)
        if tender is not None and is_large(tender, b):
            ld += 1
            lw += x.status == "won"
    del d
    return BidRun(won, decided, lw, ld, sum(times) / len(times))


def clearance_draws(seed: int) -> tuple[list[float], int, int]:
    g = world(seed)
    s = g.state
    while s.turn < CLEARANCE_TURN:
        s = replace(s, turn=s.turn + 1)  # the draw reads the request month only
    rng = RngFactory(s.save_meta.master_seed)
    months, never, n = [], 0, 0
    for level in ("top_secret", "secret"):
        for p in s.people:
            c = gc.draw_clearance(s, p.id, PLAYER, level, rng, g.loaded.balance, g.loaded.game_data)
            n += 1
            if c.outcome == "denied":
                never += 1
            else:
                months.append(float(c.due_turn - c.requested_turn))
    return months, never, n


def reaction(seed: int) -> tuple[float, bool]:
    """Target 4: (brand points lost on the consumer lines, an open letter queued)."""
    g = world(seed)
    g.state = with_company(g.state, replace(g.state.player, stage=3))
    add_team(g)
    s, app = product(g.state, "consumer_apps", "Snap", 70.0, brand=60.0)
    s, dev = product(s, "devices", "Phone", 70.0, brand=60.0)
    contract = Contract(
        id=1,
        tender_id=0,
        company_id=PLAYER,
        product_id=dev,
        government="us",
        area="devices",
        buyer="defence",
        contract="fixed_price",
        value_cents=10**9,
        start_turn=s.turn + 1,
        base_end_turn=s.turn + 37,
        end_turn=s.turn + 61,
    )
    s = replace(s, gov_contracts=(contract,))
    before = s.product(app)
    after, _ = reputation.on_defence_award(
        s, contract, RngFactory(s.save_meta.master_seed), g.loaded.balance, g.loaded.game_data
    )
    assert before is not None
    lost = before.brand - after.product(app).brand  # type: ignore[union-attr]
    record = after.defence_record(PLAYER)
    return lost, record is not None and record.letter_turn is not None


def same_books(seed: int) -> bool:
    """Target 1: identical books and player snapshots with and without government.yaml."""
    a, b = world(seed), world(seed, without_government=True)
    for _ in range(SAME_MONTHS):
        a.turn()
        b.turn()
    snaps_a = [replace(x) for x in a.snapshots]
    return a.balances == b.balances and snaps_a == b.snapshots


@dataclass(frozen=True, slots=True)
class SeedRun:
    seed: int
    same: bool
    veteran: BidRun
    newcomer: BidRun
    clear_months: tuple[float, ...]
    never: int
    asked: int
    brand_lost: float
    letter: bool


def run_seed(seed: int) -> SeedRun:
    months, never, n = clearance_draws(seed)
    lost, letter = reaction(seed)
    return SeedRun(
        seed=seed,
        same=same_books(seed),
        veteran=bid_run(seed, veteran=True),
        newcomer=bid_run(seed, veteran=False),
        clear_months=tuple(months),
        never=never,
        asked=n,
        brand_lost=lost,
        letter=letter,
    )


@dataclass(frozen=True, slots=True)
class Results:
    runs: tuple[SeedRun, ...]


def run(seeds: Sequence[int] = SEEDS, jobs: int = os.cpu_count() or 1) -> Results:
    if jobs <= 1:
        return Results(tuple(run_seed(s) for s in seeds))
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return Results(tuple(pool.map(run_seed, seeds)))


def _share(a: int, b: int) -> float:
    return a / b if b else 0.0


def report(r: Results) -> str:
    lines = [
        "M44 balance targets (formulas.md 57.6), seeds " + ", ".join(str(x.seed) for x in r.runs)
    ]
    for x in r.runs:
        lines.append(
            f"  seed {x.seed}: same books {x.same}; veteran won {x.veteran.won}/{x.veteran.decided}"
            f" ({_share(x.veteran.won, x.veteran.decided):.0%}), newcomer large"
            f" {x.newcomer.large_won}/{x.newcomer.large_decided}; clearance median"
            f" {median(x.clear_months):.1f} months, never {_share(x.never, x.asked):.1%};"
            f" brand lost {x.brand_lost:.1f}, letter {x.letter};"
            f" {x.veteran.turn_seconds * 1000:.0f} ms a turn"
        )
    same = all(x.same for x in r.runs)
    win = median(_share(x.veteran.won, x.veteran.decided) for x in r.runs)
    lw = sum(x.newcomer.large_won for x in r.runs)
    ld = sum(x.newcomer.large_decided for x in r.runs)
    months = [m for x in r.runs for m in x.clear_months]
    med = median(months) if months else 0.0
    never = _share(sum(x.never for x in r.runs), sum(x.asked for x in r.runs))
    brands = [x.brand_lost for x in r.runs]
    letters = sum(x.letter for x in r.runs)
    ms = median(x.veteran.turn_seconds for x in r.runs) * 1000

    def ok(cond: bool) -> str:
        return "met" if cond else "MISSED"

    n = len(r.runs)
    large = _share(lw, ld)
    brand_ok = all(BRAND_BAND[0] <= v <= BRAND_BAND[1] for v in brands)
    lo, hi = CLEAR_MONTHS
    lines += [
        f"1 History holds: identical books without bids on {sum(x.same for x in r.runs)}/{n}"
        f" seeds: {ok(same)}",
        f"2 A real but slow customer: veteran median win share {win:.0%} (>= {WIN_FLOOR:.0%}):"
        f" {ok(win >= WIN_FLOOR)}; newcomer large {lw}/{ld} = {large:.0%}"
        f" (<= {NEWCOMER_LARGE_CAP:.0%}): {ok(large <= NEWCOMER_LARGE_CAP)}",
        f"3 Clearances take time: median {med:.1f} months ({lo:.0f}-{hi:.0f}):"
        f" {ok(lo <= med <= hi)}; never clear {never:.1%} (>= {NEVER_FLOOR:.0%}):"
        f" {ok(never >= NEVER_FLOOR)}",
        f"4 It costs something: brand lost {min(brands):.1f}-{max(brands):.1f}"
        f" ({BRAND_BAND[0]:.0f}-{BRAND_BAND[1]:.0f}): {ok(brand_ok)}; a letter on {letters}/{n}"
        f" seeds (>= {LETTER_SEEDS}): {ok(letters >= LETTER_SEEDS)}",
        f"5 Turn time: {ms:.0f} ms a turn (2026-2028, a bidding company; guards: make"
        " check-timing)",
    ]
    return "\n".join(lines)


__all__ = ["area_of"]
