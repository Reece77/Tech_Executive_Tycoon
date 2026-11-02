"""Rival decisions (docs/formulas.md 15.2-15.3): one action a month in phase 2, the effects
that run for a few months, segment-share memory, and the month's market news.

Randomness: stream `rivals`, key `(company_id,)`; one normal draw per candidate action in the
order they are listed (products by id, segments in categories.yaml order, actions in
RIVAL_ACTIONS order). Every decision is a `RivalMove`; the repository logs it to decision_log
with source "rival" and replay recomputes it (ADR-0015 section 5).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

import numpy as np

from tst.sim.data_models import RIVAL_ACTIONS, SCORE_MAX, Balance, GameData
from tst.sim.geo import formulas as gf
from tst.sim.geo.cities import home_region
from tst.sim.geo.models import ProductRegion, RegionalSegment
from tst.sim.ledger import CASH, LedgerBalances, LedgerEntry, account_balance
from tst.sim.log import LogItem, inbox_item
from tst.sim.people.models import current_ability
from tst.sim.products import formulas as pf
from tst.sim.products.models import SELLING, Product, ProductSegment
from tst.sim.rivals import formulas as f
from tst.sim.rivals.models import PoachApproach, RivalEffect, RivalMove, SegmentShare, stream_key
from tst.sim.rivals.poaching import TARGET_KEY, poach_draw
from tst.sim.rivals.startups import startup_funding
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    with_approach,
    with_pool,
    with_product,
    with_product_region,
    with_product_segment,
    with_regional_segment,
    with_rival_effect,
    with_rival_move,
    with_segment_share,
)

PUSHES = ("feature_push", "quality_push", "brand_push")
PERCENT = 100  # tunable-exempt: percent in news words


@dataclass(frozen=True, slots=True)
class Candidate:
    action: str
    need: float
    product_id: int | None = None
    segment: str | None = None  # for enter_region (M9): the region's key


ENTER_REGION = "enter_region"  # M9 (19.6): weighted as enter_segment


def selling_regions(state: GameState, product: Product, home: str) -> set[str]:
    """Regions a product sells or is launching in: home if it has home segments."""
    regions = {r.region for r in state.regions_of(product.id)}
    if state.segments_of(product.id):
        regions.add(home)
    return regions


def region_unserved(
    state: GameState, category: str, segments: Iterable[str], region: str, home: str
) -> float:
    """Unserved share of a region's demand in the given segments of a category (19.6)."""
    demand = served = 0.0
    for seg in segments:
        if region == home:
            market = state.market(category, seg)
            demand += market.addressable if market is not None else 0.0
            served += sum(s.customers for _, s in _rivals_in(state, category, seg))
        else:
            rmarket = state.regional_market(category, seg, region)
            demand += rmarket.addressable if rmarket is not None else 0.0
            served += sum(
                r.customers
                for r in state.regional_segments
                if r.region == region
                and r.segment == seg
                and (p := state.product(r.product_id)) is not None
                and p.category == category
                and p.status == "live"
            )
    return max(0.0, demand - served) / demand if demand > 0 else 0.0


def region_candidates(
    state: GameState, company: CompanyState, months: float, balance: Balance, data: GameData
) -> list[Candidate]:
    """enter_region for each live product and region it does not sell in yet, in regions.yaml
    order: need (unserved share - 0.4) / 0.4 with 12 months of costs in cash (19.6)."""
    if not data.region_markets or not data.cities:
        return []
    entry = balance.geo.region_entry
    home = home_region(state, balance, data)
    out: list[Candidate] = []
    for product in sorted(state.company_products(company.id), key=lambda p: p.id):
        if product.status != "live":
            continue
        selling = selling_regions(state, product, home)
        segments = product_segment_keys(state, product, data)
        for region in data.region_keys:
            if region in selling:
                continue
            need = 0.0
            if months >= entry.cash_months:
                unserved = region_unserved(state, product.category, segments, region, home)
                need = max(0.0, min(1.0, (unserved - entry.unserved) / entry.span))
            out.append(Candidate(ENTER_REGION, need, product.id, region))
    return out


