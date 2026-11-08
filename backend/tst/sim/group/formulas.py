"""The group's formulas (docs/formulas.md 31.3-31.7), pure and exact: stakes as basis points,
money as integer cents, rates through `exact` and rounded half-to-even once (ADR-0003)."""

from __future__ import annotations

from fractions import Fraction
from typing import Literal

from tst.sim.data_models import Balance
from tst.sim.group.models import FULL_STAKE_BP
from tst.sim.money import exact

type Treatment = Literal["consolidated", "equity", "fair_value"]


def _round(x: Fraction) -> int:
    return round(x)  # Fraction rounds half to even


def stake(stake_bp: int) -> Fraction:
    return Fraction(stake_bp, FULL_STAKE_BP)


def treatment(stake_bp: int, balance: Balance) -> Treatment:
    """31.3: 50% or more is consolidated, 20-50% an associate, below 20% fair value."""
    held = stake(stake_bp)
    if held >= exact(balance.group.control):
        return "consolidated"
    if held >= exact(balance.group.influence):
        return "equity"
    return "fair_value"


def nci_cents(net_assets_cents: int, stake_bp: int) -> int:
    """31.3: the outside holders' share of a consolidated subsidiary's net assets (or of its
    profit): (1 - stake) x amount."""
    return _round((1 - stake(stake_bp)) * net_assets_cents)


def equity_method_cents(
    cost_cents: int, profit_cents: int, dividends_cents: int, stake_bp: int
) -> int:
    """31.3: an associate's carrying amount: its cost, plus the group's share of its profit,
    less the group's share of its dividends."""
    held = stake(stake_bp)
    return cost_cents + _round(held * profit_cents) - _round(held * dividends_cents)


def conglomerate_discount(
    segments: int, intra_share: float | Fraction, balance: Balance
) -> Fraction:
    """31.7: d = clamp(base + per_segment x (segments - 1) - synergy x intra-group share,
    min, max)."""
    db = balance.group.discount
    d = (
        exact(db.base)
        + exact(db.per_segment) * max(segments - 1, 0)
        - exact(db.synergy) * exact(intra_share)
    )
    return min(max(d, exact(db.min)), exact(db.max))


def discounted_cents(parts_cents: int, discount: Fraction) -> int:
    """31.7: the sum of the parts after the conglomerate discount."""
    return _round(parts_cents * (1 - discount))


def stake_price_cents(value_cents: int, stake_bp: int, discount: float = 0.0) -> int:
    """A stake's price: value x stake x (1 - discount) (31.5; discount 0 for a listed one)."""
    return _round(value_cents * stake(stake_bp) * (1 - exact(discount)))


def buyout_cents(value_cents: int, minority_bp: int, premium: float) -> int:
    """31.5: buying out minorities at their share of value plus the premium."""
    return _round(value_cents * stake(minority_bp) * (1 + exact(premium)))


def market_stake_cents(cap_cents: int, from_bp: int, to_bp: int, impact: float) -> int:
    """31.5: buying a listed rival from `from_bp` to `to_bp` on the market. Each 1% of the
    target already bought raises the price of the next by `impact`: the average multiplier
    over the purchase is 1 + impact x (the midpoint in percent)."""
    bought = stake(to_bp - from_bp)
    midpoint_pct = Fraction(from_bp + to_bp, 2 * 100)
    return _round(cap_cents * bought * (1 + exact(impact) * midpoint_pct))


def minority_seats(minority_bp: int, balance: Balance) -> int:
    """31.4: one board seat per `group.seat_per_stake` held by minorities."""
    return int(stake(minority_bp) // exact(balance.group.seat_per_stake))


def transfer_price_cents(
    kind: str, cost_cents: int, market_cents: int, balance: Balance, margin: float | None = None
) -> int:
    """31.6: an intra-group flow's price per unit: cost, cost plus a margin, or market."""
    if kind == "cost":
        return cost_cents
    if kind == "cost_plus":
        m = balance.group.cost_plus if margin is None else margin
        return _round(cost_cents * (1 + exact(m)))
    return market_cents


def unfair(price_cents: int, market_cents: int, balance: Balance) -> bool:
    """31.6: more than `group.fairness_band` from the market price."""
    if market_cents <= 0:
        return False
    gap = abs(Fraction(price_cents - market_cents, market_cents))
    return gap > exact(balance.group.fairness_band)
