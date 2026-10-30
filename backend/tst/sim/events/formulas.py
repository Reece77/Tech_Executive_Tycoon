"""Event formulas (docs/formulas.md 16.1-16.3): candidate weights, severity, effect caps."""

from __future__ import annotations

from tst.sim.data_models import EventsBalance, TriggerBalance
from tst.sim.events.data import NON_NEGATIVE, VALUELESS, Severity
from tst.sim.money import BP_DENOMINATOR, Cents


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def below_strength(value: float, cfg: TriggerBalance) -> float | None:
    """Strength of a "below" trigger: (below - value) / span, None when it does not hold."""
    if cfg.below is None or cfg.span is None or value >= cfg.below:
        return None
    return clamp01((cfg.below - value) / cfg.span)


def candidate_weight(
    template_weight: float,
    strength: float,
    *,
    category_used_last_month: bool,
    blocked: bool,
    events: EventsBalance,
) -> float:
    """16.1: template weight x trigger strength x 0.5 if its category was used last month,
    x 0 if the template ran in the last 24 months or a named person in the last 6."""
    if blocked:
        return 0.0
    factor = events.category_repeat_factor if category_used_last_month else 1.0
    return template_weight * strength * factor


def severity_for(
    strength: float,
    allowed: tuple[Severity, ...],
    *,
    critical_ok: bool,
    events: EventsBalance,
) -> Severity | None:
    """16.1: minor below major_from, major from it; critical only for a critical template
    whose trigger allows it and with no critical event in the gap. None: the template
    cannot run (it is critical-only and critical is not allowed)."""
    if "critical" in allowed and critical_ok:
        return "critical"
    wanted: Severity = "major" if strength >= events.major_from else "minor"
    if wanted in allowed:
        return wanted
    usable = [s for s in allowed if s != "critical"]
    return usable[0] if usable else None


def cash_base_cents(cash: Cents, monthly_revenue: Cents, events: EventsBalance) -> Cents:
    """16.3: cash effects are capped in bp of max(cash, 3 x monthly revenue)."""
    return max(cash, round(events.cash_revenue_months * monthly_revenue), 0)


def effect_cap(
    effect: str, severity: Severity, events: EventsBalance, cash_base: Cents, *, gain: bool
) -> float:
    """The largest size of an effect (16.3); cash in cents, gains at half the cost cap."""
    if effect in VALUELESS or effect == "resign":
        return 0.0
    cap = events.cap(effect, severity)
    if effect != "cash_delta":
        return cap
    cost_cap = cash_base * cap / BP_DENOMINATOR
    return cost_cap * events.cash_gain_share if gain else cost_cap


def clamp_effect(
    effect: str, value: float, severity: Severity, events: EventsBalance, cash_base: Cents
) -> float:
    """A value clamped to its cap (16.3); growth boosts and raises are never negative, and
    cash is rounded to whole cents."""
    if effect in VALUELESS or effect == "resign":
        return 0.0
    cap = effect_cap(effect, severity, events, cash_base, gain=value > 0)
    low = 0.0 if effect in NON_NEGATIVE else -cap
    out = max(low, min(cap, value))
    return float(round(out)) if effect == "cash_delta" else out


def share_value(
    effect: str, share: float, severity: Severity, events: EventsBalance, cash_base: Cents
) -> float:
    """A template effect's value: its share of the cap (16.4)."""
    return clamp_effect(
        effect,
        share * effect_cap(effect, severity, events, cash_base, gain=share > 0),
        severity,
        events,
        cash_base,
    )


def size_word(effect: str, value: float, severity: Severity, events: EventsBalance) -> str:
    """The size word ("small", none, or "large") of an effect against its cap, for the words the
    API shows instead of numbers (16.9). Cash is described by its amount instead."""
    if effect in VALUELESS or effect in ("resign", "cash_delta"):
        return ""
    share = abs(value) / events.cap(effect, severity)
    if share <= events.effect_size_bounds.lo:
        return "small"
    if share > events.effect_size_bounds.hi:
        return "large"
    return ""
