"""The meetings engine (docs/formulas.md 59.1-59.3): moves, their bounded effects and the
meeting's outcome. Pure: a meeting and an item's scored moves in, a new meeting out. The LLM's
part ends at the moves (validated JSON, ADR-0023); everything here is the engine's, so the same
moves always give the same effects and a replay needs no LLM.

Each answered item has a strength in -1..1: the sum of its checked moves' fixed effects (the
problem table when the question is about a real problem), scaled by the founder's factor
(0.8-1.2: a better communicator gains more and loses less) and, for a suiting persona, by
`skill.persona_mult`. A speaker feels it x their relevance (their hidden weight on the item's
topic: 1 + priority_weight x (n w - 1)) x their receptiveness this meeting. Totals are clamped
to each kind's step, so no meeting moves anything further than 59 allows."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.errors import MeetingRuleError
from tst.sim.meetings.agenda import money_words
from tst.sim.meetings.config import MOVES, TOPICS, MeetingsBalance
from tst.sim.meetings.models import Answer, Commitment, CommitmentKind, Effects, Item, Meeting, Move

POSITIVE_FOR: dict[str, str] = {"beloved": "positive", "ruthless": "push_back"}
GUIDANCE_MOVES = ("reaffirm", "raise", "lower")
SHARE_DIGITS = 6  # tunable-exempt: stored precision of a share (sentiment, targets)
POINT_DIGITS = 4  # tunable-exempt: stored precision of points (confidence, credibility)
CHANGE = {"reaffirm": 0, "raise": 1, "lower": -1}


def _clamp(v: float, bound: float) -> float:
    return max(-bound, min(bound, v))


def check_moves(
    meeting: Meeting, item: Item, claimed: tuple[Move, ...], max_moves: int
) -> tuple[Move, ...]:
    """The engine's checks on scored moves: one not in the kind's set, or that the item does
    not bear out, is `neutral` (59). One of each kind, one guidance move, at most `max_moves`."""
    allowed = MOVES[meeting.kind]
    out: list[Move] = []
    seen: set[str] = set()
    for m in claimed:
        if len(out) >= max_moves:
            break
        kind = m.kind if m.kind in allowed else "neutral"
        if kind in seen or (kind in GUIDANCE_MOVES and seen & set(GUIDANCE_MOVES)):
            continue
        seen.add(kind)
        ok = True
        if kind == "explain":
            ok = m.fact is not None and 0 <= m.fact < len(item.facts)
        elif kind in GUIDANCE_MOVES:
            ok = item.guidance
        elif kind == "promise" or (kind == "commit" and meeting.kind == "board"):
            ok = item.figure is not None
        out.append(Move(kind, m.fact if kind == "explain" else None) if ok else Move("neutral"))
    return tuple(out) or (Move("neutral"),)


def _tables(meeting: Meeting, mb: MeetingsBalance) -> tuple[dict[str, float], dict[str, float]]:
    if meeting.kind == "board":
        return mb.board.effects, mb.board.problem_effects
    if meeting.kind == "call":
        return mb.call.effects, mb.call.problem_effects
    return mb.investor_day.effects, mb.investor_day.problem_effects


def relevance(meeting: Meeting, speaker: int, item: Item, mb: MeetingsBalance) -> float:
    w = meeting.hidden.priorities[speaker][TOPICS.index(item.topic)]
    return 1 + mb.priority_weight * (len(TOPICS) * w - 1)


def raw_strength(
    meeting: Meeting, item: Item, moves: tuple[Move, ...], mb: MeetingsBalance
) -> float:
    """The moves' fixed effects summed, -1..1, before the founder's and speakers' scaling."""
    ordinary, problem = _tables(meeting, mb)
    table = problem if item.problem else ordinary
    w = meeting.hidden.priorities[item.speaker][TOPICS.index(item.topic)]
    total = 0.0
    for m in moves:
        v = table[m.kind]
        if m.kind == "push_back" and w < 1 / len(TOPICS) and not item.problem:
            v = mb.board.push_back_unloved  # pushing back on what the asker cares little for
        total += v
    return _clamp(total, 1.0)