def product_segment_keys(state: GameState, product: Product, data: GameData) -> list[str]:
    """Segments the product sells anywhere, in categories.yaml order."""
    keys = {s.segment for s in state.segments_of(product.id)}
    keys |= {r.segment for r in state.regional_segments_of(product.id)}
    return [k for k in data.category(product.category).segment_keys if k in keys]


# --- Memory: shares of served customers (phase 11) -------------------------------------------


def served_shares(state: GameState) -> dict[tuple[int, str], float]:
    """Each selling product's share of its segment's served customers now."""
    totals: dict[tuple[str, str], float] = {}
    rows: list[tuple[Product, ProductSegment]] = []
    for product in state.products:
        if product.status not in SELLING:
            continue
        for seg in state.segments_of(product.id):
            totals[(product.category, seg.segment)] = (
                totals.get((product.category, seg.segment), 0.0) + seg.customers
            )
            rows.append((product, seg))
    out = {}
    for product, seg in rows:
        total = totals[(product.category, seg.segment)]
        out[(product.id, seg.segment)] = seg.customers / total if total > 0 else 0.0
    return out


def remember_shares(state: GameState, balance: Balance) -> GameState:
    """Append this month's share to each product-segment's history (window + 1 kept)."""
    keep = balance.rivals.window_turns + 1
    known = {(s.product_id, s.segment): s for s in state.segment_shares}
    for key, share in served_shares(state).items():
        old = known.get(key)
        history = (*(old.history if old else ()), share)[-keep:]
        state = with_segment_share(state, SegmentShare(key[0], key[1], history))
    return state


def share_change(state: GameState, product_id: int, segment: str, window: int) -> float | None:
    """Share now minus share `window` months ago; None without that much history."""
    for s in state.segment_shares:
        if s.product_id == product_id and s.segment == segment:
            if len(s.history) <= window:
                return None
            return s.history[-1] - s.history[-1 - window]
    return None


# --- Costs and cash ---------------------------------------------------------------------------


def monthly_cost_cents(state: GameState, company_id: int, balance: Balance, data: GameData) -> int:
    from tst.sim.hiring.phases import monthly_costs  # phases import this module's callers

    return sum(amount for _, _, amount in monthly_costs(state, company_id, balance, data))


def cash_months(
    state: GameState, company_id: int, balances: LedgerBalances, balance: Balance, data: GameData
) -> float:
    cost = monthly_cost_cents(state, company_id, balance, data)
    cash = account_balance(balances, company_id, CASH)
    return float("inf") if cost <= 0 else cash / cost


# --- Candidate actions ------------------------------------------------------------------------


def _feature(product: Product, data: GameData, turn: int) -> float:
    if product.held_feature is not None:
        return product.held_feature
    return pf.feature_score(product.feature_points, data.category(product.category), turn)


def _appeal(product: Product, seg: ProductSegment, data: GameData, turn: int) -> float:
    if seg.price_cents is None:
        return 0.0
    reference = data.category(product.category).market(seg.segment).reference_price_cents
    return pf.appeal(
        data.segment(seg.segment).weights,
        product.quality,
        pf.price_score(reference, seg.price_cents),
        product.brand,
        _feature(product, data, turn),
    )


def _rivals_in(
    state: GameState, category: str, segment: str
) -> list[tuple[Product, ProductSegment]]:
    out = []
    for product in state.products:
        if product.category != category or product.status != "live":
            continue
        for seg in state.segments_of(product.id):
            if seg.segment == segment and seg.price_cents is not None:
                out.append((product, seg))
    return out


def player_target(
    state: GameState, balance: Balance, data: GameData, u: float | None = None
) -> int | None:
    """A player's employee in the top 30% by true CA, not the founder and not already
    approached (15.6). With a draw `u` in [0, 1) the target is drawn among them weighted by
    CA, a seat holder's weight x `seat_holder_weight` (M10d, product manager 2026-11-02);
    without one, the first eligible by CA (ties by id), which says whether anyone is free."""
    player = state.player.id
    pending = {a.person_id for a in state.approaches if a.status == "pending"}
    staff = [
        e
        for e in state.staff(player)
        if e.status == "active" and not state.person(e.person_id).is_founder
    ]
    if not staff:
        return None
    ranked = sorted(
        staff,
        key=lambda e: (-current_ability(state.person(e.person_id), data), e.person_id),
    )
    top = max(1, int(len(ranked) * balance.rivals.poach.top_fraction))
    free = [e for e in ranked[:top] if e.person_id not in pending]
    if not free:
        return None
    if u is None:
        return free[0].person_id
    seated = {s.person_id for s in state.exec_seats if s.company_id == player and s.person_id}
    weight = balance.rivals.poach.seat_holder_weight
    weights = [
        current_ability(state.person(e.person_id), data) * (weight if e.person_id in seated else 1)
        for e in free
    ]
    total = sum(weights)
    if total <= 0:
        return free[0].person_id
    point, run = u * total, 0.0
    for e, w in zip(free, weights, strict=True):
        run += w
        if point < run:
            return e.person_id
    return free[-1].person_id


