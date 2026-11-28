"""Meeting responses (docs/formulas.md 59.5; M48). Only what 59.5 allows: agendas, questions,
answers, moves and their visible effects, the speakers' public facts and confidence,
credibility, commitments and their status. Never a director's priorities, a speaker's
receptiveness, the founder's factor or a draw."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from tst.api.schemas.negotiations import NegotiationModeOut

type ParamValue = str | int | float | bool


class MeetingOpenIn(BaseModel):
    kind: str = Field(description="board | call | investor_day")
    params: dict[str, ParamValue] = Field(
        default_factory=dict,
        description="An investor day's plan: plan_kind (new_industry | capital_plan | "
        "restructuring) and industry (for a new industry)",
    )


class MeetingMoveIn(BaseModel):
    kind: str = Field(
        description="board: commit | explain | defer | concede | push_back; call: reaffirm | "
        "raise | lower | explain | deflect | promise; investor day: explain | commit | deflect "
        "| concede"
    )
    fact: int | None = Field(default=None, description="The question's fact an explain cites")


class MeetingAnswerIn(BaseModel):
    message: str | None = Field(default=None, description="The player's answer (free text)")
    moves: list[MeetingMoveIn] | None = Field(default=None, description="Template mode's moves")
    source: Literal["free", "suggested", "template"] = Field(
        default="free", description="free | suggested | template (M57r-B: a Literal)"
    )


class MeetingSpeakerOut(BaseModel):
    key: str
    kind: str
    name: str
    role: str
    organisation: str
    focus: str
    confidence: float | None
    rating: str
    target_cents: int


class MeetingItemOut(BaseModel):
    n: int
    speaker: int
    topic: str
    title: str
    question: str
    facts: list[str]
    problem: bool
    figure: str
    guidance: bool


class MeetingMoveOut(BaseModel):
    kind: str
    fact: int | None
    words: str


class MeetingAnswerOut(BaseModel):
    n: int
    message: str
    message_source: str
    reply: str
    reply_source: str
    claimed: list[MeetingMoveOut]
    moves: list[MeetingMoveOut]
    reaction: str
    reaction_words: str
    commitment: str


class MeetingEffectOut(BaseModel):
    who: str
    what: str
    change: float
    words: str


class MeetingVoteOut(BaseModel):
    name: str
    backs_plan: bool


class MeetingMoveChoiceOut(BaseModel):
    kind: str
    label: str


class MeetingOut(BaseModel):
    meeting_id: int
    kind: str
    subject: str
    status: str
    opened_turn: int
    date_label: str
    error: str | None
    speakers: list[MeetingSpeakerOut]
    items: list[MeetingItemOut]
    answers: list[MeetingAnswerOut]
    next_item: int | None
    opening_line: str
    move_choices: list[MeetingMoveChoiceOut]
    credibility: float
    persona: list[str]
    plan_subject: str
    plan_facts: list[str]
    effects: list[MeetingEffectOut]
    votes: list[MeetingVoteOut]
    commitments: list[str]
    suggestions: list[str]
    mode: NegotiationModeOut


class MeetingAvailabilityOut(BaseModel):
    kind: str
    available: bool
    reason: str
    meeting_id: int | None


class MeetingSummaryOut(BaseModel):
    meeting_id: int
    kind: str
    subject: str
    status: str
    opened_turn: int
    date_label: str
    effects: list[str]


class MeetingCommitmentOut(BaseModel):
    promise_id: int
    kind: str
    words: str
    made_label: str
    deadline_label: str
    status: str


class MeetingListOut(BaseModel):
    mode: NegotiationModeOut
    available: list[MeetingAvailabilityOut]
    items: list[MeetingSummaryOut]
    commitments: list[MeetingCommitmentOut]
    credibility: float
    industries: list[MeetingMoveChoiceOut] = Field(
        description="The industries an investor day can present a new industry in (key, label)"
    )
