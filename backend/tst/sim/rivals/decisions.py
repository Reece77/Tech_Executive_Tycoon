"""Rival decisions (docs/formulas.md 15.2-15.3): one action a month in phase 2, the effects
that run for a few months, segment-share memory, and the month's market news.

Randomness: stream `rivals`, key `(company_id,)`; one normal draw per candidate action in the
order they are listed (products by id, segments in categories.yaml order, actions in
RIVAL_ACTIONS order). Every decision is a `RivalMove`; the repository logs it to decision_log
with source "rival" and replay recomputes it (ADR-0015 section 5).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tst.sim.data_models import RIVAL_ACTIONS, SCORE_MAX, Balance, GameData
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import LogItem, inbox_item
from tst.sim.people.models import current_ability
from tst.sim.products import formulas as pf
from tst.sim.products.models import SELLING, Product, ProductSegment
from tst.sim.rivals import formulas as f
from tst.sim.rivals.models import PoachApproach, RivalEffect, RivalMove, SegmentShare
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    with_approach,
    with_pool,
    with_product,
    with_product_segment,
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
    segment: str | None = None


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


def player_target(state: GameState, balance: Balance, data: GameData) -> int | None:
    """The player's employee with the highest true CA in the top 30% (ties by id), not the
    founder and not already approached (15.6)."""
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
    for e in ranked[:top]:
        if e.person_id not in pending:
            return e.person_id
    return None


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
    return sorted(out, key=lambda c: (c.product_id or 0, c.segment or "", order[c.action]))


def _cooling(state: GameState, company_id: int, c: Candidate, balance: Balance) -> bool:
    rv = balance.rivals
    since = state.turn - rv.cooldown_turns
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
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[Candidate, float] | None:
    """The best action by utility, if at least act_threshold (15.3)."""
    rv = balance.rivals
    weights = rv.weights[company.personality or "fast_follower"]
    gen = rng.stream(state.turn, "rivals", company.id)
    best: tuple[Candidate, float] | None = None
    for c in candidates(state, company, balances, balance, data):
        noise = float(gen.normal(0.0, rv.noise_sd))
        if c.need <= 0 or _cooling(state, company.id, c, balance):
            continue
        u = f.utility(c.need, weights[c.action], noise)
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
) -> tuple[GameState, str]:
    """Apply the chosen action; returns the news words."""
    rv = balance.rivals
    product = state.product(c.product_id) if c.product_id is not None else None
    seg_label = segment_label(data, c.segment)
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
        what = "features" if c.action == "feature_push" else "quality"
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
        target = player_target(state, balance, data)
        if target is None:
            return state, ""
        state = approach(state, company, target, balance, data)
        return state, "approached one of your people"
    return state, ""


def approach(
    state: GameState, company: CompanyState, person_id: int, balance: Balance, data: GameData
) -> GameState:
    """A poach approach at offer_mult x the role and level's market rate (15.6)."""
    from tst.sim.hiring.formulas import market_mid_cents

    employment = state.employment_of(person_id)
    assert employment is not None
    person = state.person(person_id)
    market = market_mid_cents(
        data.role(employment.role).salary_band_mid_cents[employment.level],
        data.region(person.region).salary_multiplier_bp,
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


# --- Phase 2 ----------------------------------------------------------------------------------


def rival_month(
    state: GameState,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[RivalMove, ...], tuple[LogItem, ...]]:
    """Each rival still in business decides once, by company id (15.3)."""
    moves: list[RivalMove] = []
    logs: list[LogItem] = []
    for company in state.rivals():
        if company.personality is None:
            continue
        chosen = choose(state, company, rng, balances, balance, data)
        if chosen is None:
            continue
        c, _ = chosen
        state, words = act(state, company, c, balance, data)
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
            pending = max(state.approaches, key=lambda a: a.id)
            person = state.person(pending.person_id)
            employment = state.employment_of(person.id)
            logs.append(
                inbox_item(
                    state.turn,
                    state.player.id,
                    "rival_approach",
                    link_kind="person",
                    link_id=person.id,
                    rival=company.name,
                    name=f"{person.first_name} {person.last_name}",
                    offer_cents=pending.offer_cents,
                    salary_cents=employment.salary_cents if employment else 0,
                )
            )
    return state, tuple(moves), tuple(logs)


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