def candidates(
    state: GameState,
    company: CompanyState,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> list[Candidate]:
    rv = balance.rivals
    need = rv.need
    turn = state.turn
    out: list[Candidate] = []
    months = cash_months(state, company.id, balances, balance, data)
    player = state.player.id
    player_products = [p for p in state.company_products(player) if p.status == "live"]
    for product in sorted(state.company_products(company.id), key=lambda p: p.id):
        if product.status != "live":
            continue
        category = data.category(product.category)
        own = {s.segment: s for s in state.segments_of(product.id)}
        if not own and state.regions_of(product.id):
            continue  # sells only abroad: it comes home through enter_region (M9, 19.6)
        for seg_key in category.segment_keys:
            seg = own.get(seg_key)
            if seg is None or seg.price_cents is None:
                market = state.market(product.category, seg_key)
                served = sum(s.customers for _, s in _rivals_in(state, product.category, seg_key))
                unserved = 0.0
                if market is not None and market.addressable > 0:
                    unserved = max(0.0, market.addressable - served) / market.addressable
                out.append(
                    Candidate(
                        "enter_segment", f.need_enter(unserved, months, need), product.id, seg_key
                    )
                )
                continue
            change = share_change(state, product.id, seg_key, rv.window_turns) or 0.0
            others = [
                (p, s)
                for p, s in _rivals_in(state, product.category, seg_key)
                if p.id != product.id
            ]
            mine = _appeal(product, seg, data, turn)
            next_best = max((_appeal(p, s, data, turn) for p, s in others), default=0.0)
            best_feature = max((_feature(p, data, turn) for p, _ in others), default=0.0)
            best_quality = max((p.quality for p, _ in others), default=0.0)
            best_brand = max((p.brand for p, _ in others), default=0.0)
            out += [
                Candidate("price_cut", f.need_price_cut(-change, need), product.id, seg_key),
                Candidate(
                    "price_rise",
                    f.need_price_rise(mine - next_best, change < 0, need),
                    product.id,
                    seg_key,
                ),
                Candidate(
                    "feature_push",
                    f.need_gap(best_feature, _feature(product, data, turn), need.feature_gap),
                    product.id,
                    seg_key,
                ),
                Candidate(
                    "quality_push",
                    f.need_gap(best_quality, product.quality, need.quality_gap),
                    product.id,
                    seg_key,
                ),
                Candidate(
                    "brand_push",
                    f.need_gap(best_brand, product.brand, need.brand_gap),
                    product.id,
                    seg_key,
                ),
            ]
            gain = max(
                (
                    share_change(state, p.id, seg_key, rv.window_turns) or 0.0
                    for p in player_products
                    if p.category == product.category
                    and any(s.segment == seg_key for s in state.segments_of(p.id))
                ),
                default=0.0,
            )
            has_target = gain > 0 and player_target(state, balance, data) is not None
            out.append(
                Candidate("poach", f.need_poach(gain, has_target, need), product.id, seg_key)
            )
    out.append(Candidate("cut_costs", f.need_cut_costs(months, need)))
    order = {a: i for i, a in enumerate(RIVAL_ACTIONS)}
    ranked = sorted(out, key=lambda c: (c.product_id or 0, c.segment or "", order[c.action]))
    # Region entry (M9, 19.6) comes after v1's candidates, so their draws are unchanged.
    return ranked + region_candidates(state, company, months, balance, data)


def _cooling(state: GameState, company_id: int, c: Candidate, balance: Balance) -> bool:
    rv = balance.rivals
    since = state.turn - rv.cooldown_turns
    if c.action == ENTER_REGION:  # M9: one region entry per rival per its cooldown (19.6)
        after = state.turn - balance.geo.region_entry.cooldown_turns
        return any(
            m.company_id == company_id and m.action == ENTER_REGION and m.turn > after
            for m in state.rival_moves
        )
    for m in state.rival_moves:
        if (
            m.company_id == company_id
            and m.action == c.action
            and m.product_id == c.product_id
            and m.segment == c.segment
            and m.turn > since
        ):
            return True
    if c.action in PUSHES:
        return any(
            e.company_id == company_id and e.kind == c.action and e.product_id == c.product_id
            for e in state.rival_effects
            if e.end_turn >= state.turn
        )
    if c.action == "cut_costs":
        return any(
            e.company_id == company_id and e.kind == "cut_costs" and e.end_turn >= state.turn
            for e in state.rival_effects
        )
    return False


def choose(
    state: GameState,
    company: CompanyState,
    gen: np.random.Generator,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[Candidate, float] | None:
    """The best action by utility, if at least act_threshold (15.3)."""
    rv = balance.rivals
    weights = rv.weights[company.personality or "fast_follower"]
    best: tuple[Candidate, float] | None = None
    for c in candidates(state, company, balances, balance, data):
        noise = float(gen.normal(0.0, rv.noise_sd))
        if c.need <= 0 or _cooling(state, company.id, c, balance):
            continue
        u = f.utility(c.need, weights.get(c.action, weights["enter_segment"]), noise)
        if best is None or u > best[1]:
            best = (c, u)
    if best is None or best[1] < rv.act_threshold:
        return None
    return best


# --- Effects of an action (15.3) --------------------------------------------------------------


def _effect(
    state: GameState, company_id: int, kind: str, product_id: int | None, balance: Balance
) -> GameState:
    effect_id, ids = state.next_ids.take("rival_effect")
    effect = RivalEffect(
        id=effect_id,
        company_id=company_id,
        kind=kind,  # type: ignore[arg-type]
        start_turn=state.turn,
        end_turn=state.turn + balance.rivals.push_turns - 1,
        product_id=product_id,
    )
    return with_rival_effect(replace(state, next_ids=ids), effect)


def _grow_builders(state: GameState, company_id: int, fraction: float) -> GameState:
    for pool in state.company_pools(company_id):
        if pool.function == "builder":
            state = with_pool(state, replace(pool, headcount=pool.headcount * (1 + fraction)))
    return state


def segment_label(data: GameData, segment: str | None) -> str:
    return data.segment(segment).label if segment else ""


def act(
    state: GameState,
    company: CompanyState,
    c: Candidate,
    balance: Balance,
    data: GameData,
    rng: RngFactory | None = None,
) -> tuple[GameState, str]:
    """Apply the chosen action; returns the news words."""
    rv = balance.rivals
    product = state.product(c.product_id) if c.product_id is not None else None
    seg_label = segment_label(data, c.segment) if c.action != ENTER_REGION else ""
    if c.action in ("price_cut", "price_rise") and product is not None:
        seg = next(s for s in state.segments_of(product.id) if s.segment == c.segment)
        factor = rv.price_cut if c.action == "price_cut" else rv.price_rise
        state = with_product_segment(
            state, replace(seg, price_cents=max(1, round((seg.price_cents or 0) * factor)))
        )
        pct = round(abs(1 - factor) * PERCENT)
        verb = "cut" if c.action == "price_cut" else "raised"
        return state, f"{verb} {seg_label} prices {pct}% on {product.name}"
    if c.action in ("feature_push", "quality_push") and product is not None:
        state = _effect(state, company.id, c.action, product.id, balance)
        state = _grow_builders(state, company.id, rv.push_pool_growth)
        what = "feature" if c.action == "feature_push" else "quality"
        return state, f"started a {what} push on {product.name}"
    if c.action == "brand_push" and product is not None:
        state = _effect(state, company.id, c.action, product.id, balance)
        budget = round(product.marketing_budget_cents * (1 + rv.brand_push_marketing))
        state = with_product(state, replace(product, marketing_budget_cents=budget))
        return state, f"started a brand push on {product.name}"
    if c.action == "enter_segment" and product is not None and c.segment is not None:
        market = data.category(product.category).market(c.segment)
        price = round(
            market.reference_price_cents * rv.price_factor[company.personality or "fast_follower"]
        )
        state = with_product_segment(
            state,
            ProductSegment(
                product_id=product.id, segment=c.segment, price_cents=price, added_turn=state.turn
            ),
        )
        return state, f"entered {seg_label} with {product.name}"
    if c.action == ENTER_REGION and product is not None and c.segment is not None:
        return enter_region(state, company, product, c.segment, balance, data)
    if c.action == "cut_costs":
        for pool in state.company_pools(company.id):
            state = with_pool(
                state, replace(pool, headcount=pool.headcount * (1 - rv.cut_costs_pools))
            )
        for p in state.company_products(company.id):
            budget = round(p.marketing_budget_cents * (1 - rv.cut_costs_marketing))
            state = with_product(state, replace(p, marketing_budget_cents=budget))
        state = _effect(state, company.id, "cut_costs", None, balance)
        return state, "cut costs"
    if c.action == "poach":
        u = None
        if rng is not None:  # keyed by the rival's identity (M10d; ADR-0013 amendment)
            u = poach_draw(rng, state.turn, *stream_key(company.id, company.rival_key), TARGET_KEY)
        target = player_target(state, balance, data, u)
        if target is None:
            return state, ""
        state = approach(state, company, target, balance, data)
        return state, "approached one of your people"
    return state, ""


def enter_region(
    state: GameState,
    company: CompanyState,
    product: Product,
    region: str,
    balance: Balance,
    data: GameData,
    *,
    news: bool = True,
) -> tuple[GameState, str]:
    """A rival starts selling a product in a region at once, in every segment it sells
    anywhere, at p_ref x price index x its personality's price factor (19.6). Rivals have
    no offices and do not localize (M9 brief)."""
    home = home_region(state, balance, data)
    factor = balance.rivals.price_factor[company.personality or "fast_follower"]
    category = data.category(product.category)
    for seg in product_segment_keys(state, product, data):
        reference = category.market(seg).reference_price_cents
        if region == home:
            price = max(1, round(reference * factor))
            if state.product_segment(product.id, seg) is None:
                state = with_product_segment(
                    state, ProductSegment(product.id, seg, price, added_turn=state.turn)
                )
            continue
        price = gf.regional_price_cents(reference, region, home, data, factor)  # M10r
        state = with_regional_segment(
            state, RegionalSegment(product.id, region, seg, price, added_turn=state.turn)
        )
    if region != home:
        state = with_product_region(
            state, ProductRegion(product.id, region, state.turn, state.turn)
        )
    return state, f"entered {data.region(region).label} with {product.name}" if news else ""


def approach(
    state: GameState, company: CompanyState, person_id: int, balance: Balance, data: GameData
) -> GameState:
    """A poach approach at offer_mult x the role and level's market rate (15.6)."""
    from tst.sim.hiring.formulas import market_mid_cents

    employment = state.employment_of(person_id)
    assert employment is not None
    from tst.sim.geo.cities import work_multiplier_bp

    market = market_mid_cents(
        data.role(employment.role).salary_band_mid_cents[employment.level],
        work_multiplier_bp(state, employment, balance, data),
    )
    offer = round(market * balance.rivals.poach.offer_mult)
    approach_id, ids = state.next_ids.take("approach")
    return with_approach(
        replace(state, next_ids=ids),
        PoachApproach(
            id=approach_id,
            rival_id=company.id,
            person_id=person_id,
            offer_cents=offer,
            made_turn=state.turn,
        ),
    )


def approach_note(state: GameState, made: PoachApproach) -> LogItem:
    """The player's inbox item for a rival's approach (15.6)."""
    person = state.person(made.person_id)
    employment = state.employment_of(person.id)
    return inbox_item(
        state.turn,
        state.player.id,
        "rival_approach",
        link_kind="person",
        link_id=person.id,
        rival=state.company(made.rival_id).name,
        name=f"{person.first_name} {person.last_name}",
        offer_cents=made.offer_cents,
        salary_cents=employment.salary_cents if employment else 0,
    )


# --- Phase 2 ----------------------------------------------------------------------------------


def rival_month(
    state: GameState,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[RivalMove, ...], tuple[LogItem, ...], tuple[LedgerEntry, ...]]:
    """Each rival still in business decides once, by company id (15.3); a startup short of
    cash tries to raise first, and cuts costs if that fails (15.4)."""
    moves: list[RivalMove] = []
    logs: list[LogItem] = []
    entries: list[LedgerEntry] = []
    for company in state.rivals():
        if company.personality is None:
            continue
        gen = rng.stream(state.turn, "rivals", *stream_key(company.id, company.rival_key))
        chosen = choose(state, company, gen, balances, balance, data)
        if company.is_startup:
            months = cash_months(state, company.id, balances, balance, data)
            cost = monthly_cost_cents(state, company.id, balance, data)
            state, raised, funded, failed = startup_funding(
                state, company, float(gen.random()), months, cost, balance, data
            )
            entries += raised
            if funded is not None:
                moves.append(funded)
            if failed:
                chosen = (Candidate("cut_costs", 1.0), 1.0)
            company = state.company(company.id)
        if chosen is None:
            continue
        c, _ = chosen
        state, words = act(state, company, c, balance, data, rng)
        if not words:
            continue
        move_id, ids = state.next_ids.take("rival_move")
        move = RivalMove(
            id=move_id,
            company_id=company.id,
            turn=state.turn,
            action=c.action,
            product_id=c.product_id,
            segment=c.segment,
            detail=f"{company.name} {words}",
        )
        state = with_rival_move(replace(state, next_ids=ids), move)
        moves.append(move)
        if c.action == "poach":
            logs.append(approach_note(state, max(state.approaches, key=lambda a: a.id)))
    return state, tuple(moves), tuple(logs), tuple(entries)


def apply_effects(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Phase 3: running pushes, cost-cut drag and departed builders change rival products
    (15.2); finished brand pushes return their extra marketing."""
    rv = balance.rivals
    turn = state.turn
    for e in state.rival_effects:
        if e.start_turn > turn:
            continue
        if e.end_turn < turn:
            continue
        targets = (
            [state.product(e.product_id)]
            if e.product_id is not None and state.product(e.product_id) is not None
            else [p for p in state.company_products(e.company_id)]
        )
        company = state.company(e.company_id)
        for product in targets:
            if product is None or product.status == "retired":
                continue
            if e.kind == "feature_push":
                product = _add_feature(product, rv.feature_push_rate, data, turn)
            elif e.kind == "quality_push":
                target = rv.qcap_per_skill * (company.builder_skill or 0.0)
                step = min(rv.quality_push_rate, max(0.0, target - product.quality))
                product = replace(product, quality=product.quality + step)
            elif e.kind == "brand_push":
                product = replace(product, brand=min(SCORE_MAX, product.brand + rv.brand_push_rate))
            elif e.kind == "cut_costs":
                product = _add_feature(product, -rv.cut_costs_drag, data, turn)
                product = replace(product, brand=max(0.0, product.brand - rv.cut_costs_drag))
            elif e.kind == "builder_left":
                hit = rv.poach.key_builder_quality_hit / rv.push_turns
                product = replace(product, quality=max(0.0, product.quality - hit))
            if e.kind == "brand_push" and e.end_turn == turn:
                product = replace(
                    product,
                    marketing_budget_cents=round(
                        product.marketing_budget_cents / (1 + rv.brand_push_marketing)
                    ),
                )
            state = with_product(state, product)
    return state


def _add_feature(product: Product, amount: float, data: GameData, turn: int) -> Product:
    """Feature score +amount: an incumbent's held score, or a developing product's F by the
    points that move its score that much this month (11.4)."""
    if product.held_feature is not None:
        held = max(0.0, min(SCORE_MAX, product.held_feature + amount))
        return replace(product, held_feature=held)
    points = amount / SCORE_MAX * pf.expected_features(data.category(product.category), turn)
    return replace(product, feature_points=max(0.0, product.feature_points + points))


def market_news(state: GameState, moves: tuple[RivalMove, ...]) -> tuple[LogItem, ...]:
    """One inbox item for the player listing the month's rival moves (15.5)."""
    if not moves:
        return ()
    lines = "; ".join(m.detail for m in moves)
    return (inbox_item(state.turn, state.player.id, "market_news", count=len(moves), lines=lines),)
