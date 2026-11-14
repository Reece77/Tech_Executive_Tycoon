"""Rules and gatekeeping (docs/formulas.md 44.5; ADR-0021 5-6), from 2026, after the markets.

**Reviews.** Each month every device platform the player's group does not own reviews each of
the group's app-distributed products it lists in a region with users. The chance of an action
is `review.base[strictness]`, x `first_party` when the product's category is one the owner
sells its own apps in, x `own_store` when the group owns a device platform with users, x
`steering` when the product links users to pay outside. One uniform (stream `platforms` key
(1, platform id, product id)) decides whether it acts, a second which action by
`review.weights`: a rejected update (a month's features lost), a fee dispute (a month's fees on
that platform charged again) or a removal (the product leaves the platform's users in every
region it sells in; a critical event). Chances and draws are never stored or shown.

**A removal's answers** (`platform_step`): comply (relisted at once, the steering link dropped;
lost customers come back over `recovery_months`); appeal (an answer in 1-3 months; the chance,
drawn inside `appeal_odds` when it is decided, stays hidden); regulators (in a region with
platform rules: an answer in 6 months at `regulator_odds` x the rules' share of the region).
A lost appeal leaves it removed: comply from the Platforms screen.

**While removed** a product loses `removed_loss` x the platform's users of its customers there
each month; relisted, it wins `lost` back evenly over `recovery_months` (44.9 target 4).

**The player as gatekeeper.** Each December a platform of the group with standard or strict
review removes `player_removes` rivals' apps a year (the largest) in each category the group
sells apps in, for a year; strict review costs goodwill (phase).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import GameEvent, QueuedEvent
from tst.sim.geo.models import RegionalSegment
from tst.sim.geopolitics import world
from tst.sim.ledger import CASH, PLATFORM_FEE_REVENUE, PLATFORM_FEES, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.platforms import data as pdata
from tst.sim.platforms import draws
from tst.sim.platforms.fees import app_category, app_revenue_cents, fees_due
from tst.sim.platforms.models import ListingStatus, Platform, PlatformListing, Review
from tst.sim.platforms.phase import by_region, first_party, home_of, live_in
from tst.sim.products.models import SELLING, Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_product,
    with_product_segment,
    with_queued,
    with_regional_segment,
)

REMOVAL: Final = "platform_removal"  # the critical event's template id
ACTIONS: Final = ("rejected_update", "fee_dispute", "removal")
REGULATOR_MONTHS: Final = 6  # tunable-exempt: 44.5 names no length; a regulator's inquiry
KEEP_REVIEWS: Final = MONTHS_PER_YEAR  # tunable-exempt: months of reviews kept for the API
RIVAL_REMOVAL_MONTHS: Final = MONTHS_PER_YEAR  # tunable-exempt: a rival app off the player's store
PLATFORM_LINK: Final = "platforms"
NONE_LEFT: Final = 1e-6  # tunable-exempt: customers below this are all won back


def _owned_by_group(state: GameState) -> set[int]:
    group = {c.id for c in world.group(state)}
    return {p.id for p in state.platforms if p.owner_id in group}


def listing_of(
    state: GameState, product_id: int, platform_id: int, region: str
) -> PlatformListing | None:
    return next(
        (
            x
            for x in state.platform_listings
            if (x.product_id, x.platform_id, x.region) == (product_id, platform_id, region)
        ),
        None,
    )


def _set_listing(
    state: GameState, row: PlatformListing | None, key: tuple[int, int, str]
) -> GameState:
    others = tuple(
        x for x in state.platform_listings if (x.product_id, x.platform_id, x.region) != key
    )
    return replace(state, platform_listings=(*others, row) if row is not None else others)


def selling_regions(
    state: GameState, product: Product, platform: Platform, balance: Balance, data: GameData
) -> list[str]:
    home = home_of(state, balance, data)
    rows = by_region(state)
    out = []
    for region in data.region_keys:
        row = rows.get(region, {}).get(platform.id)
        if row is None or row.users <= 0 or not live_in(platform, region, state.turn):
            continue
        if app_revenue_cents(state, product, region, home, balance) > 0:
            out.append(region)
    return out


def chance(
    state: GameState, platform: Platform, product: Product, balance: Balance, data: GameData
) -> float:
    """The month's chance of an action (module docstring). Engine-side only."""
    rb = balance.platforms.review
    c = rb.base[platform.strictness]
    if product.category in first_party(platform, state, data, balance):
        c *= rb.first_party
    rows = by_region(state)
    if any(
        rows.get(r, {}).get(pid) and rows[r][pid].users > 0
        for pid in _owned_by_group(state)
        for r in data.region_keys
    ):
        c *= rb.own_store
    if product.id in state.steering_products:
        c *= rb.steering
    return min(1.0, c)


