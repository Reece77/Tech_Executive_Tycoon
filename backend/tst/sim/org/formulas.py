"""Pure organization formulas (docs/formulas.md sections 7 and 13).

No randomness and no state: callers resolve managers and teammates and pass numbers in.
Every number comes from `Balance` or from the scale definitions in `tst.sim.scale`.
"""

from __future__ import annotations

import math
from typing import Literal

from tst.sim.data_models import HiringBalance, OrgBalance
from tst.sim.money import BP_DENOMINATOR
from tst.sim.scale import ATTR_NEUTRAL

LEADERSHIP_WEIGHT = 2  # Q = (2 leadership + communication + mentoring) / 4 x S (13.3)
QUALITY_DIVISOR = LEADERSHIP_WEIGHT + 1 + 1  # weights of leadership, communication, mentoring


def span_limit(leadership: float, org: OrgBalance) -> int:
    """L = 5 + floor(leadership / 4) (13.2)."""
    return org.span_base + math.floor(leadership / org.span_per_leadership)


def span_factor(leadership: float, reports: int, org: OrgBalance) -> float:
    """S = 1 up to L direct reports, else L / n (13.2)."""
    limit = span_limit(leadership, org)
    return 1.0 if reports <= limit else limit / reports


def manager_quality(
    leadership: float, communication: float, mentoring: float, span: float
) -> float:
    """Q = (2 leadership + communication + mentoring) / 4 x S (13.3)."""
    return (LEADERSHIP_WEIGHT * leadership + communication + mentoring) / QUALITY_DIVISOR * span


def manager_morale_term(quality: float, org: OrgBalance) -> float:
    """W_mgr = clamp(0.8 (Q - 10), -8, +8) (13.4)."""
    raw = org.manager_morale_slope * (quality - ATTR_NEUTRAL)
    return min(max(raw, -org.manager_morale_cap), org.manager_morale_cap)


type ManagerLabel = Literal["strong", "fine", "stretched"]


def manager_label(morale_term: float, org: OrgBalance) -> ManagerLabel:
    """How a manager comes across, from their W_mgr (13.4): strong at or above the upper
    band, stretched at or below the lower band, else fine (M2b display label)."""
    if morale_term >= org.manager_label_bands.hi:
        return "strong"
    if morale_term <= org.manager_label_bands.lo:
        return "stretched"
    return "fine"


def growth_multiplier(
    mentoring: float, span: float, mentor_teammate: bool, org: OrgBalance
) -> float:
    """M_growth = clamp(1 + (mentoring S + bonus - 5) / 20, 0.75, 1.5) (13.5)."""
    bonus = org.mentor_tag_bonus if mentor_teammate else 0.0
    raw = 1 + (mentoring * span + bonus - org.mentoring_neutral) / org.mentoring_divisor
    return min(max(raw, org.growth_mult_min), org.growth_mult_max)


def tag_term(tag: str, holders: int, org: OrgBalance) -> float:
    """Each other holder of `tag` in the unit adds its effect; the sum is capped (13.6)."""
    total = org.tag_morale[tag] * holders
    cap = org.tag_morale_cap[tag]
    return min(total, cap) if cap >= 0 else max(total, cap)


def remote_term(sociability: float, remote: bool, org: OrgBalance) -> float:
    """-3 if sociability >= 14, +2 if <= 7, else 0, for remote workers only (13.9)."""
    if not remote:
        return 0.0
    if sociability >= org.remote.sociable_at:
        return org.remote.sociable_morale
    if sociability <= org.remote.solitary_at:
        return org.remote.solitary_morale
    return 0.0


def pitch(recruiting: float, hiring: HiringBalance) -> float:
    """0.3 x (recruiting - 10) / 10, from whoever made the offer (formulas.md 7, M2)."""
    return hiring.pitch_per_recruiting * (recruiting - hiring.pitch_neutral) / ATTR_NEUTRAL


def is_raise_bonus(old_cents: int, new_cents: int, org: OrgBalance) -> bool:
    """A raise of at least raise_threshold_bp of the old salary (exact integer test, 13.8)."""
    return new_cents * BP_DENOMINATOR >= old_cents * (BP_DENOMINATOR + org.raise_threshold_bp)
