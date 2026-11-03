"""Pure formulas for fabless chips (docs/formulas.md 26.3, M12b). The 26.7 chip worked
example is a unit test of these functions."""

from __future__ import annotations


def chip_yield(base: float, per_lead: float, lead: float, cap: float) -> float:
    """yield = 0.70 + 0.003 x chip-design lead, at most the cap (0.92; 0.95 after
    Chiplets) (26.3)."""
    return min(cap, base + per_lead * max(0.0, lead))


def chip_unit_cents(wafer_cents: float, per_wafer: int, yield_rate: float, packaging: int) -> float:
    """wafer price / (chips per wafer x yield) + packaging and test (26.3): $9,000 / 45.6 +
    $8 = $205.37 (26.7)."""
    return wafer_cents / (per_wafer * yield_rate) + packaging


def chips_from_wafers(wafers: float, per_wafer: int, yield_rate: float) -> float:
    """Good chips from a month's wafer starts."""
    return wafers * per_wafer * yield_rate


def gpu_capex_factor(own_cost: float, market_price: float, floor: float, share: float) -> float:
    """Own accelerators in own GPU data centres: capex x (0.4 + 0.6 x own unit cost / market
    chip price), never above 1 (26.3)."""
    if market_price <= 0:
        return 1.0
    return min(1.0, floor + share * own_cost / market_price)
