"""Frozen currency records (docs/formulas.md 64.4, ADR-0025). GameState holds one `FxState`: the
translation marks (each regional price's local value fixed at the month it was set), currency
forwards, hedging programmes, the indexes' seeded walk after `fx.applies_from` and the player's
translation months. Persisted in `fx_record` (migration 0068_m54).

Hidden values: the walk's future months do not exist until they come (each month's step is drawn
then, stream `fx` (region index, month)); the API shows only indexes up to this month."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PriceMark:
    """A price's local value is fixed at the month it was set (ADR-0025 point 3): the segment of
    `product_id` in `region` was last priced `price_cents` (US cents then) in month `turn`."""

    product_id: int
    region: str
    segment: str
    price_cents: int
    turn: int


@dataclass(frozen=True, slots=True)
class FxHedge:
    """A currency forward (ADR-0025 point 5): `notional_cents` of a region's money (as US cents at
    the spot index when bought) delivered at `settle_turn` at the forward index. Index values are
    x INDEX_SCALE. `value_cents` is its fair value as last booked (positive an asset)."""

    id: int
    company_id: int
    region: str
    notional_cents: int
    turn: int
    settle_turn: int
    spot_index: int
    forward_index: int
    status: str = "open"  # open, settled
    value_cents: int = 0
    settled_cents: int = 0
    programme: bool = False  # bought by a hedging programme (the player's or the CFO's)


@dataclass(frozen=True, slots=True)
class HedgeProgramme:
    """A rolling hedge: each month a forward on `share` of the month's net revenue in each foreign
    region, `term_months` ahead (the CFO delegate runs one within fx.cfo_limit_share, 40)."""

    company_id: int
    share: float
    term_months: int
    by_cfo: bool = False


@dataclass(frozen=True, slots=True)
class FxMonth:
    """A company's foreign money in a region this month, in US cents: revenue and local costs as
    booked (translated) and what they would have been at the indexes they were set at."""

    turn: int
    company_id: int
    region: str
    revenue_cents: int
    cost_cents: int
    untranslated_revenue_cents: int
    untranslated_cost_cents: int
    hedge_cents: int  # hedges settled this month (gain positive)


@dataclass(frozen=True, slots=True)
class FxState:
    marks: tuple[PriceMark, ...] = ()
    hedges: tuple[FxHedge, ...] = ()
    programmes: tuple[HedgeProgramme, ...] = ()
    # region -> index x INDEX_SCALE month by month from fx.applies_from (drawn as months come)
    walk: tuple[tuple[str, tuple[int, ...]], ...] = ()
    months: tuple[FxMonth, ...] = ()

    def walk_of(self, region: str) -> tuple[int, ...]:
        return next((w for r, w in self.walk if r == region), ())

    def programme(self, company_id: int) -> HedgeProgramme | None:
        return next((p for p in self.programmes if p.company_id == company_id), None)

    def open_hedges(self, company_id: int) -> tuple[FxHedge, ...]:
        return tuple(h for h in self.hedges if h.company_id == company_id and h.status == "open")

    def next_hedge_id(self) -> int:
        return max((h.id for h in self.hedges), default=0) + 1
