"""Pure formulas of docs/formulas.md 25 (M13). No state, no RNG: draws come in as numbers."""

from __future__ import annotations

import math

from tst.sim.markets_public.config import (
    AnalystsBalance,
    DemandBalance,
    EarningsBalance,
    FirstDayBalance,
    IpoBalance,
    MultipleBalance,
    SentimentBalance,
)
from tst.sim.markets_public.models import Rating, Result

PCT = 100
BP = 10_000  # tunable-exempt: basis points in one


def multiple(
    growth: float, margin: float, base_rate_pct: float, climate: float, mb: MultipleBalance
) -> float:
    """m = clamp(base + growth g + margin x m_op - rate (r_base - pivot), bounds) x v (25.3)."""
    raw = (
        mb.base
        + mb.growth * growth
        + mb.margin * margin
        - mb.rate * (base_rate_pct - mb.rate_pivot)
    )
    return mb.bounds.clamp(raw) * climate


def fundamental_value_cents(arr_cents: int, m: float) -> int:
    """V_f = ARR x m (25.3)."""
    return round(arr_cents * m)


def per_share_cents(value_cents: int, shares: int) -> int:
    return round(value_cents / shares) if shares > 0 else 0


def new_shares(shares_before: int, share_sold: float) -> int:
    """New shares that make `share_sold` of the post-IPO fully diluted count (25.2 step 3)."""
    return round(shares_before * share_sold / (1 - share_sold))


def offer_price_cents(
    value_cents: int, shares_after: int, quality: float, ambition: float, dual_discount: float
) -> int:
    """V_f x bank quality x ambition, per post-IPO share; dual-class prices lower (25.2)."""
    return round(value_cents * quality * ambition * (1 - dual_discount) / shares_after)


def book_demand(z: float, climate: float, db: DemandBalance) -> float:
    """d = clamp(N(mean + climate x (v - 1), sd), bounds), with z a standard normal (25.2)."""
    return db.bounds.clamp(db.mean + db.climate * (climate - 1) + db.sd * z)


def demand_word(d: float, ib: IpoBalance) -> str:
    """The book in words (25.8): never the draw."""
    for word in ib.demand_words:
        if d < word.below:
            return word.word
    return ib.demand_top_word


def first_day_return(d: float, ambition: float, fb: FirstDayBalance) -> float:
    """r = clamp(0.25 (d - 1) - 0.15 (a - 1) / 0.15, -0.3, 0.8) (25.2 step 5). M13 reads `a`
    as the final price over the fair price, so a raise or a cut counts as ambition too."""
    return fb.bounds.clamp(fb.demand * (d - 1) - fb.ambition * (ambition - 1) / fb.step)


def fee_cents(gross_cents: int, fee: float) -> int:
    return round(gross_cents * fee)


def sentiment_step(sentiment: float, z: float, sb: SentimentBalance) -> float:
    """S' = 1 + phi (S - 1) + sd z, clamped (25.3)."""
    return sb.bounds.clamp(1 + sb.phi * (sentiment - 1) + sb.sd * z)


def share_price_cents(value_cents: int, shares: int, sentiment: float) -> int:
    """P = V_f / shares x S (25.3)."""
    return max(1, round(value_cents * sentiment / shares)) if shares > 0 else 0


def analyst_count(cap_cents: int, ab: AnalystsBalance) -> int:
    """3 analysts, one more per doubling of market cap above base_cap, at most 8 (25.3)."""
    if cap_cents <= ab.base_cap_cents:
        return ab.min
    return min(ab.max, ab.min + int(math.log2(cap_cents / ab.base_cap_cents)))


def rating(target_cents: int, price_cents: int, ab: AnalystsBalance) -> Rating:
    """Buy above 1.15 x the price, sell below 0.9, otherwise hold (25.3)."""
    ratio = target_cents / price_cents if price_cents > 0 else 1.0
    if ratio > ab.buy_above:
        return "buy"
    if ratio < ab.sell_below:
        return "sell"
    return "hold"


def surprise(actual_cents: int, guided_cents: int) -> float:
    """s = actual / guided - 1 (25.4)."""
    return actual_cents / guided_cents - 1 if guided_cents > 0 else 0.0


def margin_surprise_points(actual_bp: int, guided_bp: int) -> float:
    """sm = actual margin - guided margin, in percentage points (25.4)."""
    return (actual_bp - guided_bp) / PCT


def earnings_jump(s: float, sm: float, eb: EarningsBalance) -> float:
    """clamp(3 s + 0.02 sm, -0.25, +0.20): sentiment x (1 + this) (25.4)."""
    return eb.jump.clamp(eb.revenue_weight * s + eb.margin_weight * sm)


def result_of(s: float, eb: EarningsBalance) -> Result:
    if s < eb.miss_below:
        return "miss"
    if s >= eb.beat_from:
        return "beat"
    return "inline"


def margin_bp(op_cents: int, revenue_cents: int) -> int:
    return round(op_cents * BP / revenue_cents) if revenue_cents > 0 else 0


def ceo_score(skills: dict[str, float], weights: dict[str, float]) -> float:
    """The CEO's score s: a weighted mean of true skills (25.6). Never shown."""
    return sum(w * skills[k] for k, w in weights.items())
