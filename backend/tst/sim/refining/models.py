"""M20 records (docs/formulas.md 36): a refinery's own state beside its generic facility, the
contracts refineries buy inputs and sell outputs under, and the month's own-group supply.

A refinery is a `Facility` (ADR-0020: one facility model) of a refinery kind; `Refinery` holds
what only refineries have, keyed by the facility's id. Every record belongs to a `company_id`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type DealSide = Literal["buy", "sell"]
type DealStatus = Literal["active", "ended"]


@dataclass(frozen=True, slots=True)
class PlantMonth:
    """One month of a plant (36.1), as the Refineries screen shows it. Volumes are in the
    goods' volume units; cents are the month's totals. `unit_cost_cents` is the full cost of a
    unit of output (inputs, power, other, fixed, depreciation and the plant's staff)."""

    turn: int
    output: float = 0.0
    capacity: float = 0.0  # what it could make this month at full input (after ramp, staff, curbs)
    yield_: float = 0.0  # the effective yield (36.3)
    input_group: float = 0.0  # input volume from the group (its mines and refineries)
    input_contract: float = 0.0
    input_spot: float = 0.0
    input_short: float = 0.0  # input it wanted but allocation did not give
    input_cents: int = 0
    power_cents: int = 0
    power_index: float = 1.0
    other_cents: int = 0
    fixed_cents: int = 0
    depreciation_cents: int = 0
    staff_cents: int = 0
    to_group: float = 0.0  # output supplied to the group's products and refineries
    to_contract: float = 0.0
    to_spot: float = 0.0
    revenue_cents: int = 0  # contract and spot sales, and intra-group sales at transfer price
    market_cents: float = 0.0  # the output's market price this month, cents a unit
    unit_cost_cents: float = 0.0

    @property
    def cost_cents(self) -> int:
        return (
            self.input_cents
            + self.power_cents
            + self.other_cents
            + self.fixed_cents
            + self.depreciation_cents
            + self.staff_cents
        )

    @property
    def market_value_cents(self) -> float:
        return self.output * self.market_cents

    @property
    def margin(self) -> float | None:
        """Operating margin at market prices (36.5 target 1): (value - cost) / value."""
        value = self.market_value_cents
        return (value - self.cost_cents) / value if value > 0 else None


@dataclass(frozen=True, slots=True)
class Refinery:
    """A refinery's own state (36.1). `estimate_cents` is the quoted capex the player saw; the
    facility's `capex_cents` carries the hidden overrun (revealed as it is paid)."""

    facility_id: int
    company_id: int
    recipe: str  # refining.recipes key
    estimate_cents: int
    host_id: int | None = None  # a by-product line's host plant (36.1)
    curb_until: int | None = None  # last month of a power curb (36.4)
    curb_run: float = 1.0
    stop_until: int | None = None  # an incident's stop and investigate: last month at zero
    incident_turn: int | None = None  # an incident event awaiting its answer
    incidents: int = 0
    last_depreciated_cents: int = 0  # the facility's accumulated depreciation last month
    mine_fed: float = 0.0  # input units the group's mines supplied this month (M19 merge)
    mine_protected: float = 0.0  # last month's: input that keeps 100% allocation this month
    month: PlantMonth | None = None  # the latest month
    history: tuple[tuple[int, float, float, float], ...] = ()  # (turn, output, unit, market)

    def curbed(self, turn: int) -> bool:
        return self.curb_until is not None and turn <= self.curb_until

    def stopped(self, turn: int) -> bool:
        return self.stop_until is not None and turn <= self.stop_until


@dataclass(frozen=True, slots=True)
class RefiningDeal:
    """A refinery contract (36.1): buy an input or sell an output at a price fixed at signing
    (the month's market price) for a monthly volume. A buy contract signed before a shortage
    keeps 100% allocation (as 22.4) and pays `refining.deal.take_or_pay` of what it does not
    take each month; a sell contract delivers what the company's plants make, up to its volume."""

    id: int
    company_id: int
    side: DealSide
    good: str
    signed_turn: int
    end_turn: int  # the last month it covers
    monthly_volume: float
    price_cents: float  # cents a volume unit
    taken: float = 0.0
    last_taken: float = 0.0
    charged_cents: int = 0  # take-or-pay so far
    status: DealStatus = "active"

    def running(self, turn: int) -> bool:
        return self.status == "active" and self.signed_turn <= turn <= self.end_turn


@dataclass(frozen=True, slots=True)
class OwnSupply:
    """Own-group supply this month (36.1, 36.2): `volume` units of `good` from a plant of
    `seller_id` to `buyer_id` at `unit_cents` (the transfer price; the plant's cost inside one
    company), against a market price of `market_cents`. A wafer lot names the chip product
    (`product_id`) whose wafer starts it covers; a commodity lot covers the buyer's use.
    `taken` is set after production (what the buyer used; the rest is sold at spot)."""

    turn: int
    facility_id: int
    seller_id: int
    buyer_id: int
    good: str
    volume: float
    unit_cents: float
    market_cents: float
    product_id: int | None = None
    taken: float = 0.0