def raw_strength_public(
    meeting: Meeting, item: Item, moves: tuple[Move, ...], mb: MeetingsBalance
) -> float:
    """The moves' fixed effects from the published table only (no hidden weight): what a
    speaker's shown reaction is worded from (59.5)."""
    ordinary, problem = _tables(meeting, mb)
    table = problem if item.problem else ordinary
    return _clamp(sum(table[m.kind] for m in moves), 1.0)


def scaled(
    meeting: Meeting, strength: float, moves: tuple[Move, ...], mb: MeetingsBalance
) -> float:
    """The founder's factor: x factor on a gain, x (lo + hi - factor) on a loss; a strong
    persona trait multiplies what suits it (beloved: gains; ruthless: a push-back); and the
    impression the founder makes, `skill.impression` x (factor - 1), on every answer."""
    f = meeting.hidden.skill
    lo, hi = mb.skill.band.lo, mb.skill.band.hi
    if strength >= 0:
        out = strength * f
        if "beloved" in meeting.persona:
            out *= mb.skill.persona_mult
    else:
        out = strength * (lo + hi - f)
        if "ruthless" in meeting.persona and any(m.kind == "push_back" for m in moves):
            out /= mb.skill.persona_mult
    # the founder's manner colours every answer: above factor 1 it adds, below it costs (59.4)
    return out + mb.skill.impression * (f - 1)


def cred_mult(meeting: Meeting, mb: MeetingsBalance) -> float:
    """59.2: positive effects of calls and investor days are whole from `full_at` credibility
    and halved at or below `half_at` (linear between)."""
    cb = mb.credibility
    c = meeting.credibility
    if c >= cb.full_at:
        return 1.0
    if c <= cb.half_at:
        return 1 / 2
    return 1 / 2 + (c - cb.half_at) / (cb.full_at - cb.half_at) / 2


def play_item(meeting: Meeting, claimed: tuple[Move, ...], mb: MeetingsBalance) -> Meeting:
    """One answer to the next item; after the last, the meeting is done and its effects set."""
    if meeting.status != "open":
        raise MeetingRuleError(f"this meeting is over ({meeting.status})")
    item = meeting.next_item
    if item is None:
        raise MeetingRuleError("the agenda is finished")
    moves = check_moves(meeting, item, claimed, mb.max_moves)
    kinds = {m.kind for m in moves}
    strength = raw_strength(meeting, item, moves, mb)
    commitment: Commitment | None = None
    change, reaffirmed = 0, False
    deadline = meeting.period_turn + 2  # tunable-exempt: the quarter's last month
    guided = kinds & set(GUIDANCE_MOVES)
    if guided and item.figure is not None and meeting.guidance_base is not None:
        move = next(iter(guided))
        change, reaffirmed = CHANGE[move], move == "reaffirm"
        level = round(meeting.guidance_base[0] * (1 + change * mb.call.guidance_step))
        commitment = Commitment(
            "guidance",
            "revenue",
            level,
            meeting.guidance_base[0],
            deadline,
            f"revenue of at least {money_words(level)} (guidance)",
        )
    elif item.figure is not None and (
        ("commit" in kinds and meeting.kind == "board") or "promise" in kinds
    ):
        kind: CommitmentKind = "commitment" if meeting.kind == "board" else "guidance"
        commitment = Commitment(
            kind,
            item.figure.metric,
            item.figure.value,
            item.figure.value,
            deadline,
            item.figure.words,
        )
    cred = 0.0
    if meeting.kind == "call" and item.problem and "deflect" in kinds:
        cred = -mb.call.deflect_cred
    answer = Answer(
        n=item.n,
        claimed=claimed,
        moves=moves,
        strength=strength,
        commitment=commitment,
        guidance_change=change,
        reaffirmed=reaffirmed,
        credibility=cred,
    )
    out = replace(meeting, answers=(*meeting.answers, answer))
    if out.next_item is None:
        out = replace(out, status="done", effects=effects(out, mb))
    return out


