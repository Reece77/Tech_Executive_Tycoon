from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ErrorOut(BaseModel):
    """Stable error body for every 4xx response."""

    code: str
    message: str
    event_id: int | None = None  # critical_event_open: the event blocking Continue (M6)
    retryable: bool | None = Field(
        default=None,
        description="True: refused before anything was written, so the same request may be "
        "sent again (save_busy; M8r). Absent: do not retry automatically.",
    )


class BreakdownItemOut(BaseModel):
    """One driver of a number (M7b tooltips)."""

    label: str
    amount: float
    unit: Literal["cents", "count", "points", "percent", "months"]


class BreakdownOut(BaseModel):
    """Why a number is what it is: its drivers and an optional note, built by the backend;
    the front end only displays them (M7b; spec 13)."""

    items: list[BreakdownItemOut]
    note: str | None = None


class OverviewBreakdownsOut(BaseModel):
    """The top bar's and Overview's driver tooltips, fetched when one first opens."""

    cash: BreakdownOut = Field(description="Last month's change in cash by kind")
    runway: BreakdownOut = Field(description="Cash over this month's projected net burn")
    mrr: BreakdownOut = Field(description="Last month's revenue by product")
    arr: BreakdownOut = Field(description="12 x MRR by product")
    burn: BreakdownOut = Field(description="Last month's fall in cash by cost line")
    headcount: BreakdownOut = Field(description="Staff by org unit")
    avg_morale: BreakdownOut = Field(description="The company-wide average of the morale terms")


class GlossaryOut(BaseModel):
    """Definitions of every KPI and column (backend/data/glossary.yaml; M7b)."""

    terms: dict[str, str]
