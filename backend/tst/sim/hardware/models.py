"""Frozen hardware and chip records (docs/formulas.md 26, M12b; ADR-0020). Every record
belongs to a `company_id`; nothing assumes one player company."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.money import MILLICENTS_PER_CENT

type ContractKind = Literal["assembly", "wafer"]
type ProductionContractStatus = Literal["active", "ended"]


@dataclass(frozen=True, slots=True)
class ProductionContract:
    """A contract-manufacturing contract (kind `assembly`: `units` a month assembled by a
    contract manufacturer for `fee_cents` a unit; 26.2) or a wafer contract (kind `wafer`:
    `units` wafer starts a month from a foundry at `price_cents` a wafer, the index locked at
    signing; 26.3). Take-or-pay charges a share of the price on each unused unit a month.
    `delivered`, `used` and `charged_cents` are the last month's. The price is stored exactly,
    in integer thousandths of a cent (M15r, Codex review 4 finding 8)."""

    id: int
    company_id: int
    product_id: int
    kind: ContractKind
    supplier: str  # hardware.contract.manufacturers or chips.contract.foundries key
    units: int  # a month: units assembled, or wafer starts
    price_millicents: int  # a unit's fee, or a wafer's price at the locked index, in 1/1000 cent
    signed_turn: int
    end_turn: int  # the last month it covers
    city: str | None = None  # cities.yaml key (assembly contracts)
    delivered: float = 0.0  # units available last month after allocation
    used: float = 0.0
    charged_cents: int = 0  # last month's take-or-pay
    status: ProductionContractStatus = "active"
    node: str | None = None  # M21 (38.1): a wafer contract at a named node (None: M12b's wafer)

    def running(self, turn: int) -> bool:
        return self.status == "active" and self.signed_turn <= turn <= self.end_turn

    @property
    def price_cents(self) -> float:
        """The price in cents (fractional), from its exact stored millicents."""
        return self.price_millicents / MILLICENTS_PER_CENT


@dataclass(frozen=True, slots=True)
class ProductionMonth:
    """What one unit-sale product made and sold in a month (26.2, 26.3): units by source,
    chips used, and the cost of goods by line (cents). History: append-only."""

    turn: int
    product_id: int
    company_id: int
    capacity: float  # units it could make this month
    units: float  # units sold (and made: build to order)
    plant_units: float = 0.0
    contract_units: float = 0.0
    own_chips: float = 0.0  # its own chips used (internal supply at cost, no revenue)
    bought_chips: float = 0.0
    internal_units: float = 0.0  # a chip product: chips its company's devices used
    bom_cents: int = 0
    chip_cents: int = 0
    assembly_cents: int = 0
    lost_units: float = 0.0  # demand above the capacity cap, lost to the next-best product

    @property
    def cogs_cents(self) -> int:
        return self.bom_cents + self.chip_cents + self.assembly_cents
