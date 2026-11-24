"""The immediate action a meeting ends with (docs/formulas.md 59; ADR-0014): `MeetingOutcome`
applies a finished meeting's effects, which the meetings engine computed within its bounds:
directors' confidence, sentiment, analysts' targets, credibility, commitments as promises
(29.2) and the quarter's guidance. Set only by the meetings service; replays apply it from the
decision log like any action, so a game replay never reads a conversation. A skipped meeting
has no action: skip is today's game (59.4 target 1).

The action re-checks every bound, so even a hand-made outcome cannot move more than 59 allows.
Its fields are JSON-plain (lists of numbers and strings), as the decision log stores them."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import MeetingRuleError
from tst.sim.log import inbox_item
from tst.sim.markets_public.public import consensus, guidance_problem
from tst.sim.meetings.config import MEETING_KINDS
from tst.sim.meetings.models import Meeting
from tst.sim.press import moments
from tst.sim.press.models import Promise
from tst.sim.state import GameState, public_of, with_guidance, with_promise, with_public, with_seat

PCT: Final = 100  # the confidence scale
EPS: Final = 1e-9  # tunable-exempt: float tolerance on a bound
QUARTER_END: Final = 2  # tunable-exempt: a quarter's last month, from its first
CAUSES: Final = {
    "board": "a board meeting",
    "call": "an earnings call",
    "investor_day": "an investor day",
}
COMMITMENT_KINDS: Final = ("commitment", "guidance")
METRICS: Final = ("revenue", "margin")


@dataclass(frozen=True, slots=True)
class MeetingOutcome:
    actor_id: int
    meeting_kind: str  # board, call or investor_day
    period_turn: int  # the month the meeting was held
    confidence: Sequence[Sequence[float]] = ()  # (seat id, points)
    sentiment: float = 0.0  # share of S
    targets: Sequence[Sequence[float]] = ()  # (analyst index, share)
    credibility: float = 0.0  # points
    # (kind, metric, level, baseline, deadline turn, words)
    commitments: Sequence[Sequence[Any]] = ()
    guidance: Sequence[int] | None = None  # (revenue cents, margin bp)
    summary: str = ""  # the inbox's one line (public words)
    kind: Literal["meeting_outcome"] = "meeting_outcome"


ACTION_TYPES: Final[dict[str, type]] = {"meeting_outcome": MeetingOutcome}


def _check(state: GameState, a: MeetingOutcome, balance: Balance) -> None:
    mb = balance.meetings
    if a.meeting_kind not in MEETING_KINDS:
        raise MeetingRuleError(f"unknown meeting {a.meeting_kind!r}")
    if a.period_turn != state.turn:
        raise MeetingRuleError("a meeting's outcome is applied in the month it is held")
    s_bound = {"board": 0.0, "call": mb.call.step, "investor_day": mb.investor_day.step}
    if abs(a.sentiment) > s_bound[a.meeting_kind] + EPS:
        raise MeetingRuleError("the sentiment change is out of bounds")
    for _seat, points in a.confidence:
        if abs(points) > mb.board.step + EPS or a.meeting_kind != "board":
            raise MeetingRuleError("a confidence change is out of bounds")
    for _i, share in a.targets:
        if abs(share) > mb.call.target_step + EPS or a.meeting_kind != "call":
            raise MeetingRuleError("a target change is out of bounds")
    c_lo = {
        "board": 0.0,
        "call": -mb.call.questions * mb.call.deflect_cred,
        "investor_day": -mb.investor_day.cred_step,
    }[a.meeting_kind]
    c_hi = mb.investor_day.cred_step if a.meeting_kind == "investor_day" else 0.0
    if not c_lo - EPS <= a.credibility <= c_hi + EPS:
        raise MeetingRuleError("the credibility change is out of bounds")
    for c in a.commitments:
        kind, metric, _level, _base, deadline, _words = c
        if kind not in COMMITMENT_KINDS or metric not in METRICS:
            raise MeetingRuleError("unknown commitment")
        if deadline != state.turn + QUARTER_END:
            raise MeetingRuleError("a commitment is due at the quarter's end")


def apply_meeting(state: GameState, a: MeetingOutcome, balance: Balance, data: GameData) -> Outcome:
    cid = acting_company(state, a.actor_id)
    founder = state.founder_of(cid)
    if founder is None or founder.id != a.actor_id:
        raise MeetingRuleError("the founder attends the company's meetings")
    _check(state, a, balance)
    state = spend_energy(
        state, a.actor_id, a.kind, balance, cost=balance.meetings.energy[a.meeting_kind]
    )
    seats = {s.id: s for s in state.board(cid)}
    for seat_id, points in a.confidence:
        seat = seats.get(int(seat_id))
        if seat is None or seat.confidence is None:
            raise MeetingRuleError(f"no voting director in seat {seat_id}")
        value = max(0.0, min(float(PCT), seat.confidence + float(points)))
        state = with_seat(state, replace(seat, confidence=value))
    public = public_of(state, cid)
    if (a.sentiment or a.targets) and public is None:
        raise MeetingRuleError("only a listed company has a share price to move")
    if public is not None and (a.sentiment or a.targets):
        bounds = balance.public.sentiment.bounds
        by_index = {int(i): float(s) for i, s in a.targets}
        analysts = tuple(
            replace(x, target_cents=max(1, round(x.target_cents * (1 + by_index[x.index]))))
            if x.index in by_index
            else x
            for x in public.analysts
        )
        state = with_public(
            state,
            replace(
                public,
                sentiment=bounds.clamp(public.sentiment * (1 + float(a.sentiment))),
                analysts=analysts,
            ),
        )
    state = moments.adjust_credibility(
        state, cid, float(a.credibility), CAUSES[a.meeting_kind], balance
    )
    if a.guidance is not None:
        revenue, margin = (int(v) for v in a.guidance)
        why = guidance_problem(state, cid, revenue, balance)
        if why is not None:
            raise MeetingRuleError(why)
        from tst.sim.markets_public.models import Guidance

        cons_rev, cons_margin = consensus(state, cid)
        state = with_guidance(
            state, Guidance(cid, state.turn, revenue, margin, cons_rev, cons_margin, True)
        )
    for kind, metric, level, base, deadline, _words in a.commitments:
        pid, ids = state.next_ids.take("promise")
        state = with_promise(
            replace(state, next_ids=ids),
            Promise(
                id=pid,
                company_id=cid,
                kind=str(kind),
                made_turn=state.turn,
                deadline_turn=int(deadline),
                domain=str(metric),
                level=int(level),
                baseline=int(base),
            ),
        )
    log = inbox_item(
        state.turn,
        cid,
        "meeting_held",
        link_kind="finance",
        meeting=CAUSES[a.meeting_kind],
        summary=a.summary,
    )
    return Outcome(state, (), (log,))


def summary_words(meeting: Meeting) -> str:
    """The inbox's line, from the engine's effects only (public words)."""
    e = meeting.effects
    assert e is not None
    parts: list[str] = []
    if e.confidence:
        avg = sum(d for _s, d in e.confidence) / len(e.confidence)
        parts.append(f"directors' confidence {avg:+.1f} on average")
    if e.votes:
        backing = sum(1 for _i, v in e.votes if v)
        parts.append(f"{backing} of {len(e.votes)} directors back the plan")
    if e.sentiment:
        parts.append(f"market sentiment {e.sentiment:+.1%}")
    if e.credibility:
        parts.append(f"credibility {e.credibility:+.1f}")
    for c in e.commitments:
        parts.append(f"you committed to {c.words}")
    text = "; ".join(parts) or "nothing moved"
    return f"{meeting.subject}: {text}."


def outcome_action(meeting: Meeting, actor_id: int) -> MeetingOutcome:
    """The finished meeting's effects as the action that applies them."""
    e = meeting.effects
    if meeting.status != "done" or e is None:
        raise MeetingRuleError("only a finished meeting has an outcome")
    return MeetingOutcome(
        actor_id=actor_id,
        meeting_kind=meeting.kind,
        period_turn=meeting.period_turn,
        confidence=tuple((s, d) for s, d in e.confidence),
        sentiment=e.sentiment,
        targets=tuple((i, t) for i, t in e.targets),
        credibility=e.credibility,
        commitments=tuple(
            (c.kind, c.metric, c.level, c.baseline, c.deadline_turn, c.words) for c in e.commitments
        ),
        guidance=e.guidance,
        summary=summary_words(meeting),
    )
