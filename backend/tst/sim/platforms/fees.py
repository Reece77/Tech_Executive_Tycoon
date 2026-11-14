"""Platform fees (docs/formulas.md 44.4; ADR-0021 4), after the month's markets, from
`platforms.fees_from`.

A product in an app-distributed category (`platforms.app_categories`) pays, in each region and
on each device platform with users there that lists it, `fee x paid_share x revenue in the
region's app segments x the platform's share of users`. The seller posts 5150 (debit) against
cash; an owner with books posts the same amount to cash against 4150. When seller and owner
are both in the player's group the pair is 5900 / 4300, which consolidation removes (31.6). No
fee when seller and owner are the same company. Fees to owners outside the game (Google) leave
the game with the cash.

The player's device lines on Android pay `platforms.android_licence_cents` a unit sold (5150).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.geopolitics import world
from tst.sim.ledger import (
    CASH,
    INTERCOMPANY_PURCHASES,
    INTERCOMPANY_SALES,
    PLATFORM_FEE_REVENUE,
    PLATFORM_FEES,
    REVENUE_SUBSCRIPTIONS,
    LedgerEntry,
    LedgerLine,
)
from tst.sim.platforms import data as pdata
from tst.sim.platforms.models import PlatformListing
from tst.sim.platforms.phase import by_region, home_of, live_in
from tst.sim.products.models import SELLING, Product
from tst.sim.state import GameState


def app_category(category: str, balance: Balance | None) -> bool:
    return balance is not None and category in balance.platforms.app_categories


def listed(state: GameState, product_id: int, platform_id: int, region: str) -> bool:
    """A product reaches a platform's users unless removed (or still answering a removal)."""
    row = _listing(state, product_id, platform_id, region)
    return row is None or row.status == "listed"


def _listing(
    state: GameState, product_id: int, platform_id: int, region: str
) -> PlatformListing | None:
    return next(
        (
            x
            for x in state.platform_listings
            if x.product_id == product_id and x.platform_id == platform_id and x.region == region
        ),
        None,
    )


def app_revenue_cents(
    state: GameState, product: Product, region: str, home: str | None, balance: Balance
) -> int:
    """Monthly revenue in the region's store-distributed segments: customers x price."""
    segments = set(balance.platforms.app_categories[product.category].segments)
    rows = [
        (r.customers, r.price_cents)
        for r in state.regional_segments_of(product.id, region)
        if r.segment in segments
    ]
    if region == home:
        rows += [
            (s.customers, s.price_cents)
            for s in state.segments_of(product.id)
            if s.segment in segments
        ]
    return round(sum(n * (p or 0) for n, p in rows))


def seller_year_cents(state: GameState, company_id: int) -> int:
    return sum(state.company(company_id).mrr_history[-MONTHS_PER_YEAR:])


def fees_due(
    state: GameState, balance: Balance, data: GameData
) -> dict[tuple[int, int, int, str], int]:
    """(seller product id, platform id, owner id or -1, region) -> this month's fee in cents."""
    pb = balance.platforms
    home = home_of(state, balance, data)
    rows = by_region(state)
    steering = set(_steering(state))
    out: dict[tuple[int, int, int, str], int] = {}
    books = {c.id for c in state.ledger_companies()}
    for product in state.products:
        if product.status not in SELLING or product.company_id not in books:
            continue
        if not app_category(product.category, balance):
            continue
        app = pb.app_categories[product.category]
        year = seller_year_cents(state, product.company_id)
        for region in data.region_keys:
            revenue = app_revenue_cents(state, product, region, home, balance)
            if revenue <= 0:
                continue
            for pid, row in rows.get(region, {}).items():
                p = state.platform(pid)
                if (
                    p is None
                    or p.kind != "device"
                    or row.users <= 0
                    or not live_in(p, region, state.turn)
                ):
                    continue
                if p.owner_id == product.company_id or not listed(state, product.id, pid, region):
                    continue
                sched = pdata.schedule(p, region, state.turn, balance, data, state.rival_stores)
                fee = pdata.fee_for(sched, product.category, year, product.id in steering, balance)
                cents = round(revenue * app.paid_share * row.users * fee)
                if cents > 0:
                    out[(product.id, pid, p.owner_id if p.owner_id is not None else -1, region)] = (
                        cents
                    )
    return out


