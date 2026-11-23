"""Conglomerate view schemas (M43 sub-task 2): the group's books by industry, by company and by
year, where capital went, the capital-allocation panel and the January letters. Every figure is
the player's own ledger's (displayed values only, never a hidden one); read-only, no energy."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FiguresOut(BaseModel):
    revenue_cents: int = Field(description="External revenue (intercompany left out)")
    gross_margin: float | None = Field(
        description="Gross profit over revenue; null without revenue"
    )
    operating_profit_cents: int
    operating_margin: float | None
    capital_employed_cents: int = Field(description="At the year end (or now, this year)")
    return_on_capital: float | None = Field(
        description="Operating profit over capital employed; null when capital employed <= 0"
    )


class IndustryYearOut(BaseModel):
    year: int
    months: int = Field(description="Months of the year played (12 but this year)")
    revenue_cents: int
    operating_profit_cents: int
    capital_employed_cents: int
    capex_cents: int


class IndustryOut(BaseModel):
    key: str
    label: str
    figures: FiguresOut
    share_of_revenue: float = Field(description="Of the group's revenue in the year shown")
    growth: float | None = Field(description="Revenue growth on the year before; null if new")
    risk: str = Field(description="low | moderate | high | new: the spread of yearly growth")
    trend: list[IndustryYearOut]


class CompanyFiguresOut(BaseModel):
    company_id: int
    name: str
    role: str = Field(description="holding | operating | subsidiary")
    industries: list[str] = Field(description="Labels of the industries it had revenue in")
    figures: FiguresOut
    intercompany_cents: int = Field(description="Its sales to other group companies")


class CapexOut(BaseModel):
    key: str = Field(description="An industry key, or corporate")
    label: str
    cents: int


class CapitalYearOut(BaseModel):
    year: int
    capex: list[CapexOut]
    acquisitions_cents: int = Field(description="Acquisitions, stakes and goodwill")
    returned_cents: int = Field(description="Dividends and buybacks")


class PlannedOut(BaseModel):
    key: str
    label: str
    committed_cents: int = Field(description="Builds under way: capex still to pay")
    limits_cents: int = Field(description="Subsidiaries' yearly capex limits (31.4)")


class AllocationOut(BaseModel):
    key: str
    label: str
    return_on_capital: float | None
    growth: float | None
    risk: str
    planned: PlannedOut


class WaitingProposalOut(BaseModel):
    kind: str = Field(description="pitch | group_pitch | proposal")
    company: str
    who: str
    title: str
    amount_cents: int | None = Field(description="What it would cost, where it says")
    turn: int


class LetterOut(BaseModel):
    year: int = Field(description="The year the letter covers")
    turn: int = Field(description="The January it was written")
    text: str
    source: str = Field(description="claude | mock | template")


class ConglomerateOut(BaseModel):
    year: int = Field(description="The year shown: the last full year, or this year to date")
    months: int
    group: FiguresOut
    industries: list[IndustryOut]
    corporate: FiguresOut | None = Field(
        description="Lines of companies with no industry revenue (a holding company's office)"
    )
    companies: list[CompanyFiguresOut]
    capital: list[CapitalYearOut]
    allocation: list[AllocationOut]
    proposals: list[WaitingProposalOut]
    letters: list[LetterOut]