def effects(meeting: Meeting, mb: MeetingsBalance) -> Effects:
    """What the meeting did, every total within its bound (59.1-59.3)."""
    items = {i.n: i for i in meeting.items}
    commitments = tuple(a.commitment for a in meeting.answers if a.commitment is not None)
    if meeting.kind == "board":
        deltas = [0.0] * len(meeting.speakers)
        for a in meeting.answers:
            item = items[a.n]
            s = scaled(meeting, a.strength, a.moves, mb) * mb.board.item_points
            for i in range(len(meeting.speakers)):
                share = 1.0 if i == item.speaker else mb.board.spill
                deltas[i] += (
                    s * share * relevance(meeting, i, item, mb) * meeting.hidden.receptiveness[i]
                )
        deltas = [_clamp(d, mb.board.step) for d in deltas]
        growth = TOPICS.index("growth")
        votes = []
        for i, sp in enumerate(meeting.speakers):
            after = (sp.confidence or 0.0) + deltas[i]
            tilt = mb.board.vote_priority * (len(TOPICS) * meeting.hidden.priorities[i][growth] - 1)
            votes.append((i, after + tilt >= mb.board.vote_at))
        return Effects(
            confidence=tuple(
                (sp.seat_id, round(d, POINT_DIGITS))
                for sp, d in zip(meeting.speakers, deltas, strict=True)
                if sp.seat_id is not None
            ),
            commitments=commitments,
            votes=tuple(votes),
        )
    pos = cred_mult(meeting, mb)

    def gain(v: float) -> float:
        return v * pos if v > 0 else v

    if meeting.kind == "call":
        cb = mb.call
        sentiment = 0.0
        targets = [0.0] * len(meeting.speakers)
        for a in meeting.answers:
            item = items[a.n]
            s = gain(scaled(meeting, a.strength, a.moves, mb))
            r = (
                relevance(meeting, item.speaker, item, mb)
                * meeting.hidden.receptiveness[item.speaker]
            )
            sentiment += s * cb.item_share * r
            targets[item.speaker] += s * cb.target_share * r
        guidance = None
        guided = [a for a in meeting.answers if a.guidance_change or a.reaffirmed]
        if guided and meeting.guidance_base is not None:
            last = guided[-1]
            rev = round(meeting.guidance_base[0] * (1 + last.guidance_change * cb.guidance_step))
            guidance = (rev, meeting.guidance_base[1])
        return Effects(
            sentiment=round(_clamp(sentiment, cb.step), SHARE_DIGITS),
            targets=tuple(
                (sp.analyst_index, round(_clamp(t, cb.target_step), SHARE_DIGITS))
                for sp, t in zip(meeting.speakers, targets, strict=True)
                if sp.analyst_index is not None and t
            ),
            credibility=round(sum(a.credibility for a in meeting.answers), POINT_DIGITS),
            commitments=commitments,
            guidance=guidance,
        )
    d = mb.investor_day
    econ = meeting.plan.economics if meeting.plan is not None else 0.0
    sentiment = gain(econ) * d.economics_share
    cred = gain(econ) * d.economics_cred
    for a in meeting.answers:
        item = items[a.n]
        s = gain(scaled(meeting, a.strength, a.moves, mb))
        r = relevance(meeting, item.speaker, item, mb) * meeting.hidden.receptiveness[item.speaker]
        sentiment += s * d.item_share * r
        cred += s * d.item_cred * r
    return Effects(
        sentiment=round(_clamp(sentiment, d.step), SHARE_DIGITS),
        credibility=round(_clamp(cred, d.cred_step), POINT_DIGITS),
    )


def skip(meeting: Meeting) -> Meeting:
    """Skipping gives today's outcome: nothing the meeting would have moved moves (59)."""
    if meeting.status != "open":
        raise MeetingRuleError(f"this meeting is over ({meeting.status})")
    return replace(meeting, status="skipped", effects=None)


def replay(meeting: Meeting, rounds: tuple[tuple[Move, ...], ...], mb: MeetingsBalance) -> Meeting:
    """The meeting after stored answers (their scored moves): no LLM, same result."""
    for claimed in rounds:
        meeting = play_item(meeting, claimed, mb)
    return meeting
