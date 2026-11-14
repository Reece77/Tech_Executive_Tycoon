"""Response and request schemas for the Market screen's Commodities tab and the product cost
breakdown (M17, formulas.md 33).

Only history and the current month: prices, indexes and allocation up to the month the player
is in, never a seeded month ahead or a shock's drawn length (33.6 target 1). Deals, suppliers
(data, not hidden) and the company's own use.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class PricePointOut(BaseModel):
    turn: int
    label: str
    price: float = Field(description="In the good's unit")
    index: float = Field(description="Price / the 2010-2019 mean (1.0 = normal)")
    allocation: float = Field(description="Share spot buyers get (1.0 outside shortages)")


class CommodityOut(BaseModel):
    good: str
    label: str
    unit: str = Field(description="The price unit, e.g. $/t or US cents/lb")
    volume_unit: str = Field(description="What contracts and offtakes buy: t, kg or lot")
    price: float = Field(description="This month's price, in `unit`")
    index: float
    change_12m: float = Field(description="Index against twelve months before, as a fraction")
    allocation: float
    long_run: float = Field(description="The 2015-2025 median price, in `unit`")
    top_country: str
    top_share: float = Field(description="Its largest country's share of production or refining")
    note: str = Field(description="Shortage, a running shock, or full allocation, in words")
    use_month: float = Field(description="Your company's use last month, in volume units")
    peak_price: float = Field(description="The highest price in the history shown")
    peak_label: str = Field(description="Its month")
    history: list[PricePointOut]


class PowerOut(BaseModel):
    region: str
    label: str
    index: float = Field(description="Industrial power against North America (1.0)")
    history: list[PricePointOut]


class CommodityDealOut(BaseModel):
    supplier_country_label: str | None = None  # M23a: where the supplier sits
    deal_id: int
    kind: str = Field(description="contract or offtake")
    good: str
    good_label: str
    supplier: str | None
    supplier_name: str | None
    supplier_company_id: int | None = Field(
        default=None, description="M28: the supplier's company page (from 2026)"
    )
    signed: str
    ends: str
    volume_year: float
    signing_price: float
    floor: float
    ceiling: float
    price_now: float = Field(description="What it pays at this month's spot")
    prepaid_cents: int
    prepaid_left_cents: int
    status: str = Field(description="active, ended or breached")
    taken: float
    last_taken: float
    hedge_cents: int = Field(description="Cost of goods saved against spot so far")
    charged_cents: int = Field(description="Take-or-pay so far")


class SupplierGoodOut(BaseModel):
    good: str
    label: str
    share: float = Field(description="Rough share of world production or refining")
    open: bool = Field(description="It signs offtakes for this good this month")


class SupplierOut(BaseModel):
    key: str
    name: str
    region: str
    region_label: str
    country: str | None = Field(default=None, description="M23a: where the supplier sits")
    country_label: str | None = None
    listing: str
    company_id: int | None = Field(default=None, description="M28: its company page (from 2026)")
    reliability: float = Field(description="Chance it keeps delivering through a severe shock")
    goods: list[SupplierGoodOut]
    revenue_2010_usd_m: float | None
    revenue_note: str | None = Field(description="The 2010 revenue as printed, and its check")


class CommoditiesOut(BaseModel):
    goods: list[CommodityOut]
    power: list[PowerOut]
    deals: list[CommodityDealOut]
    suppliers: list[SupplierOut]
    collar: float = Field(description="Offtake floor and ceiling: signing price -/+ this share")
    prepay_max: float
    offtake_years: list[int] = Field(description="[min, max]")
    contract_months: list[int] = Field(description="[min, max]")
    offtake_take_or_pay: float
    contract_take_or_pay: float
    offtake_energy: int
    contract_energy: int


class CommodityContractIn(BaseModel):
    good: str
    months: int
    volume_year: float = Field(gt=0)


class OfftakeIn(BaseModel):
    good: str
    supplier: str
    years: int
    volume_year: float = Field(gt=0)
    prepay: float = Field(default=0.0, ge=0, le=1)


class DealQuoteOut(BaseModel):
    good: str
    supplier: str | None
    months: int
    volume_year: float
    price: float
    floor: float
    ceiling: float
    year_value_cents: int
    prepaid_cents: int


class CommoditiesActionOut(BaseModel):
    commodities: CommoditiesOut
    energy: EnergyOut
    unread_inbox: int


class CommodityCostLineOut(BaseModel):
    """One commodity's part of a unit's cost (33.2): the product cost breakdown."""

    good: str
    label: str
    weight: float = Field(description="Its weight in the product's commodity mix")
    index: float = Field(description="Its price index this month (1.0 = normal)")
    spot_cents: float = Field(description="Its cost in one unit at spot")
    hedged_share: float = Field(description="Share of your use covered by contracts and offtakes")
    deal_cents: float = Field(description="Its cost in one unit after your deals")


# --- M23c: the planning view -------------------------------------------------------------


class CommodityPlanDriverOut(BaseModel):
    product_id: int
    name: str
    need_month: float = Field(description="Volume units a month this product uses")
    share: float = Field(description="Of the commodity's monthly need")


class CommodityPlanMonthOut(BaseModel):
    turn: int
    label: str
    required: float = Field(description="The month's need at this month's production")
    deals: float = Field(description="Running contracts' and offtakes' volume that month")
    own: float = Field(description="The group's own supply at this month's rate")
    gap: float = Field(description="Need not covered by deals or own supply")


class CommodityPlanOut(BaseModel):
    good: str
    label: str
    volume_unit: str
    need_month: float = Field(description="This month's use, volume units")
    need_12m: float = Field(description="The next 12 months at this month's production")
    deals_12m: float = Field(description="What running contracts and offtakes deliver in them")
    own_12m: float = Field(description="The group's own supply to the group, at this rate")
    mines_12m: float = Field(description="The group's mines' output at the latest month's rate")
    cover: float | None = Field(description="(deals + own supply) / need, at most 1")
    gap_12m: float
    drivers: list[CommodityPlanDriverOut] = Field(description="The products that use it")
    deals_ending: list[str] = Field(description="Deals that end inside the 12 months")
    months: list[CommodityPlanMonthOut]


class CommodityPlansOut(BaseModel):
    turn_label: str
    months: int
    plans: list[CommodityPlanOut]
