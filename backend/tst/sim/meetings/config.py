"""Schemas for M48's tunables (docs/formulas.md 59): the `meetings.*` keys of balance.yaml.
Model definitions only (no file reads)."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range

# The meeting kinds of 59, in stream-key order: append only (a kind's index keys its draws).
type MeetingKind = Literal["board", "call", "investor_day"]
MEETING_KINDS: Final[tuple[MeetingKind, ...]] = ("board", "call", "investor_day")

# What a question is about. A speaker's hidden priorities weigh these (59.1).
type Topic = Literal["growth", "margin", "risk", "governance"]
TOPICS: Final[tuple[Topic, ...]] = ("growth", "margin", "risk", "governance")

# The closed move sets (59.1-59.3); `neutral` is what an unrecognised or invalid scoring becomes.
BOARD_MOVES: Final = ("commit", "explain", "defer", "concede", "push_back", "neutral")
CALL_MOVES: Final = ("reaffirm", "raise", "lower", "explain", "deflect", "promise", "neutral")
DAY_MOVES: Final = ("explain", "commit", "deflect", "concede", "neutral")
MOVES: Final[dict[str, tuple[str, ...]]] = {
    "board": BOARD_MOVES,
    "call": CALL_MOVES,
    "investor_day": DAY_MOVES,
}
ALL_MOVES: Final = tuple(sorted({m for ms in MOVES.values() for m in ms}))

# Investor-day plans (59.3)
type PlanKind = Literal["new_industry", "capital_plan", "restructuring"]
PLAN_KINDS: Final[tuple[PlanKind, ...]] = ("new_industry", "capital_plan", "restructuring")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MeetingSkill(_Frozen):
    band: Range  # the founder's factor at score 1 and 20 (59.1: 0.8-1.2)
    weights: dict[str, float]  # skill -> weight in the founder's score (sums to 1)
    persona_mult: float = Field(ge=1)  # x a suiting move for a strong persona trait (32.4)


class BoardMeeting(_Frozen):
    step: float = Field(gt=0)  # points; most one director's confidence moves in one meeting
    item_points: float = Field(gt=0)  # points a full-strength answer moves the asker
    spill: float = Field(ge=0, le=1)  # share of an answer's effect the other directors feel
    items: int = Field(ge=1)  # agenda items at most
    concern_below: float = Field(ge=0, le=100)  # a director under this raises a concern
    vote_at: float = Field(ge=0, le=100)  # a director backs the plan from this confidence
    vote_priority: float = Field(ge=0)  # points a director's growth weight adds to its vote
    commitment_kept: float = Field(ge=0)  # points to every voting director when kept
    commitment_broken_mult: float = Field(ge=1)  # a broken commitment costs this x the kept
    effects: dict[str, float]  # move -> strength on an ordinary item (-1..1)
    problem_effects: dict[str, float]  # move -> strength on an item about a real problem
    push_back_unloved: float  # push_back's strength when the asker cares little for the topic


class EarningsCall(_Frozen):
    step: float = Field(gt=0)  # share of S; most a call moves sentiment (59.2: 3%)
    target_step: float = Field(gt=0)  # share; most a call moves one analyst's target (5%)
    item_share: float = Field(gt=0)  # sentiment share a full-strength answer earns
    target_share: float = Field(gt=0)  # target share a full-strength answer earns the asker
    questions: int = Field(ge=1)  # questions a call takes at most
    guidance_step: float = Field(gt=0, lt=1)  # raise/lower move revenue guidance by this share
    deflect_cred: float = Field(ge=0)  # credibility a deflection on a real problem costs
    effects: dict[str, float]
    problem_effects: dict[str, float]


class InvestorDay(_Frozen):
    step: float = Field(gt=0)  # share of S; most an investor day moves sentiment (59.3: 8%)
    cred_step: float = Field(gt=0)  # credibility points it moves at most (59.3: 10)
    item_share: float = Field(gt=0)  # sentiment share a full-strength answer earns
    item_cred: float = Field(ge=0)  # credibility points a full-strength answer earns
    economics_share: float = Field(ge=0)  # sentiment share the plan's economics earn at +-1
    economics_cred: float = Field(ge=0)  # credibility points they earn at +-1
    hurdle: float  # return on capital the plan's economics are judged against
    span: float = Field(gt=0)  # return on capital above the hurdle that scores +1
    every_months: int = Field(ge=1)  # an investor day at most this often
    firms: tuple[str, ...]  # the investors who ask, by firm
    questions: int = Field(ge=1)
    effects: dict[str, float]
    problem_effects: dict[str, float]


class MeetingCredibility(_Frozen):
    full_at: float = Field(ge=0, le=100)  # positive effects are whole from this credibility
    half_at: float = Field(ge=0, le=100)  # ...and halved at or below this (59.2)
    guidance_kept: float = Field(ge=0)  # credibility for guidance kept (a call's promise)
    guidance_broken: float = Field(ge=0)  # ...lost for guidance broken


class MeetingsBalance(_Frozen):
    energy: dict[str, int]  # meeting kind -> founder energy to attend
    skill: MeetingSkill
    priority_traits: dict[str, str]  # topic -> personality trait behind it ("-" reverses)
    priority_noise: float = Field(ge=0, lt=1)  # a meeting's draw moves a weight by +- this share
    priority_weight: float = Field(ge=0, le=1)  # how much the asker's weight on a topic counts
    receptiveness: Range  # a speaker's drawn factor on the effects at one meeting
    board: BoardMeeting
    call: EarningsCall
    investor_day: InvestorDay
    credibility: MeetingCredibility
    max_moves: int = Field(ge=1)  # moves one answer counts at most
    max_message_chars: int = Field(ge=1)  # characters in the player's answer
    max_reply_words: int = Field(ge=1)  # words in the speaker's reply
    suggestions: int = Field(ge=1)  # suggested answers an item (three)
    history_items: int = Field(ge=0)  # earlier items quoted in a prompt

    @model_validator(mode="after")
    def _check(self) -> MeetingsBalance:
        if set(self.energy) != set(MEETING_KINDS):
            raise ValueError(f"meetings.energy needs exactly {list(MEETING_KINDS)}")
        if set(self.priority_traits) != set(TOPICS):
            raise ValueError(f"meetings.priority_traits needs exactly {list(TOPICS)}")
        tables = {
            "board": (self.board.effects, self.board.problem_effects),
            "call": (self.call.effects, self.call.problem_effects),
            "investor_day": (self.investor_day.effects, self.investor_day.problem_effects),
        }
        for kind, pair in tables.items():
            for table in pair:
                if set(table) != set(MOVES[kind]):
                    raise ValueError(f"meetings.{kind} effects need exactly {list(MOVES[kind])}")
                if any(not -1 <= v <= 1 for v in table.values()):
                    raise ValueError(f"meetings.{kind} effects lie in [-1, 1]")
        if abs(sum(self.skill.weights.values()) - 1) > 1e-9:  # tunable-exempt: float tolerance
            raise ValueError("meetings.skill.weights must sum to 1")
        if not self.credibility.half_at < self.credibility.full_at:
            raise ValueError("meetings.credibility.half_at is below full_at")
        return self
