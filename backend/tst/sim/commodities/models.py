"""M17 records (docs/formulas.md 33.3): commodity contracts and offtake agreements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DealKind = Literal["contract", "offtake"]
DealStatus = Literal["active", "ended", "breached"]
MONTHS_PER_YEAR = 12  # tunable-exempt: calendar


@dataclass(frozen=True, slots=True)
class CommodityDeal:
    """A company's commodity deal (33.3). A **contract** fixes the price at signing for 6-36
    months (`floor == ceiling`; take-or-pay on the unused volume at the end). An **offtake**
    buys from a named supplier for 3-10 years inside a collar around the price at signing,
    take-or-pay each month, with optional prepayment that buys 100% allocation in shocks.

    Prices are in the good's unit (commodities_history.yaml); volumes in its volume unit."""

    id: int
    company_id: int
    kind: DealKind
    good: str
    signed_turn: int
    end_turn: int  # the last month it covers
    volume_year: float  # volume units a year
    signing_price: float
    floor: float
    ceiling: float
    supplier: str | None = None  # suppliers.yaml key (offtakes)
    prepaid_cents: int = 0  # paid at signing (1350)
    prepaid_left_cents: int = 0  # not yet drawn against purchases
    status: DealStatus = "active"
    taken: float = 0.0  # volume units taken so far
    last_taken: float = 0.0  # last month's
    last_price: float = 0.0  # last month's price paid
    hedge_cents: int = 0  # cost of goods saved (negative: paid above spot) so far
    charged_cents: int = 0  # take-or-pay charged so far
    closed_turn: int | None = None

    @property
    def monthly_volume(self) -> float:
        return self.volume_year / MONTHS_PER_YEAR

    def running(self, turn: int) -> bool:
        return self.status == "active" and self.signed_turn <= turn <= self.end_turn

    def price_for(self, spot: float) -> float:
        """The price paid against `spot`: inside the collar (a contract's is fixed), 33.3."""
        return min(self.ceiling, max(self.floor, spot))
