"""Negotiation responses (docs/formulas.md 58.6; M47). Only what 58.6 allows: opening offers,
the counterpart's public facts and stated reasons, ranges as revealed, rounds and their moves,
the debrief. Never a reservation value, aspiration, patience, priority or draw."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

type ParamValue = str | int | float | bool


class NegotiationOpenIn(BaseModel):
    kind: str = Field(
        description="acquisition | hire | retention | supplier | offtake | foundry | ppa | "
        "government | settlement | licence_in | licence_out"
    )
    params: dict[str, ParamValue] = Field(
        description="The deal as its own action takes it (e.g. target_id, candidate_id, good)"
    )


class MoveIn(BaseModel):
    kind: str = Field(
        description="concede | anchor | justify | appeal | threaten_walk | package | close"
    )
    term: int | None = None
    other: int | None = None
    fact: int | None = None


class RoundIn(BaseModel):
    offer: list[int] = Field(description="The player's offer, one value per term in its unit")
    message: str | None = Field(default=None, description="Free text (LLM mode); untrusted")
    moves: list[MoveIn] | None = Field(default=None, description="Template mode's buttons")
    source: Literal["free", "suggested", "template"] = "free"


class TermOut(BaseModel):
    key: str
    label: str
    unit: str = Field(description="cents | bp (basis points of the quote)")
    wants: str = Field(description="lower | higher: which way the player wants it")
    base_shown: str = Field(description="The quote a bp term is a share of")


class MoveOut(BaseModel):
    kind: str
    term: int | None
    other: int | None
    fact: int | None
    words: str


class RangeOut(BaseModel):
    lo: int
    hi: int
    shown: str


class RoundOut(BaseModel):
    n: int
    offer: list[int]
    offer_shown: list[str]
    claimed: list[MoveOut] = Field(description="The moves as scored")
    moves: list[MoveOut] = Field(description="After the engine's checks")
    counter_before: list[int]
    counter: list[int]
    counter_shown: list[str]
    outcome: str = Field(description="countered | final | agreed | walked")
    reason: str
    reason_words: str
    mood: str = Field(description="open | firm | final: how close they are to walking")
    relationship_change: int
    message: str
    message_source: str
    reply: str
    reply_source: str


class ModeOut(BaseModel):
    mode: str = Field(description="llm | template")
    reason: str = Field(description="'' | setting | offline | budget")
    cap_cents: int
    spent_cents: float


class NegotiationOut(BaseModel):
    negotiation_id: int
    kind: str
    subject: str
    status: str = Field(description="open | agreed | walked | skipped | lapsed | failed")
    opened_turn: int
    date_label: str
    cooldown_until: int | None
    error: str | None
    terms: list[TermOut]
    counterpart_name: str
    counterpart_role: str
    counterpart_organisation: str
    counterpart_style: str
    relationship: str
    facts: list[str]
    used_facts: list[int]
    persona: list[str]
    opening: list[int]
    opening_shown: list[str]
    opening_line: str
    counter: list[int]
    counter_shown: list[str]
    offer: list[int] | None
    offer_shown: list[str]
    ranges: list[RangeOut] = Field(description="Where their limit lies, as revealed")
    mood: str
    rounds: list[RoundOut]
    suggestions: list[str]
    final: list[int] | None
    final_shown: list[str]
    mode: ModeOut


class NegotiationSummaryOut(BaseModel):
    negotiation_id: int
    kind: str
    subject: str
    status: str
    opened_turn: int
    date_label: str
    counterpart_name: str
    counterpart_organisation: str
    rounds: int
    final_shown: list[str]


class NegotiationListOut(BaseModel):
    mode: ModeOut
    items: list[NegotiationSummaryOut]
