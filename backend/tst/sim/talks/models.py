"""Talk records (docs/formulas.md 61; ADR-0023). A talk is one press interview, crisis
conference or one-to-one: the other side's public facts, its questions (each from the
engine's facts), the hidden reactions and draws (`TalkHidden`), and the answers.

`TalkHidden` never reaches the API or a prompt (61.3 target 5): the API and the prompt
builders read a talk only through `tst.conversations.talk_view.public`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.talks.config import TalkKind

type TalkStatus = Literal["open", "done", "skipped"]


@dataclass(frozen=True, slots=True)
class Counterpart:
    """Who the player talks to: public facts only. A journalist (outlet, beat, stance) or one
    of the company's people (role, level, shown morale)."""

    name: str
    role: str
    organisation: str
    person_id: int | None = None  # a one-to-one's person
    beat: str = ""  # a journalist's
    stance: str = ""  # a journalist's public stance: friendly, neutral or sceptical
    morale: int | None = None  # a person's morale as shown when the talk opened


@dataclass(frozen=True, slots=True)
class Question:
    """One question. `facts` are displayed facts the answer may lean on; `offer` is the
    promise a `promise` (or `promise_promotion`) move would make, in words ("" for none);
    `rival` names the rival an `attack_rival` may name ("" for none)."""

    n: int
    topic: str
    title: str
    question: str
    facts: tuple[str, ...]
    offer: str = ""
    rival: str = ""


@dataclass(frozen=True, slots=True)
class TalkHidden:
    """HIDDEN (61.3 target 5): the other side's receptiveness at each question, drawn when the
    talk opens; the founder's (or delegate's) factor; a person's personality factors by move
    (from their true ego, ambition and loyalty)."""

    receptiveness: tuple[float, ...]
    skill: float
    traits: tuple[tuple[str, float], ...] = ()  # move -> personality factor (one-to-ones)


@dataclass(frozen=True, slots=True)
class Move:
    kind: str


@dataclass(frozen=True, slots=True)
class Answer:
    n: int
    claimed: tuple[Move, ...]
    moves: tuple[Move, ...]
    strength: float  # -1..1, from the published table, before the hidden scaling


@dataclass(frozen=True, slots=True)
class PromiseOffer:
    """A promise a talk can make, through its existing rules (29.2's or 61.2's): its kind and
    parameters, and its words."""

    kind: str  # no_price_rise, no_layoffs or promotion
    words: str
    product_id: int | None = None
    person_id: int | None = None
    months: int = 0


@dataclass(frozen=True, slots=True)
class Subject:
    """What the talk is about: a press moment's event (interviews and press crises), a recall
    or a robotaxi incident (crises without a moment), or a person (one-to-ones)."""

    key: int  # the stream key's subject id: the moment, the recall or incident, the person
    source: str  # press, recall, robotaxi or person
    words: str
    event_id: int | None = None  # the press event the interview answers
    product_id: int | None = None
    rival_id: int | None = None
    approach_id: int | None = None  # a pending rival approach (one-to-ones)
    medical: bool = False  # a medical device's class I recall (an inspection can follow)
    equity_ok: bool = False  # the person has no option grant and the pool has room


@dataclass(frozen=True, slots=True)
class Effects:
    """What a talk did, every value within its bound: the press tone (interviews), the brand
    target change (% for months), credibility, a persona trait's points, an inspection's
    chance; a person's morale, loyalty and stress, a retention chance, a raise, options and a
    promise made."""

    tone: str = ""
    brand_pct: float = 0.0
    brand_months: int = 0
    credibility: float = 0.0
    persona: tuple[str, float] | None = None
    inspection_chance: float = 0.0
    morale: float = 0.0
    loyalty: float = 0.0
    stress: float = 0.0
    retain_chance: float = 0.0
    offer_raise: bool = False  # a raise of talks.one_to_one.raise_share, through give_raise
    equity_bp: int = 0
    reveal: bool = False
    promise: PromiseOffer | None = None


@dataclass(frozen=True, slots=True)
class Talk:
    kind: TalkKind
    company_id: int
    subject: Subject
    opened_turn: int
    counterpart: Counterpart
    questions: tuple[Question, ...]
    hidden: TalkHidden
    audience: float  # 29.1's a, public
    offer: PromiseOffer | None = None  # the one promise the talk can make (its questions' offer)
    delegate_id: int | None = None  # a seat holder holding the one-to-one (61.2)
    answers: tuple[Answer, ...] = ()
    status: TalkStatus = "open"
    effects: Effects | None = None

    @property
    def next_question(self) -> Question | None:
        n = len(self.answers)
        return self.questions[n] if n < len(self.questions) else None
