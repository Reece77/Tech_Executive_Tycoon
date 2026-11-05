"""Pure formulas for mergers and acquisitions (docs/formulas.md section 28): value ranges,
reservation prices, the board's bar, a tender's chance, antitrust's block probability and
integration flight. No state; every number comes from the caller or balance.yaml."""

from __future__ import annotations

import math

from tst.sim.mna.data import AntitrustBalance, IntegrationBalance, MnaBalance, TenderBalance

CENTRE = 0.5  # tunable-exempt: a uniform's midpoint, as 21.7's lead ranges


def acquihire_value_cents(cash_cents: int, builders: float, mb: MnaBalance) -> int:
    """A company with ARR below mna.min_arr_cents: its cash plus a value per builder (28.1)."""
    return max(0, cash_cents) + round(builders * mb.min_value_per_builder_cents)


def value_range_cents(value_cents: int, u: float, half_share: float) -> tuple[int, int]:
    """V_f x (1 +- half) off-centre by (u - 0.5) x half (28.1, as 21.7): the range always
    contains the true value and its midpoint is not the truth."""
    half = abs(value_cents) * half_share
    offset = (u - CENTRE) * half
    low = math.floor(value_cents + offset - half)
    high = math.ceil(value_cents + offset + half)
    return max(0, low), max(max(0, low) + 1, high)


def midpoint_cents(value_range: tuple[int, int]) -> int:
    """The estimate the player sees (28.1): the displayed range's midpoint."""
    return (value_range[0] + value_range[1]) // 2


def diligence_cost_cents(estimated_cents: int, mb: MnaBalance) -> int:
    """0.5% of the target's estimated value, at least $50,000 (28.2)."""
    d = mb.diligence
    return max(d.min_cents, round(estimated_cents * d.cost_bp / 10_000))  # tunable-exempt: bp


def personality_premium(personality: str, mb: MnaBalance) -> float:
    """p for an incumbent or a named rival by its personality (28.3)."""
    return mb.premium[personality]


def founder_premium(ambition: float, mb: MnaBalance) -> float:
    """p for a startup: its founder's 0.25 + 0.02 x (ambition - 10) (28.3)."""
    fp = mb.founder_premium
    return fp.base + fp.per_ambition * (ambition - fp.neutral)


def reservation_cents(value_cents: int, premium: float, distressed: bool, mb: MnaBalance) -> int:
    """A private target accepts at least V_f x (1 + p), p less the distress discount when
    its cash covers fewer than mna.distress_months of costs (28.3)."""
    p = premium - (mb.distress_discount if distressed else 0.0)
    return round(value_cents * (1 + p))


def distressed(cash_cents: int, monthly_costs_cents: int, mb: MnaBalance) -> bool:
    """Cash covers fewer than mna.distress_months of costs (28.3)."""
    return monthly_costs_cents > 0 and cash_cents < mb.distress_months * monthly_costs_cents


def counter_cents(reservation: int, z: float, mb: MnaBalance) -> int:
    """The private target's one counter: reservation x (1 + N(0, sd)), z a standard normal."""
    return round(reservation * (1 + mb.counter_sd * z))


def board_bar(z: float, mb: MnaBalance) -> float:
    """A listed target's board accepts a premium over market cap of at least this (28.3)."""
    return mb.board.bar + mb.board.sd * z


def premium_over(price_cents: int, market_cap_cents: int) -> float:
    return price_cents / market_cap_cents - 1 if market_cap_cents > 0 else math.inf


def tender_chance(premium: float, aggressive: bool, tb: TenderBalance) -> float:
    """A hostile tender succeeds with clamp((premium - 0.15) / 0.5, 0, 0.9), less the
    defence for an aggressive target (28.3)."""
    base = min(max((premium - tb.floor) / tb.span, 0.0), tb.cap)
    return max(0.0, base - (tb.defence if aggressive else 0.0))


def tender_fee_cents(price_cents: int, tb: TenderBalance) -> int:
    return round(price_cents * tb.fee_bp / 10_000)  # tunable-exempt: basis points


def block_probability(combined_share: float, year: int, ab: AntitrustBalance) -> float:
    """In review (0.35 <= S_c < 0.50): (S_c - 0.35) / 0.15 x strictness(year) (28.4); 1 at
    or above the block line, 0 below the review line."""
    if combined_share < ab.review:
        return 0.0
    if combined_share >= ab.block:
        return 1.0
    return (combined_share - ab.review) / (ab.block - ab.review) * ab.strictness_in(year)


def antitrust_outcome(combined_share: float, ab: AntitrustBalance) -> str:
    """cleared, review or blocked (28.4), from the highest combined share."""
    if combined_share < ab.review:
        return "cleared"
    return "review" if combined_share < ab.block else "blocked"


def personality_distance(gaps: list[float], ib: IntegrationBalance) -> float:
    """0-1 between two companies: the mean gap of their people's average personality traits
    over integration.distance_span attribute points (M14 decision for 28.5)."""
    if not gaps:
        return 0.0
    return min(1.0, sum(abs(g) for g in gaps) / len(gaps) / ib.distance_span)


def flight_chance(distance: float, ib: IntegrationBalance, *, brand: bool = False) -> float:
    """An acquired key person's monthly flight chance: 3% for a kept brand; 2% + 6% x
    distance when integrated (28.5)."""
    if brand:
        return ib.flight_brand
    return ib.flight_base + ib.flight_per_distance * distance


def clash_step(
    morale: float, target_morale: float, distance: float, ib: IntegrationBalance
) -> float:
    """One month of culture clash: morale moves clash x distance of the gap (28.5)."""
    return morale + ib.clash * distance * (target_morale - morale)


def blended_lead(mine: float, theirs: float, ib: IntegrationBalance) -> float:
    """The research lead after integrating: the higher of the two + 20% of the lower (28.5)."""
    return max(mine, theirs) + ib.tech_lower_share * min(mine, theirs)


def goodwill_cents(price_cents: int, book_equity_cents: int) -> int:
    """Price - the target's book equity, posted to 1800 at closing (28.3)."""
    return price_cents - book_equity_cents
