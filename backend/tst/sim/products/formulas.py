"""Pure product and market formulas (docs/formulas.md section 11).

No randomness and no state: callers draw from their own stream (ADR-0013, ADR-0017) and
pass numbers in. Every number comes from `Balance`, the category data, or the scale
definitions in `tst.sim.scale`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Literal

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import (
    SCORE_MAX,
    AppealWeights,
    CategoryDef,
    ComputeIndexFile,
    MarketBalance,
    ProductsBalance,
)
from tst.sim.scale import ATTR_MAX, ATTR_NEUTRAL, MORALE_MAX

# Skill mixes for selling and marketing (11.3): (2 x main + two others) / 4.
MAIN_SKILL_WEIGHT = 2
MIX_DIVISOR = MAIN_SKILL_WEIGHT + 1 + 1
PRICE_SCORE_AT_REFERENCE = SCORE_MAX / 2  # 50 at the reference price (11.6)

type PaceLabel = Literal["fast", "steady", "slow"]


def clamp_score(value: float) -> float:
    """Quality, feature score, brand and price score live on [0, 100]."""
    return min(max(value, 0.0), float(SCORE_MAX))


# --- 11.3 Who works on a product ----------------------------------------------------------


def morale_factor(morale: float | None, pb: ProductsBalance) -> float:
    """m = 0.7 + 0.6 x morale / 100; the founder (no morale) uses 1."""
    if morale is None:
        return 1.0
    return pb.morale_factor_base + pb.morale_factor_slope * morale / MORALE_MAX


def dev_skill(skills: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """d = sum_k w_k x skill_k with the category's development weights."""
    return sum(w * skills[k] for k, w in weights.items())


def builder_output(d: float, m: float, t: float) -> float:
    """o_i = d_i / 10 x m_i x t_i."""
    return d / ATTR_NEUTRAL * m * t


def coord_factor(builders: int, pb: ProductsBalance) -> float:
    """coord(n) = max(0.6, 1 - 0.02 x max(0, n - 5))."""
    over = max(0, builders - pb.coord_free_builders)
    return max(pb.coord_floor, 1 - pb.coord_per_builder * over)


def dev_noise_sd(mavericks: int, pb: ProductsBalance) -> float:
    """sd = 0.15 + 0.10 per maverick builder, capped at 0.40."""
    return min(pb.dev_noise_sd + pb.maverick_noise_sd * mavericks, pb.dev_noise_sd_cap)


def tag_multiplier(tags: Iterable[str], pb: ProductsBalance) -> float:
    """t_i: the product of the output multipliers of the builder's true tags (11.10)."""
    t = 1.0
    for tag in tags:
        if tag in pb.tag:
            t *= pb.tag[tag].output
    return t


def qcap_skill(d: float, perfectionist: bool, pb: ProductsBalance) -> float:
    """A perfectionist's d counts as d + 3, capped at 20, in Q_cap (11.10)."""
    return min(d + pb.perfectionist_qcap_bonus, ATTR_MAX) if perfectionist else d


def quality_cap(builders: Sequence[tuple[float, float]], pb: ProductsBalance) -> float | None:
    """Q_cap = 5 x d-bar, d-bar the output-weighted d over (o_i, d_i) pairs (11.4).

    None when nobody produces output.
    """
    total = sum(o for o, _ in builders)
    if total <= 0:
        return None
    return pb.qcap_per_skill * sum(o * d for o, d in builders) / total


def next_quality(
    quality: float, output: float, scope: float, qcap: float | None, pb: ProductsBalance
) -> float:
    """One month of quality (11.4).

    Output below 0.25 sigma (no team, or a token one): quality rots 0.5 a month. Otherwise,
    below Q_cap it climbs 0.15 x min(1, o / sigma) of the gap; at or above Q_cap it falls 1%
    a month, never below Q_cap.
    """
    if qcap is None or output < pb.rot_threshold * scope:
        return clamp_score(quality - pb.rot_per_month)
    if quality < qcap:
        speed = min(1.0, output / scope)
        return clamp_score(quality + pb.quality_rate * speed * (qcap - quality))
    return clamp_score(max(qcap, quality * (1 - pb.overcap_decay)))


def is_rotting(output: float, scope: float, pb: ProductsBalance) -> bool:
    return output < pb.rot_threshold * scope


def pace(output: float, scope: float, pb: ProductsBalance) -> PaceLabel:
    """fast if min(1, o / sigma) >= 0.75, steady if >= 0.4, else slow (11.13)."""
    speed = min(1.0, output / scope)
    if speed >= pb.pace_bands.hi:
        return "fast"
    if speed >= pb.pace_bands.lo:
        return "steady"
    return "slow"


