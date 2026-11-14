"""Onboarding and navigation responses (docs/formulas.md 42; M29). All read-only views of
what the player can see; no hidden value appears here."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SystemOut(BaseModel):
    key: str = Field(description="tst.sim.unlocks SYSTEMS key")
    label: str
    group: str = Field(
        description="company | people | products | markets | chain | finance | world | automation"
    )
    unlocked: bool = Field(description="Shown in the side bar (or Show everything is on)")
    reason: str | None = Field(description="Why it is open; null while locked")
    since_label: str | None = Field(description="When it was announced, if it was")
    item_id: int | None = Field(description="The unlock inbox item, if one was written")
    opt_in: bool = Field(description="The player may open it early (Explore for minerals)")


class UnlocksOut(BaseModel):
    show_everything: bool
    systems: list[SystemOut]
    fresh: list[str] = Field(description="Systems announced this month (for the toast)")


class StepOut(BaseModel):
    key: str
    label: str
    note: str = Field(description="The chief of staff's one line on why it matters")
    screen: str = Field(description="A systems key the step links to")
    done: bool


class GettingStartedOut(BaseModel):
    visible: bool = Field(description="First 12 months, the setting on, not dismissed")
    months_left: int
    speaker: str = Field(description="Who writes the notes: the chief of staff, or your notes")
    steps: list[StepOut]


class WhatNextItemOut(BaseModel):
    key: str
    text: str
    link_kind: str = Field(
        description="finance | event | product | person | org | recruitment | board | rival | guide"
    )
    link_id: int | None
    link_key: str | None = Field(description="The systems key of a guide link")


class WhatNextOut(BaseModel):
    items: list[WhatNextItemOut]


class PaletteEntryOut(BaseModel):
    kind: Literal["person", "product", "facility", "rival"]
    id: int
    label: str
    detail: str = Field(description="A role, a category, a place or 'rival'")
    path: str = Field(description="The route under /game/<save>/")


class PaletteOut(BaseModel):
    entries: list[PaletteEntryOut]


class OnboardingSettings(BaseModel):
    show_everything: bool
    guided_first_year: bool
    stop_on: Literal["major", "critical"] = Field(
        description="The lowest severity that stops Continue and is a holiday's default stop"
    )
    stop_for_approvals: bool = Field(
        default=True,
        description="A one-off from someone running an area stops a holiday (M27a, 40.2)",
    )
