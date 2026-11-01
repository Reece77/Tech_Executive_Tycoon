"""Response and request schemas for cities, offices and product regions (M9, formulas.md 19.7).

Only what 19.7 allows: cities' indexes and talent bonuses; offices' seats, members and cost
per head; products' regional status, prices, customers and revenue; the cross-region factor.
Never a capacity or output number (11.13).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class TalentOut(BaseModel):
    label: str = Field(description="A skill group or a skill")
    points: float = Field(description="Attribute points added to candidates' role skills")
    marks: str = Field(description="The bonus as + marks, one per half point")


class CityOut(BaseModel):
    key: str
    label: str
    region: str
    region_label: str
    salary_index: float = Field(description="Salary multiplier (San Francisco = 1.0)")
    rent_index: float = Field(description="Rent index (San Francisco = 1.0)")
    talent: list[TalentOut]
    people: int = Field(description="Your staff working in the city")
    is_hq: bool
    seat_rent_cents: int = Field(description="A leased seat's monthly rent there")
    example_rate_cents: int = Field(description="A senior software engineer's market rate there")


class UnitRefOut(BaseModel):
    unit_id: int
    name: str


class OfficeOut(BaseModel):
    office_id: int | None = Field(description="Null for flexible space in the HQ city")
    city: str
    city_label: str
    seats: int | None = Field(description="Null for flexible space (no limit)")
    people: int
    monthly_rent_cents: int = Field(description="Rent, or flexible space's cost, a month")
    cost_per_head_cents: int | None = Field(description="Null while nobody works there")
    units: list[UnitRefOut]
    crowded: bool
    crowded_morale: float | None = Field(description="Morale points when crowded")
    opened: str | None = None
    close_penalty_cents: int | None = Field(
        default=None, description="What closing the lease now costs; null for flexible space"
    )


class GeoOut(BaseModel):
    hq_city: str
    hq_label: str
    home_region: str
    home_region_label: str
    offices: list[OfficeOut] = Field(description="Flexible HQ space first, then leases by id")
    cities: list[CityOut]
    seat_sizes: list[int]
    lease_energy: int
    close_energy: int
    assign_energy: int
    close_penalty_months: int
    relocation_cents: int = Field(description="Added to a hire who moves to the search's city")


class LeaseIn(BaseModel):
    city: str
    seats: int


class LeasePreviewOut(BaseModel):
    city: str
    city_label: str
    seats: int
    monthly_rent_cents: int
    fit_out_cents: int
    example_rate_cents: int = Field(description="A senior software engineer's market rate there")
    energy: int


class UnitOfficeIn(BaseModel):
    office_id: int | None = Field(description="Null: the parent unit's office, up to the HQ")


class GeoActionOut(BaseModel):
    geo: GeoOut
    energy: EnergyOut
    unread_inbox: int


class RegionSegmentOut(BaseModel):
    segment: str
    label: str
    price_cents: int | None
    default_price_cents: int = Field(description="p_ref x the region's price index")
    customers: float
    mrr_cents: int


class ProductRegionOut(BaseModel):
    region: str
    label: str
    status: str = Field(description="home, live, localizing or not_launched")
    status_label: str = Field(description="Home, live since a month, localizing until a month")
    segments: list[RegionSegmentOut]
    customers: float
    mrr_cents: int
    local_presence: bool = Field(description="An office or enough people working there")
    sellers_here: int = Field(description="Your sellers on the product working in the region")
    sellers_neighbour: int = Field(description="Those in its sales neighbour (count half)")
    neighbour_label: str
    reach_note: str = Field(description="Reach in words, with any warning")
    addressable: int = Field(description="Addressable customers in the product's segments")
    rivals: int = Field(description="Rival products selling there in the category")
    launch_cost_cents: int | None = Field(description="Localization cost, if not launched")
    live_label: str | None = Field(description="When a launch now would go live")
    launch_problem: str | None = Field(description="Why it cannot launch there now")


class TeamRegionOut(BaseModel):
    region: str
    label: str
    builders: int


class ProductRegionsOut(BaseModel):
    product_id: int
    name: str
    regions: list[ProductRegionOut] = Field(description="Home first, then regions.yaml order")
    team: list[TeamRegionOut] = Field(description="Builders by the region they work in")
    time_zone_factor: float = Field(description="Cross-region factor on output (19.4)")
    launch_energy: int
    localize_months: int


class LaunchRegionIn(BaseModel):
    region: str


class RegionalPriceIn(BaseModel):
    segment: str
    price_cents: int


class ProductRegionsActionOut(BaseModel):
    regions: ProductRegionsOut
    energy: EnergyOut
    unread_inbox: int