def reviews_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    if not pdata.enabled(data) or pdata.in_history(state.turn, data) or not state.platforms:
        return state, [], []
    rb = balance.platforms.review
    group = {c.id for c in world.group(state)}
    owned = _owned_by_group(state)
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    reviews = [r for r in state.platform_reviews if r.turn > state.turn - KEEP_REVIEWS]
    for product in [p for p in state.products if p.company_id in group and p.status in SELLING]:
        if not app_category(product.category, balance):
            continue
        for platform in state.platforms:
            if platform.id in owned or platform.kind != "device":
                continue
            regions = [
                r
                for r in selling_regions(state, product, platform, balance, data)
                if listing_of(state, product.id, platform.id, r) is None
            ]
            if not regions:
                continue
            gen = draws.gen(rng, state.turn, draws.REVIEW, platform.id, product.id)
            if float(gen.random()) >= chance(state, platform, product, balance, data):
                continue
            pick = float(gen.random()) * sum(rb.weights[a] for a in ACTIONS)
            action = ACTIONS[-1]
            for a in ACTIONS:
                pick -= rb.weights[a]
                if pick < 0:
                    action = a
                    break
            reviews.append(Review(state.turn, product.id, platform.id, action))  # type: ignore[arg-type]
            state, more_entries, more_logs = _act(
                state, product, platform, regions, action, balance, data
            )
            entries += more_entries
            logs += more_logs
    return replace(state, platform_reviews=tuple(reviews)), entries, logs


def _act(
    state: GameState,
    product: Product,
    platform: Platform,
    regions: list[str],
    action: str,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    names = {"product": product.name, "platform": platform.store, "owner": platform.owner_label}
    if action == "rejected_update":
        lost = data.category(product.category).features_per_month
        state = with_product(
            state, replace(product, feature_points=max(0.0, product.feature_points - lost))
        )
        return (
            state,
            [],
            [
                inbox_item(
                    state.turn,
                    product.company_id,
                    "platform_rejected",
                    link_kind="product",
                    link_id=product.id,
                    **names,
                )
            ],
        )
    if action == "fee_dispute":
        due = sum(
            c
            for (pid, plat, _o, _r), c in fees_due(state, balance, data).items()
            if pid == product.id and plat == platform.id
        )
        entries = []
        if due > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=product.company_id,
                    memo=f"Platform fee dispute: {product.name}",
                    debit=PLATFORM_FEES,
                    credit=CASH,
                    amount=due,
                )
            )
            if platform.owner_id is not None and platform.owner_id in {
                c.id for c in state.ledger_companies()
            }:
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn,
                        company_id=platform.owner_id,
                        memo=f"Platform fee dispute: {product.name}",
                        debit=CASH,
                        credit=PLATFORM_FEE_REVENUE,
                        amount=due,
                    )
                )
        return (
            state,
            entries,
            [
                inbox_item(
                    state.turn,
                    product.company_id,
                    "platform_fee_dispute",
                    link_kind="product",
                    link_id=product.id,
                    cents=due,
                    **names,
                )
            ],
        )
    for region in regions:
        state = _set_listing(
            state,
            PlatformListing(product.id, platform.id, region, "removed", state.turn),
            (product.id, platform.id, region),
        )
    qid, ids = state.next_ids.take("queued")
    state = with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=product.company_id,
            template_id=REMOVAL,
            due_turn=state.turn + 1,
            source_event_id=None,
            product_id=product.id,
        ),
    )
    return state, [], []


# --- Answers ---------------------------------------------------------------------------------


def removed_of(state: GameState, product_id: int) -> list[PlatformListing]:
    return [
        x for x in state.platform_listings if x.product_id == product_id and x.status == "removed"
    ]


