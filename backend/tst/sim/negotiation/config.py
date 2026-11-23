"""Schemas for M47's tunables (ADR-0008, docs/formulas.md 58): the `negotiation.*` keys and
`llm.conversation_budget_cents` of balance.yaml. Model definitions only (no file reads)."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range

# The deal kinds of 58.1, in stream-key order: append only (a kind's index keys its draws).
type DealKind = Literal[
    "acquisition",
    "hire",
    "retention",
    "supplier",
    "offtake",
    "foundry",
    "ppa",
    "government",
    "settlement",
    "licence_in",
    "licence_out",
]
DEAL_KINDS: Final[tuple[DealKind, ...]] = (
    "acquisition",
    "hire",
    "retention",
    "supplier",
    "offtake",
    "foundry",
    "ppa",
    "government",
    "settlement",
    "licence_in",
    "licence_out",
)

# The closed move set of 58.3 (`neutral` is what an unrecognised or invalid scoring becomes).
type MoveKind = Literal[
    "concede", "anchor", "justify", "appeal", "threaten_walk", "package", "close", "neutral"
]
MOVE_KINDS: Final[tuple[MoveKind, ...]] = (
    "concede",
    "anchor",
    "justify",
    "appeal",
    "threaten_walk",
    "package",
    "close",
    "neutral",
)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MoveEffect(_Frozen):
    concession: float = Field(ge=0, le=1)  # share of move_step this move earns
    patience: int = Field(ge=-1, le=1)  # rounds of patience it adds (+) or uses (-)
    relationship: int = Field(ge=-2, le=2)  # points on the counterpart's relationship


class RangeBalance(_Frozen):
    start: float = Field(gt=0)  # half-width of the revealed range at the opening, x the zone
    narrow: float = Field(ge=0, lt=1)  # a round narrows it by this x the counterpart's openness
    floor: float = Field(gt=0)  # never narrower than this half-width, x the zone
    centre: float = Field(ge=0, lt=1)  # the range's centre is at most this x its half-width off
    skill_power: float = Field(ge=0)  # the width x (2 - skill factor) to this power


class SkillBalance(_Frozen):
    band: Range  # the skill factor's range (58.3: 0.8-1.2)
    weights: dict[str, float]  # skill -> weight in the negotiator's score (sums to 1)
    persona_at: float = Field(ge=0, le=100)  # a persona trait counts from this score
    persona_mult: float = Field(ge=1)  # x a move's effect for the trait that suits it


class NegotiationBalance(_Frozen):
    spread: dict[str, float]  # deal kind -> the zone's half-width x the median (today's price)
    spread_jitter: float = Field(ge=0, lt=1)  # the half-width varies by +/- this share
    min_spread_bp: int = Field(ge=1)  # the zone's half-width is at least this, in basis points
    patience: Range  # rounds before the counterpart walks (58.2: 3-8)
    move_step: float = Field(gt=0, le=1)  # most the counterpart's offer moves in a round, x zone
    effects: dict[str, MoveEffect]  # move -> its fixed effect (58.3)
    appeal_good: int  # relationship from which an appeal adds patience (16.7's "good": 20)
    anchor_gap: float = Field(ge=0, le=1)  # an anchor offers at least this x zone below demand
    accept_tolerance: float = Field(ge=0, lt=1)  # accepts an offer this close to its demand
    close_tolerance: float = Field(ge=0, lt=1)  # ...this close when asked to close
    max_moves: int = Field(ge=1)  # moves a message counts at most
    max_rounds: int = Field(ge=1)  # rounds a negotiation runs at most
    shown_round: float = Field(gt=0, lt=1)  # offers are shown rounded to this x the median
    range: RangeBalance
    skill: SkillBalance
    relationship_walk: int = Field(le=0)  # relationship after a walk-away
    relationship_agree: int = Field(ge=0)  # ...after an agreement
    relationship_floor: int = Field(le=0)  # a counterpart's relationship stays within
    relationship_ceiling: int = Field(ge=0)  # [floor, ceiling]
    cooldown_months: int = Field(ge=0)  # a walked-away deal can be talked about again after
    max_message_chars: int = Field(ge=1)  # characters in the player's message
    max_reply_words: int = Field(ge=1)  # words in the counterpart's reply
    suggestions: int = Field(ge=1)  # suggested replies a round (58.3: three)
    history_rounds: int = Field(ge=0)  # earlier rounds quoted in a prompt

    @model_validator(mode="after")
    def _check(self) -> NegotiationBalance:
        missing = set(DEAL_KINDS) - set(self.spread)
        if missing:
            raise ValueError(f"negotiation.spread needs {sorted(missing)}")
        if set(self.effects) != set(MOVE_KINDS):
            raise ValueError(f"negotiation.effects needs exactly {list(MOVE_KINDS)}")
        if abs(sum(self.skill.weights.values()) - 1) > 1e-9:  # tunable-exempt: float tolerance
            raise ValueError("negotiation.skill.weights must sum to 1")
        if not 1 <= self.patience.lo <= self.patience.hi:
            raise ValueError("negotiation.patience is [lo, hi] rounds, lo at least 1")
        return self


class LlmBalance(_Frozen):
    conversation_budget_cents: int = Field(ge=0)  # real cents a calendar month for conversations
