"""M13 state (docs/formulas.md 25): a company's IPO chain, its life as a listed company,
analysts, quarterly guidance, monthly share prices, and the Chair and CEO.

ADR-0020 section 7: everything here belongs to a `company_id`, so a v3 subsidiary can list on
its own. Fields marked hidden never reach the API or an LLM prompt (25.8, ADR-0007).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ListingStatus = Literal[
    "hired",  # banks hired; the S-1 event comes next month
    "filing",  # the S-1 event is out
    "roadshow",  # the roadshow's events are out
    "pricing",  # book demand drawn; the pricing critical event is out
    "priced",  # the price is set; the company lists in this turn
    "listed",
    "pulled",
]
PriceChoice = Literal["range", "raise", "cut", "pull"]
Rating = Literal["buy", "hold", "sell"]
Result = Literal["beat", "inline", "miss"]


@dataclass(frozen=True, slots=True)
class Listing:
    """A company's IPO chain (25.2), from hiring the banks to the listing or a pull. One per
    company: hiring banks again after a pull replaces it."""

    company_id: int
    bank: str  # banks.yaml key
    hired_turn: int
    status: ListingStatus = "hired"
    filed_late: bool | None = None  # the S-1 choice restated a metric (a month's delay)
    roadshow_turn: int | None = None  # the month the roadshow's events are due
    ambition: str | None = None  # high, middle or low
    share_choice: str | None = None  # low, middle or high: ipo.share_sold
    dual_class: bool | None = None
    demand: float | None = None  # hidden: the book's draw (25.8 shows only its word)
    price_choice: PriceChoice | None = None
    shares_before: int = 0  # fully diluted shares at the pricing
    new_shares: int = 0
    price_cents: int = 0  # per share: the bank's suggestion at pricing, then the final price
    gross_cents: int = 0
    fee_cents: int = 0
    first_day_return: float | None = None
    close_cents: int = 0  # the first day's closing price
    listed_turn: int | None = None
    pulled_turn: int | None = None
    ticker: str = ""

    @property
    def active(self) -> bool:
        """In the chain: banks hired, not yet listed or pulled."""
        return self.status not in ("listed", "pulled")


@dataclass(frozen=True, slots=True)
class Analyst:
    """One covering analyst (25.3): a target refreshed after each report; the rating follows
    target / price each month."""

    index: int  # position in public.analysts.firms
    target_cents: int
    rating: Rating


@dataclass(frozen=True, slots=True)
class PublicCompany:
    """A listed company's market state (25.3-25.5)."""

    company_id: int
    listed_turn: int
    ticker: str
    dual_class: bool
    listing_price_cents: int
    price_cents: int  # the share price at the last month end
    sentiment: float  # hidden (25.8): S, which also carries the future's drift
    value_cents: int  # hidden (25.8): V_f at the last month end
    analysts: tuple[Analyst, ...] = ()
    below_value_months: int = 0  # months P < activist share x V_f per share (25.4)
    below_takeover_months: int = 0  # months cap < takeover share x V_f (25.4)
    last_activist_turn: int | None = None
    last_takeover_turn: int | None = None
    beat_streak: int = 0
    miss_streak: int = 0
    results: tuple[Result, ...] = ()  # each report's result, oldest first (the last 8)
    quarter_revenue_cents: int = 0  # the running quarter's revenue so far
    quarter_op_cents: int = 0  # and its operating result
    dividend_cents: int = 0  # per share, declared: paid at the next month end
    lapsed_seats: int = 0  # investor seats lapsed since listing (25.7)
    # Event choices that need the month's cash or a draw, done at the next phase 7:
    # "activist_seat", "activist_buyback", "activist_fight" (25.4)
    pending: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Guidance:
    """One quarter's guidance and, once reported, its result (25.4). `quarter_turn` is the
    quarter's first month."""

    company_id: int
    quarter_turn: int
    revenue_cents: int
    margin_bp: int  # operating margin, basis points
    consensus_revenue_cents: int
    consensus_margin_bp: int
    by_player: bool
    actual_revenue_cents: int | None = None
    actual_margin_bp: int | None = None
    result: Result | None = None
    price_before_cents: int | None = None
    price_after_cents: int | None = None

    @property
    def reported(self) -> bool:
        return self.result is not None


@dataclass(frozen=True, slots=True)
class ShareMonth:
    """A listed company's month end (25.3): the chart's data. `mark` notes a listing, a
    beat or a miss that month."""

    company_id: int
    turn: int
    price_cents: int
    shares: int
    mark: str = ""

    @property
    def market_cap_cents(self) -> int:
        return self.price_cents * self.shares


@dataclass(frozen=True, slots=True)
class Ceo:
    """An appointed CEO (25.6); the founder is Chair while one serves."""

    id: int
    company_id: int
    person_id: int
    since_turn: int
    scopes: tuple[str, ...]  # the authority the Chair allows (config.CEO_SCOPES)
    ended_turn: int | None = None
    end_reason: str | None = None  # "replaced" (the board), "dismissed" (the Chair), "left"
    low_months: int = 0  # months of board confidence below ceo.replace.below
    # The player's last prices, (product_id, segment, cents): the CEO moves a price only
    # within ceo.price_band_pct of these (25.6)
    price_anchors: tuple[tuple[int, str, int], ...] = ()

    @property
    def active(self) -> bool:
        return self.ended_turn is None


@dataclass(frozen=True, slots=True)
class CeoDecision:
    """One decision a CEO took (25.6). `undo` is the action kind and its fields that reverse
    it, or () when it cannot be overridden (a launch, for one)."""

    id: int
    company_id: int
    person_id: int
    turn: int
    scope: str
    text: str
    mistake: bool
    undo: tuple[tuple[str, int | str], ...] = ()
    overridden_turn: int | None = None