def removal_names(state: GameState, data: GameData, event: GameEvent) -> dict[str, str]:
    rows = removed_of(state, event.product_id or -1) or [
        x for x in state.platform_listings if x.product_id == event.product_id
    ]
    if not rows:
        return {"platform": "the store", "owner": "the platform's owner", "regions": "its regions"}
    p = state.platform(rows[0].platform_id)
    labels = {r.key: r.label for r in data.regions}
    regions = sorted(
        {labels.get(x.region, x.region) for x in rows if x.platform_id == rows[0].platform_id}
    )
    return {
        "platform": p.store if p else "the store",
        "owner": p.owner_label if p else "the platform's owner",
        "regions": ", ".join(regions),
    }


def relist(state: GameState, rows: list[PlatformListing], balance: Balance) -> GameState:
    months = balance.platforms.review.recovery_months
    for x in rows:
        state = _set_listing(
            state,
            replace(
                x,
                status="listed",
                since_turn=state.turn,
                until_turn=None,
                winback_until=state.turn + months,
            ),
            (x.product_id, x.platform_id, x.region),
        )
    return state


def platform_step(
    state: GameState,
    event: GameEvent,
    step: str,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """A removal's answer (module docstring), applied by the engine."""
    rb = balance.platforms.review
    rows = removed_of(state, event.product_id or -1)
    if not rows:
        return state, [], []
    if step == "comply":
        state = relist(state, rows, balance)
        steering = tuple(p for p in state.steering_products if p != event.product_id)
        return replace(state, steering_products=steering), [], []
    if step == "appeal" or (step == "regulators" and not _ruled(state, rows, data)):
        lo, hi = rb.appeal_months
        gen = draws.gen(
            rng, state.turn, draws.REVIEW, rows[0].platform_id, rows[0].product_id, draws.LENGTH
        )
        until = state.turn + lo + int(gen.integers(hi - lo + 1))
        status: ListingStatus = "appealing"
    else:
        until = state.turn + REGULATOR_MONTHS
        status = "regulators"
    for x in rows:
        state = _set_listing(
            state,
            replace(x, status=status, until_turn=until, event_id=event.id),
            (x.product_id, x.platform_id, x.region),
        )
    return state, [], []


def _ruled(state: GameState, rows: list[PlatformListing], data: GameData) -> float:
    """The share of the rows' regions under platform rules (alternative payments, side-loading)."""
    best = 0.0
    for x in rows:
        p = state.platform(x.platform_id)
        if p is None:
            continue
        for kind in ("alt_payments", "anti_steering_banned", "side_loading"):
            best = max(best, pdata.rule_active(data, p, x.region, kind, state.turn))
    return best


def answers_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Appeals and regulators decide on their month (module docstring)."""
    rb = balance.platforms.review
    logs: list[LogItem] = []
    due: dict[tuple[int, int], list[PlatformListing]] = {}
    for x in state.platform_listings:
        if (
            x.status in ("appealing", "regulators")
            and x.until_turn is not None
            and x.until_turn <= state.turn
        ):
            due.setdefault((x.product_id, x.platform_id), []).append(x)
    for (product_id, platform_id), rows in sorted(due.items()):
        gen = draws.gen(rng, state.turn, draws.REVIEW, platform_id, product_id, draws.ANSWER)
        if rows[0].status == "appealing":
            lo, hi = rb.appeal_odds
            odds = lo + (hi - lo) * float(gen.random())
        else:
            odds = rb.regulator_odds * _ruled(state, rows, data)
        won = float(gen.random()) < odds
        product = state.product(product_id)
        p = state.platform(platform_id)
        if won:
            state = relist(state, rows, balance)
        else:
            for x in rows:
                state = _set_listing(
                    state,
                    replace(x, status="removed", until_turn=None),
                    (x.product_id, x.platform_id, x.region),
                )
        if product is not None and p is not None:
            kind = "platform_appeal_won" if won else "platform_appeal_lost"
            logs.append(
                inbox_item(
                    state.turn,
                    product.company_id,
                    kind,
                    link_kind="product",
                    link_id=product.id,
                    product=product.name,
                    platform=p.store,
                )
            )
    return state, logs


# --- While removed, and winning customers back ----------------------------------------------------


def listing_effects(state: GameState, balance: Balance, data: GameData) -> GameState:
    if not state.platform_listings:
        return state
    rb = balance.platforms.review
    home = home_of(state, balance, data)
    rows = by_region(state)
    keep = []
    for x in state.platform_listings:
        product = state.product(x.product_id)
        if product is None or product.status not in SELLING:
            continue
        users = rows.get(x.region, {}).get(x.platform_id)
        share = users.users if users is not None else 0.0
        if x.status != "listed":
            factor = 1 - rb.removed_loss * share
            state, lost = _scale(state, product, x.region, home, factor, balance)
            if x.status == "removed" and x.until_turn is not None and x.until_turn <= state.turn:
                keep.append(
                    replace(
                        x,
                        status="listed",
                        until_turn=None,
                        lost=x.lost + lost,
                        winback_until=state.turn + rb.recovery_months,
                    )
                )
            else:
                keep.append(replace(x, lost=x.lost + lost))
            continue
        if x.winback_until is not None and x.lost > 0:
            months_left = max(1, x.winback_until - state.turn + 1)
            back = x.lost / months_left
            state, got = _add(state, product, x.region, home, back, balance)
            if x.winback_until > state.turn and x.lost - got > NONE_LEFT:
                keep.append(replace(x, lost=x.lost - got))
    return replace(
        state,
        platform_listings=tuple(
            sorted(keep, key=lambda x: (x.product_id, x.platform_id, x.region))
        ),
    )


def _rows(
    state: GameState, product: Product, region: str, home: str | None, balance: Balance
) -> list[ProductSegment | RegionalSegment]:
    app = balance.platforms.app_categories.get(product.category)
    segments = set(app.segments) if app is not None else set()
    out: list[ProductSegment | RegionalSegment] = [
        r for r in state.regional_segments_of(product.id, region) if r.segment in segments
    ]
    if region == home:
        out += [s for s in state.segments_of(product.id) if s.segment in segments]
    return out


def _put(state: GameState, row: ProductSegment | RegionalSegment) -> GameState:
    if isinstance(row, ProductSegment):
        return with_product_segment(state, row)
    return with_regional_segment(state, row)


def _scale(
    state: GameState,
    product: Product,
    region: str,
    home: str | None,
    factor: float,
    balance: Balance,
) -> tuple[GameState, float]:
    lost = 0.0
    for row in _rows(state, product, region, home, balance):
        lost += row.customers * (1 - factor)
        state = _put(state, replace(row, customers=row.customers * factor))
    return state, lost


def _add(
    state: GameState,
    product: Product,
    region: str,
    home: str | None,
    amount: float,
    balance: Balance,
) -> tuple[GameState, float]:
    rows = _rows(state, product, region, home, balance)
    total = sum(r.customers for r in rows)
    got = 0.0
    for row in rows:
        share = row.customers / total if total > 0 else 1 / len(rows)
        state = _put(state, replace(row, customers=row.customers + amount * share))
        got += amount * share
    return state, got


# --- The player as gatekeeper ------------------------------------------------------------------


def player_reviews(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    if pdata.in_history(state.turn, data) or state.turn % MONTHS_PER_YEAR != MONTHS_PER_YEAR - 1:
        return state, []
    rb = balance.platforms.review
    group = {c.id for c in world.group(state)}
    logs: list[LogItem] = []
    for p in state.platforms:
        if p.owner_id not in group or p.kind != "device" or rb.player_removes[p.strictness] <= 0:
            continue
        cats = {
            q.category
            for q in state.products
            if q.company_id in group and q.status in SELLING and app_category(q.category, balance)
        }
        for cat in sorted(cats):
            rivals = [
                q
                for q in state.products
                if q.category == cat and q.company_id not in group and q.status in SELLING
            ]
            rivals.sort(key=lambda q: (-sum(s.customers for s in state.segments_of(q.id)), q.id))
            for q in rivals[: rb.player_removes[p.strictness]]:
                for region in p.regions:
                    if listing_of(state, q.id, p.id, region) is None:
                        state = _set_listing(
                            state,
                            PlatformListing(
                                q.id,
                                p.id,
                                region,
                                "removed",
                                state.turn,
                                until_turn=state.turn + RIVAL_REMOVAL_MONTHS,
                            ),
                            (q.id, p.id, region),
                        )
                logs.append(
                    inbox_item(
                        state.turn,
                        state.player.id,
                        "platform_removed_rival",
                        link_kind=PLATFORM_LINK,
                        link_id=p.id,
                        product=q.name,
                        platform=p.store,
                    )
                )
    return state, logs