def sell_skill(sales: float, negotiation: float, communication: float) -> float:
    """sell_i = (2 sales + negotiation + communication) / 4."""
    return (MAIN_SKILL_WEIGHT * sales + negotiation + communication) / MIX_DIVISOR


def marketing_skill(marketing: float, communication: float, design: float) -> float:
    """mkt_i = (2 marketing + communication + design) / 4."""
    return (MAIN_SKILL_WEIGHT * marketing + communication + design) / MIX_DIVISOR


def contribution(skill: float, m: float) -> float:
    """One seller's or marketer's share: skill / 10 x m (11.3)."""
    return skill / ATTR_NEUTRAL * m


def seller_capacity(rate: float, contributions: Iterable[float]) -> float:
    """cap = r_s x sum of sell_i / 10 x m_i: new customers a month in a sales segment."""
    return rate * sum(contributions)


# --- 11.4 Features --------------------------------------------------------------------------


def expected_features(category: CategoryDef, turn: int) -> float:
    """F_exp(t) = F0 + dF x t."""
    return category.features_at_start + category.features_per_month * max(turn, 0)


def feature_score(points: float, category: CategoryDef, turn: int) -> float:
    """clamp(100 x F / F_exp(t), 0, 100)."""
    return clamp_score(SCORE_MAX * points / expected_features(category, turn))


def held_feature_points(score: float, category: CategoryDef, turn: int) -> float:
    """Feature points that give `score` at `turn`: an incumbent's F grows with F_exp (11.9)."""
    return score / SCORE_MAX * expected_features(category, turn)


# --- 11.5 Brand -----------------------------------------------------------------------------


def marketing_points(budget_cents: int, mu: float, pb: ProductsBalance) -> float:
    """mk = budget in $1,000s + 5 mu."""
    return budget_cents / pb.budget_mk_unit_cents + pb.marketer_mk * mu


def target_brand(mk: float, brand_constant: float) -> float:
    """B* = 100 x mk / (mk + K)."""
    return SCORE_MAX * mk / (mk + brand_constant) if mk > 0 else 0.0


def next_brand(brand: float, target: float, pb: ProductsBalance) -> float:
    """brand <- brand + 0.10 (B* - brand), kept in [0, 100]."""
    return clamp_score(brand + pb.brand_rate * (target - brand))


# --- 11.6 Appeal ----------------------------------------------------------------------------


def price_score(reference_cents: int, price_cents: int) -> float:
    """clamp(50 x p_ref / price, 0, 100): 50 at the reference price, 100 at half of it."""
    return clamp_score(PRICE_SCORE_AT_REFERENCE * reference_cents / price_cents)


def appeal(
    weights: AppealWeights, quality: float, price: float, brand: float, feature: float
) -> float:
    """appeal = w_q Q + w_p price_score + w_b brand + w_f feature."""
    return (
        weights.quality * quality
        + weights.price * price
        + weights.brand * brand
        + weights.features * feature
    )


# --- 11.7 Customers -------------------------------------------------------------------------


def churn_rate(
    base: float,
    best: float,
    own_appeal: float,
    quality: float,
    sunset: bool,
    mb: MarketBalance,
) -> float:
    """base x (1 + max(0, best - appeal) / 50) x 1.5 if Q < 40 x 3 if sunset, at most 1."""
    rate = base * (1 + max(0.0, best - own_appeal) / mb.gap_divisor)
    if quality < mb.low_quality_at:
        rate *= mb.low_quality_churn_mult
    if sunset:
        rate *= mb.sunset_churn_mult
    return min(rate, 1.0)


def choice_shares(
    appeals: Sequence[float], outside: float, mb: MarketBalance
) -> tuple[list[float], float]:
    """share*_i = appeal_i^g / (a0^g + sum_j appeal_j^g); also the no-purchase share."""
    powers = [max(a, 0.0) ** mb.gamma for a in appeals]
    total = outside**mb.gamma + sum(powers)
    return [p / total for p in powers], outside**mb.gamma / total


def awareness(brand: float, mb: MarketBalance) -> float:
    """0.5 x max(brand, 5) / 100: self-serve customers who hear of the product."""
    return mb.awareness_scale * max(brand, mb.awareness_floor) / SCORE_MAX


def monthly_growth(category: CategoryDef, year: int) -> float:
    """(1 + g)^(1/12): one month of addressable-demand growth (11.1); g is the year's
    growth_by_year entry for a category that has one (18.6)."""
    return float((1 + category.growth_in(year)) ** (1 / MONTHS_PER_YEAR))


def hosting_cents(category: CategoryDef, segment: str, index: ComputeIndexFile, year: int) -> float:
    """h per customer per month; x compute_index(year) for an indexed category (18.6)."""
    h = float(category.market(segment).hosting_cents)
    return h * index.of(year) if category.compute_indexed else h
