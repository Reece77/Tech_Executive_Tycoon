"""Events, storylines, relationships and AI writing (M6, docs/formulas.md 16.9).

Effects are words with a size ("large morale lift for Priya", "costs about $8,000"), never
values, caps or trigger strengths; relationships are labels, never numbers; the LLM meter is
spend against the budget and the adapter in use, never the API key.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EventChoiceOut(BaseModel):
    key: str
    label: str
    effects: list[str] = Field(
        description="What the choice does, as numbers: '+3 brand for Pipeline', 'costs $8,000', "
        "'+5% brand target for Pipeline for 12 months' (23.2, M10b)"
    )
    do_nothing: bool = Field(description="An explicit 'Do nothing' choice: no effect (23.2)")


class EventStorylineOut(BaseModel):
    storyline_id: int
    title: str
    step: int


class EventOut(BaseModel):
    event_id: int
    turn: int
    date_label: str
    category: str
    category_label: str
    severity: str = Field(description="minor | major | critical")
    status: str = Field(description="pending | open | answered | auto")
    title: str
    body: str
    choices: list[EventChoiceOut]
    chosen: str | None
    written_by: str = Field(description="Claude | template | mock | replay")
    storyline: EventStorylineOut | None
    follow_up_note: str | None = Field(description="Critical events: when a follow-up comes")
    person_ids: list[int]


class EventsOut(BaseModel):
    to_answer: int
    blocking_event_id: int | None = Field(
        description="An open critical event: it opens as a modal and blocks Continue"
    )
    blocking_event_ids: list[int] = Field(
        description="Every open major and critical event: each blocks Continue (23.1, M10b)"
    )
    blocking_proposal_ids: list[int] = Field(
        description="Executives' proposals waiting for an answer: each blocks Continue (24.1)"
    )
    blocking_pitch_ids: list[int] = Field(
        default_factory=list,
        description="Executives' pitches waiting for an answer: each blocks Continue (27.1)",
    )
    open: list[EventOut]
    recent: list[EventOut] = Field(description="Answered events of the last few months")
    ai_spend_cents: float = Field(description="Real cents spent this calendar month")
    ai_budget_cents: int


class StorylineOut(BaseModel):
    storyline_id: int
    title: str
    step: int
    summary: str
    status: str = Field(description="active | ended")
    started_label: str


class ChooseEventIn(BaseModel):
    choice: str = Field(pattern="^[ABC]$")


class ChooseEventOut(BaseModel):
    event: EventOut
    energy: int
    unread_inbox: int


class RelationshipOut(BaseModel):
    person_id: int
    name: str
    link: str = Field(description="unit-mate | manager | report")
    label: str = Field(description="close | good | neutral | strained | hostile")


class TeamMoodPairOut(BaseModel):
    a_name: str
    b_name: str
    label: str


class TeamMoodOut(BaseModel):
    unit_id: int | None
    line: str
    pairs: list[TeamMoodPairOut] = Field(description="Strained or hostile pairs in the unit")


class LLMSettingsOut(BaseModel):
    adapter: str = Field(description="claude | templates")
    in_use: str = Field(description="What writes events now: Claude or offline templates")
    key_found: bool = Field(description="Whether an API key was found (never the key)")
    spend_cents: float
    budget_cents: int
    calls: int
    reset_date: str
    model_events: str
    model_story: str
    events_by_claude: int
    rejected_drafts: int
    average_cost_cents: float | None
    can_see: list[str]
    cannot_see: list[str]


class LLMSettingsIn(BaseModel):
    adapter: str = Field(pattern="^(claude|templates)$")
    monthly_budget_cents: int = Field(ge=0, le=100_000)
    model_events: str = Field(min_length=1, max_length=64)
    model_story: str = Field(min_length=1, max_length=64)
