"""The talks engine (docs/formulas.md 61.1-61.2): moves, their bounded effects and the talk's
outcome. Pure: a talk and a question's scored moves in, a new talk out. The LLM's part ends at
the moves (validated JSON, ADR-0023); everything here is the engine's, so the same moves always
give the same effects and a replay needs no LLM.

Each answer has a published strength in -1..1: the sum of its checked moves' fixed effects
(a one-to-one's topic table where it differs). The hidden scaling then applies: a person's
personality factor by move (true ego, ambition, loyalty), the founder's (or delegate's) factor
(a gain x factor, a loss x (lo + hi - factor)) and the other side's receptiveness at that
question. Totals are clamped to each kind's step, so no talk moves anything further than 61
allows."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from tst.sim.errors import TalkRuleError
from tst.sim.talks.config import MOVES, TONE_OF, TalksBalance
from tst.sim.talks.models import Answer, Effects, Move, Question, Talk

POINT_DIGITS = 4  # tunable-exempt: stored precision of points and shares
TONES_BY_PRIORITY = ("measured", "bold", "deflect")  # a tie goes to the measured answer (29.1)
CANDOUR = ("apologise", "take_responsibility")
DEFLECTION = ("deflect", "no_comment")


def _clamp(v: float, bound: float) -> float:
    return max(-bound, min(bound, v))


def check_moves(
    talk: Talk, q: Question, claimed: tuple[Move, ...], max_moves: int
) -> tuple[Move, ...]:
    """The engine's checks on scored moves: one not in the kind's set, or that the question
    does not bear out, is `neutral`. One of each kind, at most `max_moves`."""
    allowed = MOVES[talk.kind]
    out: list[Move] = []
    seen: set[str] = set()
    for m in claimed:
        if len(out) >= max_moves:
            break
        kind = m.kind if m.kind in allowed else "neutral"
        if kind in seen:
            continue
        seen.add(kind)
        ok = True
        if kind in ("promise", "promise_promotion"):
            ok = bool(q.offer) and talk.offer is not None
        elif kind == "attack_rival":
            ok = bool(q.rival)
        elif kind == "offer_equity":
            ok = talk.subject.equity_ok
        result = Move(kind) if ok else Move("neutral")
        if result not in out:  # an unfounded move counts once, as neutral
            out.append(result)
    return tuple(out) or (Move("neutral"),)


def _table(talk: Talk, q: Question, tb: TalksBalance) -> dict[str, float]:
    if talk.kind == "interview":
        return tb.interview.effects
    if talk.kind == "crisis":
        return tb.crisis.effects
    return {**tb.one_to_one.effects, **tb.one_to_one.topic_effects.get(q.topic, {})}


def strength_public(talk: Talk, q: Question, moves: tuple[Move, ...], tb: TalksBalance) -> float:
    """The moves' fixed effects from the published tables only (no hidden factor): what the
    other side's shown reaction is worded from (61.3 target 5)."""
    table = _table(talk, q, tb)
    return _clamp(sum(table[m.kind] for m in moves), 1.0)


def _hidden_strength(talk: Talk, q: Question, moves: tuple[Move, ...], tb: TalksBalance) -> float:
    """A one-to-one's moves x the person's personality factor by move, then the founder's."""
    table = _table(talk, q, tb)
    traits = dict(talk.hidden.traits)
    raw = _clamp(sum(table[m.kind] * traits.get(m.kind, 1.0) for m in moves), 1.0)
    f = talk.hidden.skill
    lo, hi = tb.skill.band.lo, tb.skill.band.hi
    return raw * f if raw >= 0 else raw * (lo + hi - f)


def play(talk: Talk, claimed: tuple[Move, ...], tb: TalksBalance) -> Talk:
    """One answer to the next question; after the last, the talk is done and its effects set."""
    if talk.status != "open":
        raise TalkRuleError(f"this talk is over ({talk.status})")
    q = talk.next_question
    if q is None:
        raise TalkRuleError("every question has been answered")
    moves = check_moves(talk, q, claimed, tb.max_moves)
    answer = Answer(q.n, claimed, moves, strength_public(talk, q, moves, tb))
    out = replace(talk, answers=(*talk.answers, answer))
    if out.next_question is None:
        out = replace(out, status="done", effects=effects(out, tb))
    return out


