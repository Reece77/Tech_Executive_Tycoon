"""Meeting records (docs/formulas.md 59; ADR-0023). A meeting is one board meeting, earnings
call or investor day: its speakers' public facts, its agenda (items, each a question from the
engine's facts), the speakers' hidden priorities and draws (`MeetingHidden`), and the answers.

`MeetingHidden` never reaches the API or a prompt (59.5): the API and the prompt builders read
a meeting only through `tst.conversations.meeting_view.public`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.meetings.config import MeetingKind, PlanKind, Topic

type MeetingStatus = Literal["open", "done", "skipped"]
type Metric = Literal["revenue", "margin"]
type CommitmentKind = Literal["commitment", "guidance"]
type SpeakerKind = Literal["director", "analyst", "investor"]


@dataclass(frozen=True, slots=True)
class Speaker:
    """Who asks: public facts only. A director's confidence and an analyst's rating and target
    are as the player sees them when the meeting opens."""

    key: str
    kind: SpeakerKind
    name: str
    role: str
    organisation: str
    seat_id: int | None = None  # a director's seat
    analyst_index: int | None = None  # an analyst's place in public.analysts
    focus: str = ""  # an analyst's public focus (a topic); "" for a director
    confidence: float | None = None  # a director's, 0-100
    rating: str = ""  # an analyst's
    target_cents: int = 0  # an analyst's price target


@dataclass(frozen=True, slots=True)
class Figure:
    """A plan figure a commitment can be made to: next quarter's revenue (cents) or operating
    margin (basis points), at least `value`."""

    metric: Metric
    value: int
    words: str


@dataclass(frozen=True, slots=True)
class Item:
    """One agenda item or question. `facts` are displayed facts an `explain` may cite;
    `problem` marks a question about a real problem (a miss, a short runway, a concern)."""

    n: int
    speaker: int  # index into Meeting.speakers
    topic: Topic
    title: str
    question: str  # the template's question, from the facts
    facts: tuple[str, ...]
    problem: bool = False
    figure: Figure | None = None
    guidance: bool = False  # the call's guidance question (reaffirm, raise, lower)


@dataclass(frozen=True, slots=True)
class MeetingHidden:
    """HIDDEN (59.5): each speaker's priority weights over TOPICS (summing to 1) and its
    receptiveness this meeting, drawn when the meeting opens; the founder's factor."""

    priorities: tuple[tuple[float, ...], ...]
    receptiveness: tuple[float, ...]
    skill: float


@dataclass(frozen=True, slots=True)
class Move:
    kind: str
    fact: int | None = None  # the item's fact an explain cites (an index)


@dataclass(frozen=True, slots=True)
class Commitment:
    """A commitment made in a meeting, tracked as a promise (29.2): a board commitment to a
    plan figure, or guidance given on a call. Judged at `deadline_turn` (a quarter's end)."""

    kind: CommitmentKind
    metric: Metric
    level: int
    baseline: int
    deadline_turn: int
    words: str


@dataclass(frozen=True, slots=True)
class Answer:
    """One item answered: the moves as scored and as checked, and the effect's strength
    (-1..1, before the speaker's scaling), a commitment made, a guidance change (+1 raise,
    -1 lower, 0 none) and credibility lost to a deflection."""

    n: int
    claimed: tuple[Move, ...]
    moves: tuple[Move, ...]
    strength: float
    commitment: Commitment | None = None
    guidance_change: int = 0
    reaffirmed: bool = False
    credibility: float = 0.0


@dataclass(frozen=True, slots=True)
class Plan:
    """An investor day's plan (59.3): its kind, a public subject and its displayed economics,
    scored -1..1 against the hurdle."""

    kind: PlanKind
    subject: str
    facts: tuple[str, ...]
    economics: float


@dataclass(frozen=True, slots=True)
class Effects:
    """What a meeting did (59.1-59.3), every value within its bound: confidence by seat,
    sentiment as a share of S, target shares by analyst, credibility points, commitments and
    the quarter's guidance (revenue cents, margin bp) when the call set it."""

    confidence: tuple[tuple[int, float], ...] = ()
    sentiment: float = 0.0
    targets: tuple[tuple[int, float], ...] = ()
    credibility: float = 0.0
    commitments: tuple[Commitment, ...] = ()
    guidance: tuple[int, int] | None = None
    votes: tuple[tuple[int, bool], ...] = ()  # (speaker index, backs the plan)


@dataclass(frozen=True, slots=True)
class Meeting:
    kind: MeetingKind
    company_id: int
    subject: str
    opened_turn: int
    period_turn: int  # the quarter (its first month) the meeting reports on or plans
    speakers: tuple[Speaker, ...]
    items: tuple[Item, ...]
    hidden: MeetingHidden
    persona: tuple[str, ...]  # the founder's public persona traits that count (32.4)
    credibility: float  # public, when the meeting opened
    guidance_base: tuple[int, int] | None = None  # a call: the quarter's guidance before it
    plan: Plan | None = None  # an investor day's
    answers: tuple[Answer, ...] = ()
    status: MeetingStatus = "open"
    effects: Effects | None = None

    @property
    def next_item(self) -> Item | None:
        return self.items[len(self.answers)] if len(self.answers) < len(self.items) else None
