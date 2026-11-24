"""Talk responses (docs/formulas.md 61.3 target 5; M49). Only what 61 allows: the journalist's or
person's public facts, questions and their displayed facts, answers, moves and their visible
effects, the promise on offer in words, the rival that approached someone (never its offer),
tracked promises and their status. Never a receptiveness, a personality factor, the founder's
or a delegate's factor, a retention chance, a draw, or a rival's offer amount."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.negotiations import NegotiationModeOut

type ParamValue = str | int | float | bool


class TalkOpenIn(BaseModel):
    kind: str = Field(description="interview | crisis | one_to_one")
    params: dict[str, ParamValue] = Field(
        default_factory=dict,
        description="An interview or crisis: source (press | recall | robotaxi) and key; a "
        "one-to-one: person_id, and delegate_id for a seat holder to hold it",
    )


class TalkMoveIn(BaseModel):
    kind: str = Field(
        description="interview: bold_claim | measured | deflect | apologise | promise | "
        "attack_rival | no_comment; crisis: those and take_responsibility; one-to-one: listen | "
        "promise_promotion | offer_raise | offer_equity | reassign | push_harder | praise | warn"
    )


class TalkAnswerIn(BaseModel):
    message: str | None = Field(default=None, description="The player's answer (free text)")
    moves: list[TalkMoveIn] | None = Field(default=None, description="Template mode's moves")
    source: str = Field(default="free", description="free | suggested | template")


class TalkCounterpartOut(BaseModel):
    name: str
    role: str
    organisation: str
    person_id: int | None
    beat: str
    stance: str = Field(description="A journalist's public stance: friendly | neutral | sceptical")
    morale: int | None = Field(description="A person's morale as shown when the talk opened")


class TalkQuestionOut(BaseModel):
    n: int
    topic: str
    title: str
    question: str
    facts: list[str]
    offer: str = Field(description="The promise an answer here can make, in words")
    rival: str


class TalkMoveOut(BaseModel):
    kind: str
    words: str


class TalkAnswerOut(BaseModel):
    n: int
    message: str
    message_source: str
    reply: str
    reply_source: str
    claimed: list[TalkMoveOut]
    moves: list[TalkMoveOut]
    reaction: str
    reaction_words: str


class TalkEffectOut(BaseModel):
    what: str
    change: float
    words: str


class TalkMoveChoiceOut(BaseModel):
    kind: str
    label: str


class TalkOut(BaseModel):
    talk_id: int
    kind: str
    subject: str
    source: str
    status: str
    opened_turn: int
    date_label: str
    error: str | None
    counterpart: TalkCounterpartOut
    questions: list[TalkQuestionOut]
    answers: list[TalkAnswerOut]
    next_question: int | None
    opening_line: str
    move_choices: list[TalkMoveChoiceOut]
    offer: str
    approached_by: str
    delegated: bool
    effects: list[TalkEffectOut]
    suggestions: list[str]
    mode: NegotiationModeOut


class TalkAvailableOut(BaseModel):
    kind: str
    source: str
    key: int
    subject: str
    talk_id: int | None
    status: str


class TalkSummaryOut(BaseModel):
    talk_id: int
    kind: str
    subject: str
    status: str
    opened_turn: int
    date_label: str
    person_id: int | None
    effects: list[str]


class TalkPromiseOut(BaseModel):
    promise_id: int
    person_id: int
    words: str
    made_label: str
    deadline_label: str
    status: str


class TalkPersonOut(BaseModel):
    """Someone the player might hold a one-to-one with, and why they are flagged."""

    person_id: int
    name: str
    role_label: str
    morale: int | None
    flags: list[str] = Field(description="unhappy | approached | seat")
    approached_by: str
    held: str = Field(description="This month's one-to-one status, or empty")
    delegates: list[int] = Field(description="Seat holders above them who can hold it for you")


class TalkListOut(BaseModel):
    mode: NegotiationModeOut
    available: list[TalkAvailableOut]
    items: list[TalkSummaryOut]
    people: list[TalkPersonOut]
    promises: list[TalkPromiseOut]
    energy: int | None
    one_to_one_energy: int
