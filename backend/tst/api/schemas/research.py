"""Response and request schemas for the R&D tree (M11, formulas.md 21.7).

Only what 21.7 allows: the player's levels as baseline plus lead, its projects with
researchers, estimated output and progress (from displayed skill ranges), budget and months
to the next era threshold; licences; rivals' leads as ranges; the era timeline with
thresholds and no historical dates past the present.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.people import EnergyOut


class DomainOut(BaseModel):
    key: str
    label: str
    baseline: float = Field(description="The world's level, free to everyone (D)")
    lead: float = Field(description="Your lead beyond the baseline (R)")
    level: float = Field(description="baseline + lead")
    feeds: list[str] = Field(description="Market labels this domain counts for")
    next_era: str | None = Field(description="The domain's next era, if any")
    next_threshold: float | None = Field(description="The level that brings it early")


class CategoryTechOut(BaseModel):
    category: str
    label: str
    lead: float = Field(description="Your research lead for the market (weighted domains)")
    cap_lift_pct: float = Field(description="Percent added to what product teams can reach")
    feature_lift_pct: float = Field(description="Percent added to feature progress")
    first_mover: bool = Field(description="A first-mover head start is running")


class ProjectOut(BaseModel):
    project_id: int
    unit_id: int
    unit_name: str
    domain: str
    domain_label: str
    researchers: int
    budget_cents: int | None = Field(description="Monthly budget; null = full funding")
    needed_cents: int = Field(description="Full funding this month")
    funded_pct: float
    gain_per_month: float = Field(description="Estimated lead gained a month, before decay")
    last_month_gain: float | None = Field(description="Lead gained last month")
    next_era: str | None
    months_to_era: int | None = Field(description="At this pace; null if not within 10 years")
    months_before_history: int | None = Field(
        description="How early that would be; null if the era is not yet visible by date"
    )
    last_event: str | None = Field(description="'Breakthrough, June 2016' or a dead end")
    started: str


class UnitChoiceOut(BaseModel):
    unit_id: int
    name: str
    researchers: int = Field(description="Members in builder roles who would research")


class RivalLeadOut(BaseModel):
    company_id: int
    name: str
    is_startup: bool
    founded: str | None = Field(description="A startup's founding month")
    low: int = Field(description="Lead range, low")
    high: int = Field(description="Lead range, high")
    licensed: bool = Field(description="You have a licence with them (narrower range)")
    can_license_in: bool
    why_not: str | None = Field(description="Why licensing in from them is not possible")
    max_points: int = Field(description="Points you can safely ask for (from the range)")
    can_license_out: bool
    max_out_points: int = Field(description="Points you can grant them (from the range)")


class DomainRivalsOut(BaseModel):
    domain: str
    domain_label: str
    rivals: list[RivalLeadOut]


class LicenseOut(BaseModel):
    license_id: int
    direction: Literal["in", "out"]
    company: str
    domain_label: str
    points: float
    price_cents: int
    royalty_pct: float
    royalty_months_left: int
    signed: str


class EraOut(BaseModel):
    key: str
    label: str
    domain_label: str
    status: Literal["arrived", "next", "later"]
    arrived: str | None = Field(description="Month it arrived")
    on_schedule: bool | None
    months_early: int | None
    caused_by: str | None = Field(description="Company that caused it early ('You' for yours)")
    threshold: float
    your_level: float
    accelerates: str
    first_mover_reward: str
    expected: str | None = Field(
        default=None,
        description="A future era's public window until it arrives, e.g. 'expected 2026-2028'"
        " (M12b, 26.4); its scheduled month is never shown",
    )


class ResearchOut(BaseModel):
    domains: list[DomainOut]
    categories: list[CategoryTechOut]
    projects: list[ProjectOut]
    units: list[UnitChoiceOut] = Field(description="Units free to start a project")
    rivals: list[DomainRivalsOut]
    licenses: list[LicenseOut]
    eras: list[EraOut]
    decay_pct: float = Field(description="Percent of every lead lost each month")
    price_per_point_cents: int = Field(description="Licensing in, a point, at your ARR")
    margin: float = Field(description="Points a licensor keeps ahead of the licensee")
    royalty_pct: float
    royalty_months: int
    start_energy: int
    stop_energy: int
    license_energy: int


class ResearchActionOut(BaseModel):
    research: ResearchOut
    energy: EnergyOut
    unread_inbox: int


class StartProjectIn(BaseModel):
    unit_id: int
    domain: str
    budget_cents: int | None = Field(default=None, ge=0, description="Null = full funding")


class ProjectBudgetIn(BaseModel):
    budget_cents: int | None = Field(default=None, ge=0, description="Null = full funding")


class LicenseIn(BaseModel):
    company_id: int = Field(description="The rival licensing to you, or from you")
    domain: str
    points: float = Field(gt=0)
