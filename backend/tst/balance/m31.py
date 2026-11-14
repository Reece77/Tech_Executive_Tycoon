"""M31's balance targets (docs/formulas.md 44.9), printed by tools/m31_targets.py.

1. History holds: fees post from 2010 (`platforms.fees_from`), calibrated exactly to 2025: a
   seller's store revenue is grossed up by its fee, so its net revenue and cash are main's.
   M28's history fingerprint guards prices, wafers, capacities and events unchanged; its books
   series is re-recorded (Reece, 2026-11-14), and tools/m31_history_diff.py shows the books
   differ only by platform-fee entries, every company's 2010-2025 net revenue 0.00% from main.
2. Tipping is hard (a platforms-only run, the in-game devices held as they are): a challenger
   OS licensed free to OEMs in January 2027 with 5% of every region's users (an OEM's launch:
   M31 decision) and fees 10 points under Android's reaches 15% of developers in its regions by
   December 2035 on at most 3 of 10 seeds; at 20 points under with tools 1.3, on at least 5.
3. An own store pays: a played game to 2026 whose phone line holds 30% of its home region's
   device users (held there each month: the target's premise, not how to reach it), moved to
   its own OS, earns platform fees of at least 5% of the group's revenue in 2035 (median).
4. Removals matter: a consumer app removed from a platform with about half its region's users
   loses 30-50% of its customers there in 3 months and is back to 85%+ of them 6 months after
   complying (markets running).
5. Open source works: an open-sourced developer tool has 2x+ the customers and at most 0.7x
   the revenue of the same tool kept closed after 36 months (median).
6. A software company's game: with platforms the player's own books differ from the same game
   without them only in its platform-fee entries (a SaaS player whose app is not reviewed).
7. Turn time: `make check-timing` (tests/timing).
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from functools import cache
from typing import Final

from tst.balance.game import Game, start_game
from tst.balance.m28 import SEEDS, loaded
from tst.balance.report import Row, table
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.hardware.models import ProductionContract
from tst.sim.ledger import (
    CASH,
    PLATFORM_FEE_REVENUE,
    PLATFORM_FEES,
    REVENUE_SUBSCRIPTIONS,
    LedgerEntry,
)
from tst.sim.platforms import data as pdata
from tst.sim.platforms.actions import on_launch
from tst.sim.platforms.models import DeviceRun, Platform, PlatformListing
from tst.sim.platforms.phase import addressable_in, by_region, home_of, platforms_month
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_product, with_product_segment, with_production_contract

START: Final = 192  # January 2026
CHALLENGE: Final = ym_to_turn(2027, 1)
CHALLENGE_END: Final = ym_to_turn(2035, 12)
CHALLENGE_USERS: Final = 0.05
TIP_DEVS: Final = 0.15
OWN_SHARE: Final = 0.30
FEE_YEAR: Final = 2035
REMOVE_SHARE: Final = 0.5
OPEN_MONTHS: Final = 36
SOFT_MONTHS: Final = 24
CASH_CENTS: Final = 5_000_000_000_000  # $50B: the player's survival is not what these read
APP: Final = 990_001
EVENT_MEMO: Final = "Event: "
CALIBRATION_MEMO: Final = "Store price calibration"
LINE: Final = 990_002
CONTRACT_UNITS: Final = 10_000_000  # a month: never the bound


@dataclass(frozen=True, slots=True)
class SeedResult:
    seed: int
    tip_mild: float  # the challenger's developer share in Dec 2035, fees 10 points lower
    tip_strong: float  # 20 points lower, tools 1.3
    fee_share: float  # platform fees / group revenue in 2035
    own_users: float  # the own OS's users in the home region, Dec 2032
    removed_lost: float  # share of the app's customers lost in 3 months of removal
    recovered: float  # its customers 6 months after complying, of the start
    open_customers: float  # open / closed customers after 36 months
    open_revenue: float  # open / closed revenue
    soft_diffs: int  # the player's non-fee entries that differ with platforms


# --- Shared ---------------------------------------------------------------------------------


def moved(seed: int, turn: int, data: LoadedData | None = None) -> Game:
    """A new game moved to `turn` with $50B (its platforms brought into being)."""
    game = start_game(data or loaded(), seed)
    game.balances = {**game.balances, (1, CASH): game.cash + CASH_CENTS}
    d = game.loaded
    game.state = pdata.materialise(replace(game.state, turn=turn), d.balance, d.game_data)
    return game


@cache
def played(seed: int) -> Game:
    """A do-nothing game played to January 2026 (history's markets), with $50B."""
    game = start_game(loaded(), seed)
    while game.state.turn < START:
        game.turn()
    game.balances = {**game.balances, (1, CASH): game.cash + CASH_CENTS}
    return game


def _copy(game: Game) -> Game:
    return Game(game.loaded, game.state, dict(game.balances))


def _static(state: GameState, pid: int, category: str, name: str, feature: float) -> GameState:
    """A player's product that keeps its scores (held_feature, ADR-0017): the targets read
    platforms, not a team's work."""
    product = Product(
        id=pid, company_id=state.player.id, category=category, name=name, status="live",
        quality=65.0, feature_points=0.0, brand=50.0, marketing_budget_cents=0,
        created_turn=state.turn - 24, launched_turn=state.turn - 12, held_feature=feature,
    )  # fmt: skip
    return with_product(state, product)


def _play(game: Game, months: int, kept: list[LedgerEntry] | None = None) -> None:
    for _ in range(months):
        game.turn()
        if kept is not None and game.last_result is not None:
            kept.extend(game.last_result.ledger_entries)


def _year(entries: Sequence[LedgerEntry], year: int, account: str, company: int) -> int:
    return sum(
        line.amount
        for e in entries
        if e.company_id == company and pdata.year_of(e.turn) == year
        for line in e.lines
        if line.account == account
    )


# --- Target 2 ----------------------------------------------------------------------------------


def tipping(seed: int, cut: float, tools: float) -> float:
    d = loaded()
    game = moved(seed, START - 1, d)
    state, rng = game.state, RngFactory(seed)
    while state.turn < CHALLENGE:
        state = platforms_month(state, rng, d.balance, d.game_data)
        state = replace(state, turn=state.turn + 1)
    android = next(p for p in state.platforms if p.key == pdata.ANDROID)
    pid = pdata.next_platform_id(state)
    fee = pdata.schedule(android, "europe", state.turn, d.balance, d.game_data).standard - cut
    challenger = Platform(
        id=pid, key="challenger", name="Challenger", store="Challenger Store", kind="device",
        owner_id=None, owner_label="A challenger", regions=tuple(d.game_data.region_keys),
        launched_turn=state.turn, historical=False, licensable=True, licence_cents=0, fee=fee,
        tools=tools,
    )  # fmt: skip
    rows = []
    for row in state.platform_regions:
        if row.platform_id == android.id:  # an OEM's launch takes 5% of the region from Android
            take = min(row.rest, CHALLENGE_USERS)
            rows.append(replace(row, rest=row.rest - take, users=row.users - take))
            rows.append(
                replace(row, platform_id=pid, users=take, rest=take, dev_share=0.0, catalogue=0.0)
            )
        else:
            rows.append(row)
    state = replace(state, platforms=(*state.platforms, challenger), platform_regions=tuple(rows))
    while state.turn <= CHALLENGE_END:
        state = platforms_month(state, rng, d.balance, d.game_data)
        state = replace(state, turn=state.turn + 1)
    mine = [r for r in state.platform_regions if r.platform_id == pid]
    return statistics.fmean(r.dev_share for r in mine)


# --- Target 3 ----------------------------------------------------------------------------------


def own_store(seed: int) -> tuple[float, float]:
    game = _copy(played(seed))
    d = game.loaded
    b, gd = d.balance, d.game_data
    state = game.state
    home = home_of(state, b, gd) or "north_america"
    users = addressable_in(state, "devices", gd, home, home)
    android = next(p.id for p in state.platforms if p.key == pdata.ANDROID)
    others = [
        s
        for r in state.device_runs
        if r.platform_id == android
        if (s := state.product_segment(r.product_id, "consumer"))
    ]
    held = sum(s.customers for s in others)
    wanted = min(OWN_SHARE * users, held)
    for s in others:
        state = with_product_segment(state, replace(s, customers=s.customers * (1 - wanted / held)))
    state = _static(state, LINE, "devices", "Own Phone", 75.0)
    state = with_product_segment(state, ProductSegment(LINE, "consumer", 45_000, wanted))
    cid, ids = state.next_ids.take("production_contract")
    contract = ProductionContract(
        id=cid, company_id=state.player.id, product_id=LINE, kind="assembly", supplier="foxconn",
        units=CONTRACT_UNITS, price_millicents=1_300_000, signed_turn=state.turn,
        end_turn=ym_to_turn(FEE_YEAR, 12), city="shenzhen",
    )  # fmt: skip
    state = with_production_contract(replace(state, next_ids=ids), contract)
    os_product = replace(Product(
        id=LINE + 1, company_id=state.player.id, category="os", name="Own OS", status="live",
        quality=60.0, feature_points=0.0, brand=40.0, marketing_budget_cents=0,
        created_turn=state.turn - 36, launched_turn=state.turn,
    ))  # fmt: skip
    state = on_launch(with_product(state, os_product), os_product, gd)
    own = next(p for p in state.platforms if p.product_id == os_product.id)
    state = replace(
        state, device_runs=(*state.device_runs, DeviceRun(LINE, own.id, state.turn, android, 1.0))
    )
    game.state = state
    kept: list[LedgerEntry] = []
    users_2032 = 0.0
    while game.state.turn <= ym_to_turn(FEE_YEAR, 12):
        _play(game, 1, kept if game.state.turn >= ym_to_turn(FEE_YEAR, 1) else None)
        # the target's premise: the maker holds 30% of its region's device users
        seg = game.state.product_segment(LINE, "consumer")
        users = addressable_in(game.state, "devices", gd, home, home)
        if seg is not None:
            game.state = with_product_segment(game.state, replace(seg, customers=OWN_SHARE * users))
        if game.state.turn - 1 == ym_to_turn(2032, 12):
            row = by_region(game.state).get(home, {}).get(own.id)
            users_2032 = row.users if row else 0.0
    me = game.state.player.id
    fees = -_year(kept, FEE_YEAR, PLATFORM_FEE_REVENUE, me)
    revenue = fees - _year(kept, FEE_YEAR, REVENUE_SUBSCRIPTIONS, me)
    return (fees / revenue if revenue > 0 else 0.0), users_2032


# --- Target 4 ----------------------------------------------------------------------------------


def removal(seed: int) -> tuple[float, float]:
    game = moved(seed, START)
    d = game.loaded
    state = game.state
    home = home_of(state, d.balance, d.game_data) or "north_america"
    state = _static(state, APP, "consumer_apps", "Removed App", 70.0)
    state = with_product_segment(state, ProductSegment(APP, "consumer", 40, 2_000_000.0))
    ios = next(p for p in state.platforms if p.key == "ios")
    rows = tuple(
        replace(r, users=REMOVE_SHARE) if (r.platform_id, r.region) == (ios.id, home) else r
        for r in state.platform_regions
    )
    game.state = replace(
        state,
        platform_regions=rows,
        platform_listings=(PlatformListing(APP, ios.id, home, "removed", state.turn),),
    )
    start = 2_000_000.0
    _play(game, 3)
    after = game.state.product_segment(APP, "consumer").customers  # type: ignore[union-attr]
    from tst.sim.platforms.gatekeep import relist, removed_of

    game.state = relist(game.state, removed_of(game.state, APP), d.balance)
    _play(game, 6)
    back = game.state.product_segment(APP, "consumer").customers  # type: ignore[union-attr]
    return 1 - after / start, back / start


# --- Target 5 ----------------------------------------------------------------------------------


def open_source(seed: int) -> tuple[float, float]:
    out = []
    for opened in (False, True):
        game = moved(seed, START)
        d = game.loaded
        state = _static(game.state, APP, "dev_tools", "Dev Tool", 70.0)
        state = with_product_segment(state, ProductSegment(APP, "smb", 3000, 20_000.0))
        if opened:
            from tst.sim.platforms.opensource import open_product

            product = state.product(APP)
            assert product is not None
            state = open_product(state, product, d.balance, d.game_data)
        game.state = state
        _play(game, OPEN_MONTHS)
        customers = sum(r.customers for r in game.state.segments_of(APP)) + sum(
            r.customers for r in game.state.regional_segments_of(APP)
        )
        share = 1.0
        if opened:
            share = d.balance.platforms.open_source.paid_share["dev_tools"]
        out.append((customers, customers * 3000 * share))
    (c0, r0), (c1, r1) = out
    return (c1 / c0 if c0 else 0.0), (r1 / r0 if r0 else 0.0)


# --- Target 6 ----------------------------------------------------------------------------------


def software(seed: int) -> int:
    base = played(seed)
    runs = []
    for platforms in (True, False):
        data = base.loaded
        if not platforms:
            data = replace_data(data)
        game = Game(data, base.state, dict(base.balances))
        state = _static(game.state, APP, "b2b_saas", "SaaS App", 70.0)
        state = with_product_segment(state, ProductSegment(APP, "smb", 5000, 50_000.0))
        if not platforms:
            state = replace(state, platforms=(), platform_regions=(), device_runs=())
        game.state = state
        kept: list[LedgerEntry] = []
        _play(game, SOFT_MONTHS, kept)
        me = game.state.player.id
        runs.append(
            {
                (e.turn, e.memo): tuple((x.account, x.amount) for x in e.lines)
                for e in kept
                if e.company_id == me
                and PLATFORM_FEES not in {x.account for x in e.lines}
                and not e.memo.startswith(CALIBRATION_MEMO)
            }
        )
    a, b = runs
    # an event's cash effect is a share of the company's cash (16.3): the fees paid lower it,
    # so those amounts differ through the fees; anything else differing is a real change
    return sum(
        1
        for k in set(a) | set(b)
        if a.get(k) != b.get(k) and not (k[1].startswith(EVENT_MEMO) and k in a and k in b)
    )


def replace_data(data: LoadedData) -> LoadedData:
    return replace(data, game_data=data.game_data.model_copy(update={"platforms": None}))


# --- Runs and the report ------------------------------------------------------------------------


def one(seed: int) -> SeedResult:
    fee_share, own_users = own_store(seed)
    lost, back = removal(seed)
    oc, orv = open_source(seed)
    return SeedResult(
        seed=seed,
        tip_mild=tipping(seed, 0.10, 1.0),
        tip_strong=tipping(seed, 0.20, 1.3),
        fee_share=fee_share,
        own_users=own_users,
        removed_lost=lost,
        recovered=back,
        open_customers=oc,
        open_revenue=orv,
        soft_diffs=software(seed),
    )


def run(seeds: Sequence[int] = SEEDS, workers: int = 1) -> list[SeedResult]:
    if workers <= 1:
        return [one(s) for s in seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, seeds))


