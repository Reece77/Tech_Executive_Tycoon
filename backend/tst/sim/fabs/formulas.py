"""Pure formulas for fabs and process nodes (docs/formulas.md 38, M21). Unit-tested in
tests/unit/test_m21_formulas.py with 38's worked numbers."""

from __future__ import annotations

from typing import Final

MONTHS: Final = 12


def capex_cents(starts: int, capital_cents: float, scale: float, cost_mult: float = 1.0) -> int:
    """capex = wafer starts a month x 12 x capital per wafer-per-year x fab.capex_scale (38.2),
    x the DUV route's cost multiplier at 7 nm."""
    return round(starts * MONTHS * capital_cents * scale * cost_mult)


def build_months(age_months: int, mature_age: int, leading: int, mature: int) -> int:
    """3 years for a node younger than `mature_age` months at the order (or not yet in volume),
    2 for an older one (38.2)."""
    return mature if age_months >= mature_age else leading


def yield_start(
    age_months: int, mature_age: int, start_leading: float, start_mature: float
) -> float:
    """A fab's first yield: 0.35 for a node at its first volume, 0.7 for one `mature_age`
    months or older at go-live, linear between (38.2)."""
    share = min(1.0, max(0.0, age_months / mature_age))
    return start_leading + (start_mature - start_leading) * share


def learn_rate(
    learn: float, skill: float, skill_ref: float, lead_over: float, bonus: float, cap: float
) -> float:
    """A month's share of the gap to mature yield closed (38.2): learn x skill / skill_ref x
    (1 + bonus x min(cap, process lead over the node's need)), at most 1."""
    rate = learn * (skill / skill_ref) * (1 + bonus * min(cap, max(0.0, lead_over)))
    return min(1.0, max(0.0, rate))


def next_yield(current: float, mature: float, rate: float) -> float:
    """One month of learning: the yield closes `rate` of its gap to mature (38.2)."""
    return current + (mature - current) * rate


def months_to(target: float, start: float, mature: float, rate: float) -> int | None:
    """Months of learning from `start` to `target` at a constant rate (38.5 target 4)."""
    if start >= target:
        return 0
    if target >= mature or rate <= 0:
        return None
    months, y = 0, start
    while y < target:
        y = next_yield(y, mature, rate)
        months += 1
    return months


def power_mwh(base: float, per_generation: float, generation: int) -> float:
    """MWh a wafer start: base + per_generation x the node's generation (38.2)."""
    return base + per_generation * generation


def node_price_cents(
    wafer_cents: float,
    index_now: float,
    index_ref: float,
    behind_now: int,
    behind_ref: int,
    decay: float,
    factor: float,
) -> float:
    """A node's market wafer price (38.1): its reference price x the foundry wafer index since
    the reference month x (1 - decay) for each generation it is further behind the edge than
    then (dearer when it was nearer the edge),
    x the foundry market's capacity factor (38.3)."""
    steps = behind_now - behind_ref
    return wafer_cents * (index_now / index_ref) * (1 - decay) ** steps * factor


def die_cents(
    wafer_cost_cents: float,
    per_wafer: int,
    chip_yield: float,
    fab_yield: float,
    mature_yield: float,
    packaging_cents: int,
) -> float:
    """Own-fab cost per good die (38.2 with 26.3): the fab's cost a wafer start / (chips per
    wafer x the design's yield x fab yield / mature yield) + packaging. A mature fab's die costs
    what a foundry's would at the same wafer price."""
    good = per_wafer * chip_yield * min(1.0, fab_yield / mature_yield)
    return wafer_cost_cents / good + packaging_cents if good > 0 else float("inf")


def node_quality_points(generation: int, median_generation: int, per_generation: float) -> float:
    """Quality cap points for being ahead of the category's median node (38.4): +3 a generation;
    nothing for being at or behind it."""
    return per_generation * max(0, generation - median_generation)


def tools_needed(starts: int, per_tool: int) -> int:
    """EUV tools a fab of `starts` wafer starts a month needs (38.2)."""
    return -(-starts // per_tool)


def irr(cash_flows: list[float]) -> float | None:
    """The annual internal rate of return of monthly cash flows, by bisection (38.5 target 3);
    None when the flows never change sign."""
    if not any(c < 0 for c in cash_flows) or not any(c > 0 for c in cash_flows):
        return None

    def npv(rate: float) -> float:
        m = (1 + rate) ** (1 / MONTHS)
        return float(sum(c / m**i for i, c in enumerate(cash_flows)))

    lo, hi = -0.99, 2.0  # tunable-exempt: the bisection's bounds on the annual rate
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(_STEPS):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


_STEPS: Final = 200  # tunable-exempt: bisection steps
