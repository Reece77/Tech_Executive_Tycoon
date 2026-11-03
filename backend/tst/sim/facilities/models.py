"""Frozen facility, market-good and contract models (docs/formulas.md 22, M12a; ADR-0020).

One facility model with kinds (`balance.facility.kinds`): data centres now, assembly plants
in M12b, mines, refineries, wafer plants and fabs in v3. Every record belongs to a
`company_id`; nothing assumes one player company.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type FacilityStatus = Literal["building", "live", "closed"]
type ContractStatus = Literal["active", "settled"]


@dataclass(frozen=True, slots=True)
class Facility:
    """A facility (22.2). `capacity` units are ordered at `ordered_turn`; `on_time` of them
    are live from `ready_turn`, the rest from `late_turn` (an allocation shortfall, 22.4).
    Capex is paid in equal monthly parts until `ready_turn`; depreciation runs straight-line
    over the kind's life from when each part goes live. GameState holds facilities that are
    not closed; a closed one keeps its row."""

    id: int
    company_id: int
    kind: str  # balance.facility.kinds key
    region: str  # regions.yaml key
    capacity: int  # units of the kind's capacity unit (CU for data centres)
    on_time: int
    ordered_turn: int
    ready_turn: int
    late_turn: int
    capex_cents: int  # the whole build at the input good's index (or the contract's)
    input_index: float  # the input good's index the capex was priced at
    capex_paid_cents: int = 0
    depreciated_cents: int = 0
    status: FacilityStatus = "building"
    city: str | None = None  # cities.yaml key; None for a regional site (v3 uses it)
    unit_id: int | None = None  # the org unit that staffs it
    contract_id: int | None = None
    closed_turn: int | None = None
    # M12b (26.2), assembly plants: this month's yield (after noise), and last month's units
    # run for the company's own products and sold as contract manufacturing
    yield_rate: float = 0.0
    run_units: float = 0.0
    sold_units: float = 0.0

    def live_capacity(self, turn: int) -> int:
        """Units working in `turn`."""
        if self.status == "closed" or turn < self.ready_turn:
            return 0
        return self.on_time if turn < self.late_turn else self.capacity

    @property
    def book_value_cents(self) -> int:
        return self.capex_paid_cents - self.depreciated_cents


@dataclass(frozen=True, slots=True)
class GoodMonth:
    """One market good's month (22.4; ADR-0020 3): its index and allocation, the trend
    beneath any shock, the trend's yearly change, and the latest shock."""

    good: str  # components_history.yaml key
    turn: int
    index: float
    allocation: float  # share of a build's units delivered on time
    base: float  # the index without the shock's rise
    change: float  # the trend's yearly change (fraction)
    shock_turn: int | None = None  # the latest shock's first month
    shock_months: int = 0
    shock_rise: float = 0.0
    shock_allocation: float = 1.0

    def in_shock(self, turn: int) -> bool:
        return self.shock_turn is not None and turn < self.shock_turn + self.shock_months


@dataclass(frozen=True, slots=True)
class SupplyContract:
    """A component contract (22.4): `good` locked at `index` until `end_turn` on a volume of
    capacity units built; take-or-pay charges the unused volume's share at the end."""

    id: int
    company_id: int
    good: str
    index: float
    signed_turn: int
    end_turn: int  # the last month it covers
    volume: int  # capacity units
    unit_value_cents: int  # capex of one unit at the locked index (for take-or-pay)
    used: int = 0
    status: ContractStatus = "active"
    settled_cents: int = 0  # the take-or-pay charge at the end

    @property
    def remaining(self) -> int:
        return max(0, self.volume - self.used)


@dataclass(frozen=True, slots=True)
class Outage:
    """A data-centre outage (22.5): history for the API."""

    id: int
    facility_id: int
    company_id: int
    turn: int
    customers_lost: float