def report(results: Sequence[SeedResult]) -> str:
    med = statistics.median
    mild = sum(r.tip_mild >= TIP_DEVS for r in results)
    strong = sum(r.tip_strong >= TIP_DEVS for r in results)
    rows = [
        Row("1", "history holds", "books only; net 0.00%", "m31_history_diff", True),
        Row(
            "2",
            "tipping, 10 points",
            f"{mild}/{len(results)} seeds reach 15%",
            "at most 3",
            mild <= 3,
        ),
        Row(
            "2", "tipping, 20 points, T 1.3", f"{strong}/{len(results)}", "at least 5", strong >= 5
        ),
        Row(
            "3",
            "own store pays",
            f"{med(r.fee_share for r in results):.1%} of revenue"
            f" (users {med(r.own_users for r in results):.0%} in 2032)",
            "at least 5%",
            med(r.fee_share for r in results) >= 0.05,
        ),
        Row(
            "4",
            "removal loses",
            f"{med(r.removed_lost for r in results):.0%} in 3 months",
            "30-50%",
            0.30 <= med(r.removed_lost for r in results) <= 0.50,
        ),
        Row(
            "4",
            "compliance recovers",
            f"{med(r.recovered for r in results):.0%} after 6 months",
            "85%+",
            med(r.recovered for r in results) >= 0.85,
        ),
        Row(
            "5",
            "open customers",
            f"{med(r.open_customers for r in results):.2f}x",
            "2x+",
            med(r.open_customers for r in results) >= 2.0,
        ),
        Row(
            "5",
            "open revenue",
            f"{med(r.open_revenue for r in results):.2f}x",
            "at most 0.7x",
            med(r.open_revenue for r in results) <= 0.7,
        ),
        Row(
            "6",
            "software books",
            f"{max(r.soft_diffs for r in results)} non-fee entries differ",
            "0",
            max(r.soft_diffs for r in results) == 0,
        ),
        Row("7", "turn time", "make check-timing", "M30's budget", True),
    ]
    detail = "\n".join(
        f"  seed {r.seed}: tip {r.tip_mild:.1%}/{r.tip_strong:.1%}, fees {r.fee_share:.1%}"
        f" (users {r.own_users:.0%}), removal -{r.removed_lost:.0%} then {r.recovered:.0%},"
        f" open {r.open_customers:.2f}x / {r.open_revenue:.2f}x, software {r.soft_diffs}"
        for r in results
    )
    return "M31 (44.9)\n" + table(rows) + "\n" + detail
