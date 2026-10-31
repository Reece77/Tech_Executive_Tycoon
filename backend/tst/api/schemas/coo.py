"""Ask my COO responses (docs/formulas.md 17.3; M7b)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CooIssueOut(BaseModel):
    key: str
    text: str
    link_kind: str = Field(
        description="finance | event | product | person | org | recruitment | board | rival"
    )
    link_id: int | None


class CooAnswerOut(BaseModel):
    answer_id: int
    turn: int
    date_label: str
    speaker: str
    question: str
    answer: str
    source: str = Field(description="claude | mock | offline")
    cost_cents: float = Field(description="Real money this answer cost, in cents")


class CooOut(BaseModel):
    person_id: int | None = Field(description="Null: the founder's notebook")
    name: str
    role_label: str | None
    briefing: list[CooIssueOut] = Field(description="Up to five issues; empty: nothing urgent")
    answers: list[CooAnswerOut] = Field(description="The last answers, newest first")
    max_question_chars: int
    spend_cents: float = Field(description="AI spend this calendar month")
    budget_cents: int
    offline: bool = Field(description="Answers come from the offline reply (no AI in use)")


class CooQuestionIn(BaseModel):
    question: str = Field(min_length=1)
