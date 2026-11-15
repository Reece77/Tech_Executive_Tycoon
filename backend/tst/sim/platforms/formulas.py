"""Platforms' formulas (docs/formulas.md 44.2-44.4), pure functions of numbers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tst.sim.money import exact
from tst.sim.platforms.config import PlatformsBalance


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def attractiveness(
    users: float, fee: float, tools: float, goodwill: float, pb: PlatformsBalance
) -> float:
    """A_p = U_p^alpha x (1 - f_p)^beta x T_p x G_p (44.2)."""
    if users <= 0:
        return 0.0
    return float(users**pb.reach_exp * max(0.0, 1 - fee) ** pb.fee_exp * tools * goodwill)


def next_dev_shares(
    shares: Mapping[int, float], attract: Mapping[int, float], pb: PlatformsBalance
) -> dict[int, float]:
    """Developer shares move toward A_p / sum A with inertia (44.2); they stay a distribution."""
    total = sum(attract.values())
    if total <= 0:
        return dict(shares)
    k = pb.dev_inertia
    out = {p: k * shares.get(p, 0.0) + (1 - k) * attract.get(p, 0.0) / total for p in attract}
    norm = sum(out.values())
    return {p: v / norm for p, v in out.items()} if norm > 0 else out


def developer_months(dev_share: float, users: float, pb: PlatformsBalance) -> float:
    """Multi-homing (44.2): the largest `multihome_share` of developers are on every platform
    with at least `multihome_min_users` of users; the rest by attention share."""
    multi = pb.multihome_share if users >= pb.multihome_min_users else 0.0
    return multi + (1 - pb.multihome_share) * dev_share


def next_catalogue(
    catalogue: float, developers: float, months: float, pb: PlatformsBalance
) -> float:
    """C_p accumulates developer months and decays (44.2)."""
    return catalogue * (1 - pb.catalogue_decay) + developers * months


def catalogue_index(catalogue: float, leader: float) -> float:
    """C_p shown relative to the regional leader (100)."""
    return 100.0 * catalogue / leader if leader > 0 else 0.0


def catalogue_points(catalogue: float, leader: float, pb: PlatformsBalance) -> float:
    """A device's feature points from its platform's catalogue (44.3): capped in [-floor, 0]."""
    if leader <= 0:
        return 0.0
    return clamp(pb.catalogue_points * (catalogue / leader - 1), -pb.catalogue_floor, 0.0)


def stay_probability(index: float, pb: PlatformsBalance) -> float:
    """A replacing customer stays (44.3): `stay` at parity, less `stay_drop` per `stay_step`
    index points behind the leader."""
    behind = max(0.0, 100.0 - index)
    return clamp(pb.stay - pb.stay_drop * behind / pb.stay_step, 0.0, 1.0)


def dev_churn_factor(index: float, pb: PlatformsBalance) -> float:
    """A developer platform's churn multiplier (44.3): `dev_churn_cut` off at a full catalogue."""
    return 1 - pb.dev_churn_cut * clamp(index, 0.0, 100.0) / 100.0


def replace_users(
    rest: Mapping[int, float],
    stay: Mapping[int, float],
    weights: Mapping[int, float],
    replacement_months: float,
) -> dict[int, float]:
    """The rest of the market's month (44.3): 1/R of each platform's users replace; `stay` of
    them stay; the others choose afresh by `weights` (users x catalogue tilt, 0 where they may
    not choose). Shares are conserved."""
    r = max(1.0, replacement_months)
    leaving = {p: rest.get(p, 0.0) / r * (1 - stay.get(p, 0.0)) for p in rest}
    pool = sum(leaving.values())
    total = sum(weights.values())
    out = {p: rest.get(p, 0.0) - leaving[p] for p in rest}
    if total <= 0:
        return {p: rest.get(p, 0.0) for p in rest}
    for p, w in weights.items():
        out[p] = out.get(p, 0.0) + pool * w / total
    return out


def effective_fee(
    standard: float,
    small_rate: float | None,
    small: bool,
    sub_rate: float | None,
    sub_after_year: bool,
    subscription_share: float,
    renewal_share: float,
    regulated: Sequence[tuple[float, float]],
) -> float:
    """The effective fee on a seller's store revenue in a region (44.4): the standard or small-
    business rate on one-off sales, the subscription rate on subscriptions (after a year: only
    on `renewal_share` of them), then each regulated path's (share of revenue, rate)."""
    base = small_rate if small and small_rate is not None else standard
    if sub_rate is None:
        sub = base
    else:
        rate = min(sub_rate, base)
        sub = renewal_share * rate + (1 - renewal_share) * base if sub_after_year else rate
    fee = (1 - subscription_share) * base + subscription_share * sub
    for share, rate in regulated:
        fee = (1 - share) * fee + share * min(rate, fee)
    return fee


def fee_cents(revenue_cents: int, paid_share: float, users: float, fee: float) -> int:
    """The fee on one platform's part of a seller's regional revenue (44.4)."""
    return round(revenue_cents * exact(paid_share) * exact(users) * exact(fee))
