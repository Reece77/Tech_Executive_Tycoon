"""Explain and Ask why (M25 section 1): a number's breakdown, trend, drivers and the
chief of staff's template explanation; and a question about it."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.common import BreakdownItemOut

type ExplainUnit = Literal["cents", "count", "points", "percent", "months"]


class TrendPointOut(BaseModel):
    turn: int
    date_label: str
    value: float


class ExplainDriverOut(BaseModel):
    label: str
    effect: float | None = Field(
        default=None, description="Its share of the number's last change, in the number's unit"
    )
    change: float | None = Field(default=None, description="The driver's own move, in `unit`")
    unit: ExplainUnit | None = None
    kind: Literal["change", "level"] = Field(
        default="change", description="level: a term of the number as it stands now"
    )


class ExplainOut(BaseModel):
    metric: str
    label: str
    unit: ExplainUnit
    scope: Literal[
        "company", "product", "person", "account", "market", "project", "mine", "fab", "refinery"
    ]
    entity: str | None = None
    subject: str = Field(description="What the number belongs to, by name")
    value: float | None = None
    items: list[BreakdownItemOut] = Field(description="The number's driver breakdown")
    note: str | None = None
    trend: list[TrendPointOut] = Field(description="The last advisor.explain.history_months")
    trend_note: str | None = None
    drivers: list[ExplainDriverOut] = Field(description="What moved it last month, largest first")
    related: list[str] = Field(description="Related events in the last months, as the inbox")
    explanation: str = Field(description="The template explanation (offline, always shown)")
    speaker: str = Field(description="Who answers Ask why: the chief of staff, by name")
    max_question_chars: int
    offline: bool = Field(description="True when Ask why can only give the template answer")


class ExplainAskIn(BaseModel):
    question: str
    entity: str | None = None


class ExplainAnswerOut(BaseModel):
    speaker: str
    question: str
    answer: str
    source: str = Field(description="claude, mock, or template (offline or over budget)")
    cost_cents: float
