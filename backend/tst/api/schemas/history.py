"""History responses (docs/formulas.md 17.2; M7b). Shown values only (ADR-0007)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HistoryRowOut(BaseModel):
    key: str = Field(description="Unique per row: event-N, decision-N, inbox-N or month-N")
    kind: Literal["entry", "month"] = Field(description="month: a dimmed month summary line")
    turn: int
    date_label: str
    category: str | None = Field(description="people | products | finance | rivals | events")
    title: str
    detail: str | None = None
    source: str | None = Field(default=None, description="player | delegate | default")
    actor: str | None = Field(
        default=None, description='"You", the delegate\'s name, or "Default (at Continue)"'
    )
    person_id: int | None = None
    person_name: str | None = None
    product_id: int | None = None
    product_name: str | None = None
    event_id: int | None = None


class NamedOut(BaseModel):
    id: int
    name: str


class TimelineOut(BaseModel):
    total: int = Field(description="Rows matching the filters, before paging")
    offset: int
    rows: list[HistoryRowOut] = Field(description="Newest first")
    years: list[int] = Field(description="Years with history, for the year filter")
    people: list[NamedOut] = Field(description="People named in the history, for the filter")
    products: list[NamedOut]


class KpiPointOut(BaseModel):
    turn: int
    date_label: str
    cash_cents: int | None
    monthly_burn_cents: int | None
    payroll_cents: int | None
    headcount: int | None
    avg_morale: float | None
    mrr_cents: int | None
    arr_cents: int | None
    founder_bp: int | None
    board_confidence: float | None


class ProductPointOut(BaseModel):
    turn: int
    date_label: str
    mrr_cents: int = Field(description="Revenue that month, every segment")
    customers: int


class ProductSeriesOut(BaseModel):
    product_id: int
    name: str
    points: list[ProductPointOut]


class ChartsOut(BaseModel):
    kpis: list[KpiPointOut] = Field(description="Every month-end snapshot, oldest first")
    products: list[ProductSeriesOut]


class StoryStepOut(BaseModel):
    turn: int
    date_label: str
    title: str
    choice: str | None
    by: str | None = Field(description='"You" or "Default (at Continue)"; null while open')
    event_id: int


class StorylineHistoryOut(BaseModel):
    storyline_id: int
    title: str
    status: str
    started_turn: int
    started_label: str
    ended_label: str | None
    summary: str
    steps: list[StoryStepOut]


class PeakOut(BaseModel):
    value: int
    turn: int
    date_label: str


class BiggestRoundOut(BaseModel):
    series: str
    amount_cents: int
    lead: str | None
    turn: int
    date_label: str


class FirstOut(BaseModel):
    label: str
    turn: int | None = Field(description="Null: not yet")
    date_label: str | None
    detail: str | None


class PersonRecordOut(BaseModel):
    person_id: int
    name: str
    role: str
    current: bool = Field(description="Still on the staff")
    months: int = Field(description="Tenure in months")
    value: float = Field(
        description="Longest serving: months; best hires: the rise in shown rating; "
        "departures: the shown rating at departure"
    )
    detail: str | None = Field(description="Best hires: from → to; departures: the reason")


class ProductRecordOut(BaseModel):
    product_id: int
    name: str
    value: float = Field(description="Peak MRR in cents, or the highest quality shown")


class RivalOutlastedOut(BaseModel):
    name: str
    turn: int
    date_label: str
    market: str


class HallOfFameOut(BaseModel):
    """The records of 17.2. Ratings are shown ratings: the midpoint of the ranges you see."""

    peak_arr: PeakOut | None
    peak_headcount: PeakOut | None
    biggest_round: BiggestRoundOut | None
    firsts: list[FirstOut]
    longest_serving: list[PersonRecordOut]
    best_hires: list[PersonRecordOut]
    notable_departures: list[PersonRecordOut]
    best_product_mrr: ProductRecordOut | None
    best_product_quality: ProductRecordOut | None
    rivals_outlasted: list[RivalOutlastedOut]


class VentureOut(BaseModel):
    """A company the player ran (M15b addendum 10): the current one, or one they sold."""

    company_id: int
    name: str
    current: bool
    founded_label: str
    ended_label: str | None
    buyer: str | None
    price_cents: int | None
    proceeds_cents: int | None
    score: int | None = Field(description="The company score at its sale, or the latest (30.1)")