def _steering(state: GameState) -> tuple[int, ...]:
    return state.steering_products


def fee_drag(category: str, balance: Balance, data: GameData) -> float:
    """The category's 2010-2025 average fee drag (44.4's calibration): paid_share x the users'
    effective fee (a large seller's, every platform with users, the regions weighted by their
    market sizes), averaged over the history's years. Data only: the same on every seed."""
    key = (id(data), category)
    if key in _DRAG:
        return _DRAG[key]
    pf = pdata.file(data)
    app = balance.platforms.app_categories[category]
    weights = pdata.region_weights(data)
    platforms = {p.key: p for p in pdata.historical_platforms_from_file(data)}
    first, last = pdata.FIRST_YEAR, pdata.year_of(pf.history_end_turn)
    years = []
    for year in range(first, last + 1):
        turn = (year - pdata.FIRST_YEAR) * MONTHS_PER_YEAR + MONTHS_PER_YEAR // 2
        drag = 0.0
        for region, w in weights.items():
            shares = pf.user_shares[region][year]
            for key_, users in shares.items():
                p = platforms.get(key_)
                if p is None or users <= 0 or region not in p.regions or p.launched_turn > turn:
                    continue
                if p.ended_turn is not None and turn >= p.ended_turn:
                    continue
                sched = pdata.schedule(p, region, turn, balance, data)
                fee = pdata.fee_for(sched, category, BIG_SELLER, False, balance)
                drag += w * users * fee
        years.append(app.paid_share * drag)
    _DRAG[key] = sum(years) / len(years)
    return _DRAG[key]


_DRAG: dict[tuple[int, str], float] = {}
BIG_SELLER: Final = 10**12  # tunable-exempt: a seller far over any small-business threshold


def store_revenue_cents(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> int:
    home = home_of(state, balance, data)
    return sum(app_revenue_cents(state, product, r, home, balance) for r in data.region_keys)


def fee_entries(state: GameState, balance: Balance, data: GameData) -> list[LedgerEntry]:
    """Fees from `fees_from` (44.4). To 2025 the calibration is exact: each seller's store
    revenue is grossed up by the month's fee and the fee booked against it (no cash moves), so
    net revenue and cash are main's to the cent. From 2026 the reference price carries the
    category's 2010-2025 average drag (gross store revenue x 1 / (1 - drag)) and the fee is
    paid in cash. Owners in the game earn 4150 throughout (5900 / 4300 inside the group)."""
    if not pdata.enabled(data) or not state.platforms or state.turn < balance.platforms.fees_turn:
        return []
    history = pdata.in_history(state.turn, data)
    due = fees_due(state, balance, data)
    group = {c.id for c in world.group(state)}
    books = {c.id for c in state.ledger_companies()}
    paid: dict[tuple[int, int, bool], int] = {}  # (seller product, owner, intercompany)
    earned: dict[tuple[int, bool], int] = {}
    for (product_id, _pid, owner, _region), cents in due.items():
        product = state.product(product_id)
        assert product is not None
        inter = owner >= 0 and owner in group and product.company_id in group
        paid[(product_id, owner, inter)] = paid.get((product_id, owner, inter), 0) + cents
        if owner >= 0 and owner in books:
            earned[(owner, inter)] = earned.get((owner, inter), 0) + cents
    entries: list[LedgerEntry] = []
    for (product_id, _owner, inter), cents in sorted(paid.items()):
        product = state.product(product_id)
        assert product is not None
        d = product.division_id
        label = "Platform fees (group store)" if inter else "Platform fees"
        against = REVENUE_SUBSCRIPTIONS if history else CASH  # the exact calibration, to 2025
        entries.append(
            LedgerEntry(
                turn=state.turn,
                company_id=product.company_id,
                memo=f"{label}: {product.name}",
                lines=(
                    LedgerLine(INTERCOMPANY_PURCHASES if inter else PLATFORM_FEES, cents, d),
                    LedgerLine(against, -cents, d),
                ),
            )
        )
    if not history:  # 44.4's calibration from 2026: the reference price carries the drag
        books_products = [
            p
            for p in state.products
            if p.status in SELLING and p.company_id in books and app_category(p.category, balance)
        ]
        for product in books_products:
            drag = fee_drag(product.category, balance, data)
            uplift = round(store_revenue_cents(state, product, balance, data) * drag / (1 - drag))
            if uplift > 0:
                entries.append(
                    LedgerEntry(
                        turn=state.turn,
                        company_id=product.company_id,
                        memo=f"Store price calibration: {product.name}",
                        lines=(
                            LedgerLine(CASH, uplift, product.division_id),
                            LedgerLine(REVENUE_SUBSCRIPTIONS, -uplift, product.division_id),
                        ),
                    )
                )
    for (owner, inter), cents in sorted(earned.items()):
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=owner,
                memo="Platform fees earned (group apps)" if inter else "Platform fees earned",
                debit=CASH,
                credit=INTERCOMPANY_SALES if inter else PLATFORM_FEE_REVENUE,
                amount=cents,
            )
        )
    return entries


