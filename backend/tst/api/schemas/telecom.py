"""The Telecom screen (M53, docs/formulas.md 62): subscribers, coverage by region and generation,
capacity and quality, spectrum holdings, equipment by vendor, auctions and bans. Public figures
only (62.5): never a rival's auction value, a seeded auction's or ban's month before it is
announced, or 6G's month before it comes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class NetworkGenerationOut(BaseModel):
    key: str
    label: str
    open: bool = Field(description="Commercial somewhere in the world now")
    first: str | None = Field(default=None, description="Its first commercial month, once open")
    feature_points: float


class RegionNetworkOut(BaseModel):
    region: str
    label: str
    mobile_market: float = Field(description="Mobile subscriptions in the region (game scale)")
    fixed_market: float
    mobile_subscribers: float = Field(description="Yours, every mobile line")
    fixed_subscribers: float
    wholesale_contracts: float
    sites: int
    coverage: float = Field(description="Population your network covers (0-1)")
    coverage_by_generation: dict[str, float]
    best_generation: str | None
    capacity_gb: float = Field(description="Your network's GB a month")
    demand_gb: float = Field(description="Your mobile subscribers' traffic, GB a month")
    quality: float = Field(description="Capacity over demand, at most 1")
    homes_passed: float
    households: float
    licensed: dict[str, float] = Field(description="Band -> licensed share of the region")
    mhz: dict[str, float] = Field(description="Band -> population-weighted MHz you hold")
    neutrality: bool = Field(description="A net-neutrality rule is in force in the region")
    rivals: list[OperatorShareOut]


class OperatorShareOut(BaseModel):
    name: str
    subscribers: float
    share: float


class RadioOut(BaseModel):
    facility_id: int
    region: str
    generation: str
    vendor: str
    vendor_label: str
    overlay: bool
    sites: int
    live_sites: int
    status: str
    ready: str
    dark: int
    replaced: int
    owed: int = Field(description="Sites its bans make it replace by now")
    at_risk: int = Field(description="Sites announced bans will make it replace")
    replacing: int | None = Field(
        default=None, description="The record a rip-and-replace order replaces"
    )
    capex_cents: int
    capex_paid_cents: int


class FibreOut(BaseModel):
    facility_id: int
    region: str
    homes_thousands: int
    status: str
    ready: str
    capex_cents: int


class CableOut(BaseModel):
    facility_id: int
    name: str
    regions: list[str]
    km: float
    tbps: int
    status: str
    ready: str
    capex_cents: int


class SpectrumLicenceOut(BaseModel):
    id: int
    region: str
    area: str
    area_label: str
    band: str
    mhz: float
    paid_cents: int
    book_cents: int
    since: str
    expires: str
    obligation: float
    obligation_due: str | None
    status: str
    fines: int


class AwardOut(BaseModel):
    bidder: str
    blocks: int
    paid_cents: int
    yours: bool


class AuctionOut(BaseModel):
    id: int
    label: str
    region: str
    area: str
    area_label: str
    band: str
    mhz: float
    blocks: int
    reserve_cents: int = Field(description="A block")
    month: str
    term_years: int
    obligation: float
    obligation_years: int
    status: Literal["announced", "closed"]
    biddable: bool
    my_blocks: int
    my_limit_cents: int
    rounds: int
    price_cents: int = Field(description="The final price a block (0 before it runs)")
    awards: list[AwardOut]


class VendorOut(BaseModel):
    key: str
    label: str
    price_mult: float
    world_share: float = Field(description="Its share of the RAN market this year (data)")
    radio_cents: dict[str, float] = Field(description="Generation -> a site's radios from it now")
    refused_in: list[str] = Field(description="Regions whose bans refuse new radios from it")


class BanOut(BaseModel):
    label: str
    vendor: str
    region: str
    area: str
    announced: str
    no_new: str
    replace_by: str | None
    scope: float


class LineOut(BaseModel):
    product_id: int
    name: str
    category: str
    zero_rating: bool
    satellite_partner: bool


class NetworkPaybackOut(BaseModel):
    region: str
    label: str
    cash_cents: int = Field(description="Cumulative cash flow since its first build")
    capex_cents: int = Field(description="Capex paid on its sites, radios, fibre and cables")
    last_year_cash_cents: int
    months_to_payback: float | None
    paid_back: str | None


class OperatorOut(BaseModel):
    name: str
    region: str
    mobile: float = Field(description="Real subscribers, millions, this year (data)")
    fixed: float
    supplier: str | None


class TelecomScreenOut(BaseModel):
    month: str
    history: bool = Field(description="Rivals follow telecom.yaml before January 2026")
    generations: list[NetworkGenerationOut]
    regions: list[RegionNetworkOut]
    radios: list[RadioOut]
    fibres: list[FibreOut]
    cables: list[CableOut]
    licences: list[SpectrumLicenceOut]
    auctions: list[AuctionOut]
    vendors: list[VendorOut]
    bans: list[BanOut]
    lines: list[LineOut]
    payback: list[NetworkPaybackOut]
    operators: list[OperatorOut]
    site_civil_cents: float = Field(description="A new site's mast, power and backhaul now")
    fibre_home_cents: float = Field(description="Fibre a home passed now")
    cable_km_cents: float = Field(description="A subsea cable a km now")
    has_own_equipment: bool
    sizes: dict[str, list[int]] = Field(description="Facility kind -> the sizes it comes in")


class TelecomActionOut(BaseModel):
    telecom: TelecomScreenOut
    energy: EnergyOut
    unread_inbox: int


class TowersIn(BaseModel):
    region: str
    sites: int
    generation: str
    vendor: str
    city: str | None = None


class RadiosIn(BaseModel):
    region: str
    sites: int
    generation: str
    vendor: str


class FibreIn(BaseModel):
    region: str
    homes: int = Field(description="Thousands of homes passed")
    city: str | None = None


class CableIn(BaseModel):
    name: str
    regions: list[str]
    km: float
    tbps: int


class SpectrumBidIn(BaseModel):
    blocks: int
    limit_cents: int = Field(description="The most you pay a block")


class ReplaceRadiosIn(BaseModel):
    vendor: str
    sites: int


class LineSettingIn(BaseModel):
    zero_rating: bool = False
    satellite_partner: bool = False


RegionNetworkOut.model_rebuild()
