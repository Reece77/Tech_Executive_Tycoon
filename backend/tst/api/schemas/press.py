"""Schemas for press, promises, credibility, rival CEOs and Replace (M14b, formulas.md 29.6).
Only what 29.6 allows: moments and choices, open promises with their displayed progress and
deadline, credibility and its history, rival CEOs, statements, feud scores and causes. Never a
backfire before it happens, true skills behind a fit, or a rival's decision weights."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tst.api.schemas.people import AttributeOut, EnergyOut


class CauseOut(BaseModel):
    turn: int
    label: str = Field(description="Mon YYYY")
    change: float
    cause: str


class CredibilityOut(BaseModel):
    value: float = Field(description="0-100; drifts toward 50")
    history: list[CauseOut] = Field(description="The last changes and their causes, newest last")


class PromiseOut(BaseModel):
    promise_id: int
    kind: str
    words: str = Field(description="What you said, e.g. 'ship Forge by Jun 2016'")
    made: str
    deadline: str
    months_left: int
    status: str = Field(description="open | kept | broken")
    progress: str = Field(description="Where it stands, from displayed values")


class MomentOut(BaseModel):
    moment_id: int
    trigger: str
    label: str
    shown: str | None = Field(description="The month its event is shown")
    status: str
    tone: str | None
    can_promise: bool = Field(description="Answered this month, not with no comment")


class OptionOut(BaseModel):
    id: int | str
    name: str


class PromiseFormOut(BaseModel):
    moment_id: int | None = Field(description="This month's answered moment to promise in")
    open_count: int
    max_open: int
    energy: int
    months: list[int] = Field(description="[shortest, longest] months for ship, beat, research")
    in_development: list[OptionOut]
    live: list[OptionOut]
    rival_products: list[OptionOut]
    domains: list[OptionOut]


class PressOut(BaseModel):
    credibility: CredibilityOut
    promises: list[PromiseOut]
    moments: list[MomentOut]
    form: PromiseFormOut


class PromiseIn(BaseModel):
    promise: str = Field(description="ship | beat | research | no_layoffs | no_price_rise")
    product_id: int | None = None
    rival_product_id: int | None = None
    domain: str | None = None
    level: int | None = None
    months: int | None = None


class PressActionOut(BaseModel):
    press: PressOut
    energy: EnergyOut
    unread_inbox: int


class StatementOut(BaseModel):
    label: str
    kind: str = Field(description="statement | jab | answer")
    text: str


class FeudOut(BaseModel):
    rival_id: int
    rival: str
    ceo: str | None
    score: float
    rivalry: bool
    causes: list[CauseOut]


class CeoProfileOut(BaseModel):
    """What the player has learned of a rival CEO (M15b addendum 11): ranges only, narrowed
    by public appearances, poach approaches and diligence. Never true values."""

    skills: list[AttributeOut]
    personality: list[AttributeOut]
    potential_phrase: str = Field(description="Potential as a phrase from its revealed range")
    learned_label: str = Field(description="How much is known, as words")


class RivalLeaderOut(BaseModel):
    rival_id: int
    ceo: str | None = Field(description="Their CEO: the founder at a startup")
    ceo_person_id: int | None
    profile: CeoProfileOut | None = Field(
        default=None, description="Ranges the player has learned; null before anything is known"
    )
    statements: list[StatementOut]
    feud: FeudOut


class ReplaceableOut(BaseModel):
    person_id: int
    name: str
    role: str
    level: str
    reason: str = Field(description="resigned | poached")
    can_replace: bool
    problem: str | None


class ReplaceIn(BaseModel):
    person_id: int