def licence_entries(
    state: GameState, units: Mapping[int, float], balance: Balance, data: GameData
) -> list[LedgerEntry]:
    """The player's group's device units sold on Android this month pay its licence (44.1)."""
    pb = balance.platforms
    if not pdata.enabled(data) or state.turn < pb.start_turn or pb.android_licence_cents <= 0:
        return []
    group = {c.id for c in world.group(state)}
    android = {p.id for p in state.platforms if p.key in pdata.ANDROID_FAMILY}
    entries = []
    for run in state.device_runs:
        product = state.product(run.product_id)
        if product is None or product.company_id not in group or run.platform_id not in android:
            continue
        cents = round(units.get(product.id, 0.0) * pb.android_licence_cents)
        if cents > 0:
            entries.append(
                LedgerEntry(
                    turn=state.turn,
                    company_id=product.company_id,
                    memo=f"Android licence: {product.name}",
                    lines=(
                        LedgerLine(PLATFORM_FEES, cents, product.division_id),
                        LedgerLine(CASH, -cents, product.division_id),
                    ),
                )
            )
    return entries


def own_licence_entries(
    state: GameState, units: Mapping[int, float], balance: Balance, data: GameData
) -> list[LedgerEntry]:
    """Rival OEMs' device lines on the player's licensed OS pay its licence a unit (44.1)."""
    if not pdata.enabled(data) or state.turn < balance.platforms.start_turn:
        return []
    books = {c.id for c in state.ledger_companies()}
    entries = []
    for run in state.device_runs:
        p = state.platform(run.platform_id)
        product = state.product(run.product_id)
        if (
            p is None
            or product is None
            or p.historical
            or p.licence_cents is None
            or p.owner_id is None
        ):
            continue
        if product.company_id == p.owner_id or product.company_id not in books:
            continue
        cents = round(units.get(product.id, 0.0) * p.licence_cents)
        if cents <= 0:
            continue
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=product.company_id,
                memo=f"OS licence: {product.name}",
                debit=PLATFORM_FEES,
                credit=CASH,
                amount=cents,
            )
        )
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=p.owner_id,
                memo=f"OS licence earned: {product.name}",
                debit=CASH,
                credit=PLATFORM_FEE_REVENUE,
                amount=cents,
            )
        )
    return entries


def units_sold(
    flows: Mapping[tuple[int, str], object], regional: Mapping[tuple[int, str, str], float]
) -> dict[int, float]:
    """Units sold this month by product: the home segments' flows and every other region's."""
    out: dict[int, float] = {}
    for (pid, _seg), flow in flows.items():
        u = float(getattr(flow, "units", 0.0))
        if u:
            out[pid] = out.get(pid, 0.0) + u
    for (pid, _region, _seg), u in regional.items():
        out[pid] = out.get(pid, 0.0) + u
    return out


__all__ = ["fee_entries", "fees_due", "licence_entries"]