def tone(talk: Talk) -> str:
    """29.1's tone the answers add up to: the most used, a tie to measured."""
    counts = Counter(TONE_OF[m.kind] for a in talk.answers for m in a.moves if m.kind != "neutral")
    return max(TONES_BY_PRIORITY, key=lambda t: (counts[t], -TONES_BY_PRIORITY.index(t)))


def _used(talk: Talk, kinds: tuple[str, ...]) -> int:
    return sum(1 for a in talk.answers for m in a.moves if m.kind in kinds)


def _scaled(talk: Talk, tb: TalksBalance) -> list[float]:
    """Each answer's effect after the hidden scaling (press: founder and receptiveness)."""
    qs = {q.n: q for q in talk.questions}
    out = []
    for i, a in enumerate(talk.answers):
        s = _hidden_strength(talk, qs[a.n], a.moves, tb)
        out.append(s * talk.hidden.receptiveness[i])
    return out


def effects(talk: Talk, tb: TalksBalance) -> Effects:
    """What the talk did, every total within its bound (61.1-61.2)."""
    scaled = _scaled(talk, tb)
    promised = talk.offer if _used(talk, ("promise", "promise_promotion")) else None
    if talk.kind == "interview" and tone(talk) == "deflect":
        promised = None  # 29.2: a promise is made with a bold or measured answer
    if talk.kind in ("interview", "crisis"):
        a = talk.audience
        if talk.kind == "interview":
            cfg = tb.interview
            stance = cfg.stances.get(talk.counterpart.stance, 1.0)
            scaled = [s * stance if s > 0 else s for s in scaled]
            persona = None
            inspection = 0.0
        else:
            c = tb.crisis
            candour, deflection = _used(talk, CANDOUR), _used(talk, DEFLECTION)
            n = max(1, len(talk.answers))
            persona = None
            if candour > deflection:
                persona = ("beloved", round(c.persona_points * min(1.0, candour / n), POINT_DIGITS))
            elif deflection > candour:
                persona = (
                    "ruthless",
                    round(c.persona_points * min(1.0, deflection / n), POINT_DIGITS),
                )
            inspection = c.deflect_inspection if deflection and talk.subject.medical else 0.0
        cfg2 = tb.interview if talk.kind == "interview" else tb.crisis
        total = sum(scaled)
        return Effects(
            tone=tone(talk) if talk.subject.event_id is not None else "",
            brand_pct=round(_clamp(total * cfg2.brand_share, cfg2.brand_step) * a, POINT_DIGITS),
            brand_months=cfg2.brand_months,
            credibility=round(_clamp(total * cfg2.cred_share, cfg2.cred_step) * a, POINT_DIGITS),
            persona=persona,
            inspection_chance=inspection,
            promise=promised,
        )
    o = tb.one_to_one
    total = sum(scaled)
    qs = {q.n: q for q in talk.questions}
    retain = 0.0
    if talk.subject.approach_id is not None:
        on_approach = [
            s for x, s in zip(talk.answers, scaled, strict=True) if qs[x.n].topic == "approach"
        ]
        best = max(on_approach, default=0.0)
        retain = min(o.retain_cap, o.retain_base * max(0.0, best))
    return Effects(
        morale=round(_clamp(total * o.morale_points, o.morale_step), POINT_DIGITS),
        loyalty=round(_clamp(total * o.loyalty_points, o.loyalty_step), POINT_DIGITS),
        stress=o.push_stress * _used(talk, ("push_harder",)),
        retain_chance=round(retain, POINT_DIGITS),
        offer_raise=_used(talk, ("offer_raise",)) > 0,
        equity_bp=o.equity_bp if _used(talk, ("offer_equity",)) else 0,
        reveal=_used(talk, ("listen",)) > 0,
        promise=promised,
    )


def skip(talk: Talk) -> Talk:
    """Skipping gives today's outcome: nothing the talk would have moved moves (61)."""
    if talk.status != "open":
        raise TalkRuleError(f"this talk is over ({talk.status})")
    return replace(talk, status="skipped", effects=None)


def replay(talk: Talk, rounds: tuple[tuple[Move, ...], ...], tb: TalksBalance) -> Talk:
    """The talk after stored answers (their scored moves): no LLM, same result."""
    for claimed in rounds:
        talk = play(talk, claimed, tb)
    return talk


def delegated_moves(talk: Talk) -> tuple[tuple[Move, ...], ...]:
    """A seat holder's one-to-one by skip (61.2): they listen and praise at every question;
    their own factor (their skills and a draw) scales it, in place of the founder's."""
    return tuple((Move("listen"), Move("praise")) for _ in talk.questions)
