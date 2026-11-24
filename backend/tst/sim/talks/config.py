"""Schemas for M49's tunables (docs/formulas.md 61): the `talks.*` keys of balance.yaml.
Model definitions only (no file reads)."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tst.sim.facilities.config import Range

# The talk kinds of 61, in stream-key order: append only (a kind's index keys its draws).
type TalkKind = Literal["interview", "crisis", "one_to_one"]
TALK_KINDS: Final[tuple[TalkKind, ...]] = ("interview", "crisis", "one_to_one")

# The closed move sets (61.1, 61.2); `neutral` is what an unrecognised or invalid scoring becomes.
INTERVIEW_MOVES: Final = (
    "bold_claim",
    "measured",
    "deflect",
    "apologise",
    "promise",
    "attack_rival",
    "no_comment",
    "neutral",
)
CRISIS_MOVES: Final = (*INTERVIEW_MOVES[:-1], "take_responsibility", "neutral")
ONE_TO_ONE_MOVES: Final = (
    "listen",
    "promise_promotion",
    "offer_raise",
    "offer_equity",
    "reassign",
    "push_harder",
    "praise",
    "warn",
    "neutral",
)
MOVES: Final[dict[str, tuple[str, ...]]] = {
    "interview": INTERVIEW_MOVES,
    "crisis": CRISIS_MOVES,
    "one_to_one": ONE_TO_ONE_MOVES,
}
ALL_TALK_MOVES: Final = tuple(sorted({m for ms in MOVES.values() for m in ms}))

# 61.1: each press move answers in one of 29.1's tones; skip is the measured answer.
TONE_OF: Final[dict[str, str]] = {
    "bold_claim": "bold",
    "attack_rival": "bold",
    "measured": "measured",
    "promise": "measured",
    "apologise": "measured",
    "take_responsibility": "measured",
    "deflect": "deflect",
    "no_comment": "deflect",
    "neutral": "measured",
}
TONE_CHOICE: Final[dict[str, str]] = {"measured": "A", "bold": "B", "deflect": "C"}  # press.yaml

# What a one-to-one's question is about (61.2).
type Topic = Literal["morale", "ambition", "approach", "burnout"]
TOPICS: Final[tuple[Topic, ...]] = ("morale", "ambition", "approach", "burnout")
# What a press question is about (61.1).
PRESS_TOPICS: Final = ("subject", "future", "rival", "harm")

# Crisis subjects without a press moment (61.1): append only.
CRISIS_SOURCES: Final = ("recall", "robotaxi", "press")
# The only one-to-one promise the engine tracks (61.2); raises and equity execute at once.
TALK_PROMISE_KINDS: Final = ("promotion",)
PERSONALITY: Final = ("ego", "ambition", "loyalty")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TalkSkill(_Frozen):
    band: Range  # the founder's (or delegate's) factor at score 1 and 20 (as 59.1: 0.8-1.2)
    weights: dict[str, float]  # skill -> weight in the score (sums to 1)


class Outlet(_Frozen):
    name: str
    beat: str


class Interview(_Frozen):
    questions: Range  # questions an interview takes, drawn (61.1: 2-4)
    outlets: tuple[Outlet, ...]  # the journalists' outlets and beats
    stances: dict[str, float]  # public stance -> x on the coverage's gains (sceptical < 1)
    brand_share: float = Field(ge=0)  # % on the brand target a full-strength answer adds
    brand_step: float = Field(gt=0)  # % the coverage moves the brand target at most
    brand_months: int = Field(ge=1)  # months the coverage's brand change runs
    cred_share: float = Field(ge=0)  # credibility points a full-strength answer earns
    cred_step: float = Field(gt=0)  # credibility points an interview moves at most
    effects: dict[str, float]  # move -> strength (-1..1)


class Crisis(_Frozen):
    questions: Range
    window_months: int = Field(ge=0)  # months after a crisis a conference can still be held
    brand_share: float = Field(ge=0)  # % on the brand target a full-strength answer adds
    brand_step: float = Field(gt=0)
    brand_months: int = Field(ge=1)
    cred_share: float = Field(ge=0)
    cred_step: float = Field(gt=0)
    persona_points: float = Field(ge=0)  # trait points at full strength (Beloved, Ruthless)
    deflect_inspection: float = Field(ge=0, le=1)  # chance a deflection brings an inspection
    effects: dict[str, float]


class OneToOne(_Frozen):
    unhappy_below: float = Field(ge=0, le=100)  # shown morale under this flags a person
    burnout_from: float = Field(ge=0, le=100)  # stress from this brings the burnout topic
    morale_step: float = Field(gt=0)  # morale points a talk moves at most (61.2: 6)
    morale_points: float = Field(gt=0)  # morale points a full-strength answer moves
    loyalty_step: float = Field(ge=0)  # loyalty points a talk moves at most
    loyalty_points: float = Field(ge=0)  # loyalty points a full-strength answer moves
    push_stress: float = Field(ge=0)  # stress points push_harder adds
    raise_share: float = Field(gt=0, lt=1)  # offer_raise: salary x (1 + this)
    equity_bp: int = Field(ge=1)  # offer_equity: options of this many bp of FD, from the pool
    retain_base: float = Field(ge=0, le=1)  # retention chance at full strength on an approach
    retain_cap: float = Field(ge=0, le=1)
    trait_weight: dict[str, tuple[str, float]]  # move -> (personality trait, weight)
    trait_band: Range  # the personality factor's bounds
    effects: dict[str, float]  # move -> strength (-1..1) on an ordinary question
    topic_effects: dict[str, dict[str, float]]  # topic -> move -> strength where it differs


class TalkPromises(_Frozen):
    months: int = Field(ge=1)  # a promotion promise's deadline, months out (61.3 target 3: 12)
    kept_morale: float = Field(ge=0)  # morale points when kept
    kept_loyalty: float = Field(ge=0)  # loyalty points when kept
    broken_mult: float = Field(ge=1)  # broken costs this x the kept (61.2: twice)
    leave_mult: float = Field(ge=1)  # x the resignation chance after a broken promise (61.3: 2)
    leave_months: int = Field(ge=1)  # months the higher chance lasts


class TalksBalance(_Frozen):
    energy: dict[str, int]  # talk kind -> founder energy when it ends (61.2: one-to-one 2)
    skill: TalkSkill
    receptiveness: Range  # the other side's drawn factor on the effects at one talk
    delegate_noise: float = Field(
        ge=0, le=1
    )  # a delegate's draw moves their factor by +- this x band
    interview: Interview
    crisis: Crisis
    one_to_one: OneToOne
    promises: TalkPromises
    max_moves: int = Field(ge=1)
    max_message_chars: int = Field(ge=1)
    max_reply_words: int = Field(ge=1)
    suggestions: int = Field(ge=1)
    history_items: int = Field(ge=0)

    @model_validator(mode="after")
    def _check(self) -> TalksBalance:
        if set(self.energy) != set(TALK_KINDS):
            raise ValueError(f"talks.energy needs exactly {list(TALK_KINDS)}")
        tables = {
            "interview": self.interview.effects,
            "crisis": self.crisis.effects,
            "one_to_one": self.one_to_one.effects,
        }
        for kind, table in tables.items():
            if set(table) != set(MOVES[kind]):
                raise ValueError(f"talks.{kind}.effects need exactly {list(MOVES[kind])}")
        extra = [t for t in self.one_to_one.topic_effects.values()]
        for table in (*tables.values(), *extra):
            if any(not -1 <= v <= 1 for v in table.values()):
                raise ValueError("talks effects lie in [-1, 1]")
        for topic, table in self.one_to_one.topic_effects.items():
            if topic not in TOPICS or not set(table) <= set(ONE_TO_ONE_MOVES):
                raise ValueError(f"talks.one_to_one.topic_effects: bad {topic!r}")
        for move, (trait, _w) in self.one_to_one.trait_weight.items():
            if move not in ONE_TO_ONE_MOVES or trait not in PERSONALITY:
                raise ValueError(f"talks.one_to_one.trait_weight: bad {move!r}")
        if abs(sum(self.skill.weights.values()) - 1) > 1e-9:  # tunable-exempt: float tolerance
            raise ValueError("talks.skill.weights must sum to 1")
        if not self.interview.outlets:
            raise ValueError("talks.interview.outlets needs at least one outlet")
        return self
