"""The Platforms API (M31, docs/formulas.md 44.10): platforms' public facts. Users and fee
schedules as published; the player's own platform exactly; rivals' developer shares as ranges.
Never a gatekeeper's review chance or draw, a rival's plan, or a seeded future rule."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class RegulatedPathOut(BaseModel):
    label: str = Field(description="The country or the alternative store")
    share: float = Field(description="Share of the region's store sales on this path")
    rate: float


class FeeScheduleOut(BaseModel):
    standard: float
    small_rate: float | None = Field(description="Sellers under the threshold pay this")
    small_threshold_cents: int | None
    subscription_rate: float | None
    subscription_after_year: bool
    regulated: list[RegulatedPathOut]


class PlatformRegionOut(BaseModel):
    region: str
    label: str
    users: float = Field(description="Share of the region's device users (0-1)")
    developer_share: float | None = Field(description="Exact for the player's own platforms")
    developer_range: list[float] = Field(description="A range for rivals' platforms")
    catalogue_index: float = Field(description="The catalogue against the region's leader (100)")
    goodwill: float | None = Field(description="Developers' goodwill: own platforms only")
    fees: FeeScheduleOut
    rules: list[str] = Field(description="Platform rules in force there, in words")
    side_loading: float = Field(description="Share of the region where other stores may serve it")
    rival_stores: list[str]


class PlatformSettingsOut(BaseModel):
    fee: float
    strictness: Literal["lenient", "standard", "strict"]
    self_pref: Literal["off", "mild", "strong"]
    anti_steering: bool
    side_loading: bool
    licence_cents: int | None


class PlatformOut(BaseModel):
    platform_id: int
    key: str
    name: str
    store: str
    kind: Literal["device", "developer"]
    owner_label: str
    owner_company_id: int | None
    own: bool
    historical: bool
    launched_label: str | None
    ended_label: str | None
    open_source: bool
    licensable: bool
    product_id: int | None
    app_count_thousands: float | None = Field(description="platforms.yaml's latest count, if any")
    regions: list[PlatformRegionOut]
    settings: PlatformSettingsOut | None


class DeviceLineOut(BaseModel):
    product_id: int
    name: str
    platform_id: int
    platform_name: str
    previous_name: str | None
    previous_share: float = Field(description="Customers still on the old platform")
    catalogue_points: dict[str, float] = Field(description="Feature points by region (from 2026)")


class ListingOut(BaseModel):
    platform_id: int
    platform_name: str
    region: str
    region_label: str
    status: Literal["listed", "removed", "appealing", "regulators"]
    since_label: str
    answer_label: str | None


class AppFeeOut(BaseModel):
    platform_id: int
    platform_name: str
    region: str
    region_label: str
    cents: int


class AppProductOut(BaseModel):
    product_id: int
    name: str
    category: str
    steering: bool
    fees: list[AppFeeOut] = Field(description="This month's fees by platform and region")
    fees_total_cents: int
    listings: list[ListingOut] = Field(description="Removals and appeals; others are listed")
    recent_actions: list[str] = Field(description="Gatekeepers' actions in the last year")


class StandardOut(BaseModel):
    standard_id: int
    label: str
    category: str
    formats: list[str]
    adoption: float = Field(description="Share of new products on the first format")
    winner: str | None
    tipped_label: str | None
    historical: bool
    yours_on_loser: list[int] = Field(description="The group's products on the losing format")


class PlatformsOut(BaseModel):
    started: bool = Field(description="Computed shares and effects run from January 2026")
    fees_posting: bool = Field(description="Platform fees post from platforms.fees_from")
    platforms: list[PlatformOut]
    device_lines: list[DeviceLineOut]
    apps: list[AppProductOut]
    standards: list[StandardOut]
    open_products: list[int]
    developer_candidates: list[int] = Field(description="Live products that can found one")
    appeal_odds: list[float] = Field(description="The range an appeal's odds lie in")
    own_fee_range: list[float]


class DevicePlatformIn(BaseModel):
    product_id: int
    platform_id: int


class PlatformRulesIn(BaseModel):
    platform_id: int
    fee: float | None = None
    strictness: Literal["lenient", "standard", "strict"] | None = None
    self_pref: Literal["off", "mild", "strong"] | None = None
    anti_steering: bool | None = None
    side_loading: bool | None = None
    licence_cents: int | None = Field(default=None, ge=0)
    stop_licensing: bool = False


class ProductIn(BaseModel):
    product_id: int


class OpenSourceIn(BaseModel):
    product_id: int
    open: bool = True


class SteeringIn(BaseModel):
    product_id: int
    on: bool = True


class AdoptIn(BaseModel):
    product_id: int
    standard_id: int


class PlatformsActionOut(BaseModel):
    platforms: PlatformsOut
    energy: EnergyOut
    unread_inbox: int
