"""Response and request schemas for the Infrastructure screen (M12a, formulas.md 22.6).

Only what 22.6 allows: data centres' capacity, use (own and sold), reliability, staff
coverage, cost per used CU against spot, book value and build progress; the component indexes
and allocation with their history, never a future month; contracts; Cloud hosting customers
and outages. Never a person's skill (reliability is shown, not the mean skill behind it).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class IndexPointOut(BaseModel):
    turn: int
    label: str = Field(description="Mon YYYY")
    index: float
    allocation: float


class ComponentOut(BaseModel):
    good: str
    label: str
    index: float = Field(description="This month's index (January 2010 = 1.0)")
    change_12m: float = Field(description="Change over the last 12 months (fraction)")
    allocation: float = Field(description="Share of a build delivered on time (1.0 = full)")
    note: str = Field(description="One line of context: a shortage, a shock, or full supply")
    history: list[IndexPointOut] = Field(description="Past months up to this one, oldest first")


class SpotOut(BaseModel):
    good: str
    label: str
    cents_per_unit: int = Field(description="A CU a month on spot")
    index: float = Field(description="1.0 for general; the AI compute index for GPU")


class FacilityOut(BaseModel):
    facility_id: int
    name: str
    kind: str
    kind_label: str
    region: str
    region_label: str
    unit: str = Field(description="Capacity unit, e.g. CU")
    status: str = Field(description="building, live or closed")
    since: str = Field(description="Ordered (building) or live since (Mon YYYY)")
    capacity: int
    live_capacity: int
    own_use: float = Field(description="Units your own products use this month")
    sold_use: float = Field(description="Units sold as Cloud hosting this month")
    free: float
    utilization: float = Field(description="Used / live capacity (0-1)")
    reliability: float | None = Field(description="0-100; null while building")
    staff: int
    staff_needed: int
    coverage: float
    unit_id: int | None = Field(description="The unit that staffs it")
    unit_name: str | None
    monthly_cost_cents: int = Field(description="Depreciation plus operating cost a month")
    cost_per_used_cents: int | None = Field(description="Monthly cost / units used; null if none")
    spot_cents: int = Field(description="Spot price of a unit of its output")
    book_value_cents: int
    capex_cents: int
    capex_paid_cents: int
    build_progress: float | None = Field(description="Share of the build months done; null live")
    ready: str = Field(description="Mon YYYY it goes (or went) live")
    late_units: int = Field(description="Units arriving late from a shortage")
    late_ready: str | None = Field(description="Mon YYYY the late units arrive")
    sale_value_cents: int = Field(description="What selling it now brings")


class ContractOut(BaseModel):
    contract_id: int
    good: str
    good_label: str
    index: float
    signed: str
    ends: str
    volume: int
    used: int
    status: str
    take_or_pay_cents: int = Field(description="What the unused volume would cost at the end")
    settled_cents: int


class CloudSegmentOut(BaseModel):
    segment: str
    label: str
    customers: float
    units: float = Field(description="CU these customers buy")
    price_cents: int | None = Field(description="Your price per customer a month")
    price_per_unit_cents: int | None = Field(description="Your price per CU a month")


class OutageOut(BaseModel):
    turn: int
    label: str
    facility: str
    customers_lost: float


class CloudOut(BaseModel):
    product_id: int | None = Field(description="Your Cloud hosting product; null if not selling")
    product_name: str | None
    selling: bool
    can_start: bool = Field(description="True when you own a data centre and do not sell yet")
    segments: list[CloudSegmentOut]
    customers: float
    units_sold: float
    revenue_cents: int = Field(description="This month's revenue at current customers")
    spare_units: float = Field(description="General-CU equivalents still free for customers")
    price_per_unit_cents: int | None = Field(description="Average price per CU you charge")
    leader_name: str | None = Field(description="The market leader (most customers)")
    leader_price_per_unit_cents: int | None
    outages_12m: int
    outages: list[OutageOut]


class KindOut(BaseModel):
    key: str
    label: str
    unit: str
    input_good: str
    build_months: int
    life_months: int
    opex_per_unit_cents: int
    capex_per_unit_cents: int = Field(description="At this month's index")


class InfrastructureOut(BaseModel):
    turn_label: str
    components: list[ComponentOut]
    spot: list[SpotOut]
    facilities: list[FacilityOut]
    live_units: int
    building_units: int
    contracts: list[ContractOut]
    cloud: CloudOut
    kinds: list[KindOut]
    sizes: list[int]
    regions: list[RegionOptionOut]
    build_energy: int
    sell_energy: int
    contract_energy: int
    staff_energy: int
    contract_months: list[int] = Field(description="[shortest, longest]")
    take_or_pay: float
    sale_share: float
    break_even_utilization: float = Field(description="Use at which a general CU costs spot")


class RegionOptionOut(BaseModel):
    key: str
    label: str
    is_home: bool


class BuildPreviewOut(BaseModel):
    kind: str
    region: str
    capacity: int
    index: float
    capex_cents: int
    monthly_capex_cents: int
    build_months: int
    ready: str
    allocation: float
    on_time: int
    late: int
    late_months: int
    staff_needed: int
    contract_id: int | None
    contracted: int
    monthly_cost_full_cents: int = Field(description="Depreciation and operating cost at full use")
    cost_per_unit_full_cents: int
    spot_cents: int
    energy: int
    can_afford: bool = Field(description="Cash covers the first capex payment")


class BuildIn(BaseModel):
    kind: str
    region: str
    capacity: int
    contract_id: int | None = None


class ContractIn(BaseModel):
    good: str
    months: int
    volume: int


class StaffIn(BaseModel):
    unit_id: int | None


class InfrastructureActionOut(BaseModel):
    infrastructure: InfrastructureOut
    energy: EnergyOut
    unread_inbox: int


InfrastructureOut.model_rebuild()
