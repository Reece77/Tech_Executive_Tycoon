"""The negotiation engine (docs/formulas.md 58.2-58.4): zones, rounds and outcomes. Pure: a
negotiation and the round's offer and moves in, a new negotiation out. The LLM's part ends at
the moves (validated JSON, ADR-0023); everything here is the engine's, so a sequence of moves
always gives the same result and a replay needs no LLM.

Positions: for each term, x = 0 at the counterpart's reservation (the worst it accepts) and 1
at its aspiration (where it opens); x < 0 is outside its zone. Its demand `level` starts at 1
and each round falls by the round's concession, at most `move_step`, never below 0, so no
outcome is ever worse for it than its reservation."""

from __future__ import annotations

import math
from dataclasses import replace
from fractions import Fraction

import numpy as np

from tst.sim.data_models import Balance
from tst.sim.negotiation.config import DEAL_KINDS, DealKind, NegotiationBalance
from tst.sim.negotiation.models import (
    BP,
    DealRef,
    Hidden,
    Mood,
    Move,
    Negotiation,
    Reason,
    Round,
    RoundOutcome,
    TermSpec,
)
from tst.sim.rng import RngFactory

MOOD_OPEN = 3  # tunable-exempt: patience rounds left from which it reads "open" (2 firm, 1 final)
FAR = 0.30  # tunable-exempt: share of the zone between offer and demand that reads "far apart"
NEAR = 0.15  # tunable-exempt: ...and "close"
SCORE_MAX = 20.0  # tunable-exempt: the attribute scale (1-20)


def kind_index(kind: DealKind) -> int:
    return DEAL_KINDS.index(kind)


def draws(rng: RngFactory, turn: int, ref: DealRef) -> np.random.Generator:
    """The deal's one generator (stream `negotiation`, key (kind index, *deal key); ADR-0013):
    drawn when talks open, in that month."""
    return rng.stream(turn, "negotiation", kind_index(ref.kind), *ref.key)


def skill_factor(skills: dict[str, float], b: NegotiationBalance) -> float:
    """58.3: the negotiator's weighted score (1-20) mapped onto the skill band."""
    score = sum(skills.get(k, 1.0) * w for k, w in b.skill.weights.items())
    lo, hi = b.skill.band.lo, b.skill.band.hi
    return lo + (hi - lo) * (min(max(score, 1.0), SCORE_MAX) - 1.0) / (SCORE_MAX - 1.0)


NICE = (5, 2, 1)  # tunable-exempt: steps are 1, 2 or 5 x a power of ten (round figures)


def step_of(median: int, b: NegotiationBalance) -> int:
    """The rounding step of shown values: `shown_round` of the median, down to a round figure
    (1, 2 or 5 x a power of ten: $20,000 on a $1M deal, 200 bp on a quote), at least 1."""
    raw = Fraction(abs(median)) * Fraction(str(b.shown_round))
    if raw < 1:
        return 1
    power = 10 ** (len(str(int(raw))) - 1)
    return next(n * power for n in NICE if n * power <= raw)


def _favour(term: TermSpec, value: Fraction, step: int) -> int:
    """`value` rounded to `step` in the counterpart's favour (up when the player wants lower)."""
    q = value / step
    n = math.ceil(q) if term.wants == "lower" else math.floor(q)
    return max(1, n * step)


def _outward(lo: Fraction, hi: Fraction, step: int) -> tuple[int, int]:
    return max(1, math.floor(lo / step) * step), max(1, math.ceil(hi / step) * step)


def position(neg: Negotiation, t: int, value: int) -> float:
    """x of a value on term t: 0 at the reservation, 1 at the aspiration."""
    h = neg.hidden
    a, r = h.aspiration[t], h.reservation[t]
    if a == r:
        return 1.0 if value == r else (-1.0 if _worse(neg.terms[t], value, r) else 1.0)
    return float(Fraction(value - r, a - r))


def _worse(term: TermSpec, value: int, than: int) -> bool:
    """Worse for the counterpart (better for the player) than `than`."""
    return value < than if term.wants == "lower" else value > than


def shown_at(neg: Negotiation, level: float, b: NegotiationBalance) -> tuple[int, ...]:
    """The counterpart's offer at demand `level`, as shown (rounded in its favour)."""
    h = neg.hidden
    out = []
    for t, term in enumerate(neg.terms):
        exact = Fraction(h.reservation[t]) + Fraction(level) * (h.aspiration[t] - h.reservation[t])
        out.append(_favour(term, exact, step_of(h.medians[t], b)))
    return tuple(out)


def open_negotiation(
    ref: DealRef,
    rng: RngFactory,
    turn: int,
    skill: float,
    persona: tuple[str, ...],
    relationship: int,
    balance: Balance,
) -> Negotiation:
    """58.2: the counterpart's zone, patience, priorities and openness, drawn for this deal."""
    b = balance.negotiation
    gen = draws(rng, turn, ref)
    n = len(ref.terms)
    spread_u = [float(gen.random()) for _ in range(n)]
    patience = int(gen.integers(int(b.patience.lo), int(b.patience.hi), endpoint=True))
    weights = [float(gen.random()) + 0.5 for _ in range(n)]  # tunable-exempt: no zero weight
    openness = float(gen.random())
    offsets = tuple(float(gen.uniform(-1.0, 1.0)) for _ in range(n))
    total = sum(weights)
    asp: list[int] = []
    res: list[int] = []
    medians: list[int] = []
    for t, term in enumerate(ref.terms):
        if ref.zones is not None:
            a, r = ref.zones[t]
            asp.append(a)
            res.append(r)
            medians.append((a + r) // 2)
            continue
        p = ref.medians[t]
        jitter = 1 + b.spread_jitter * (2 * spread_u[t] - 1)
        half = Fraction(abs(p)) * Fraction(str(b.spread[ref.kind])) * Fraction(jitter)
        floor = Fraction(abs(p) * b.min_spread_bp, BP)
        d = max(1, round(max(half, floor)))
        side = 1 if term.wants == "lower" else -1
        asp.append(p + side * d)
        res.append(max(1, p - side * d))
        medians.append(p)
    hidden = Hidden(
        aspiration=tuple(asp),
        reservation=tuple(res),
        medians=tuple(medians),
        patience=patience,
        priorities=tuple(w / total for w in weights),
        openness=openness,
        offsets=offsets,
        skill=skill,
    )
    neg = Negotiation(
        kind=ref.kind,
        subject=ref.subject,
        terms=ref.terms,
        counterpart=ref.counterpart,
        facts=ref.facts,
        persona=persona,
        hidden=hidden,
        level=1.0,
        patience_left=patience,
        counter=(),
        opening=(),
        relationship_start=relationship,
        relationship=relationship,
    )
    opening = shown_at(neg, 1.0, b)
    return replace(neg, counter=opening, opening=opening)


def revealed(neg: Negotiation, b: NegotiationBalance) -> tuple[tuple[int, int], ...]:
    """The ranges the reservation is shown in (58.2): wide at the opening, narrowing each round
    by the counterpart's openness, narrower for a better negotiator; the reservation always lies
    inside, never at a known place in it."""
    h = neg.hidden
    rounds = len(neg.rounds)
    out = []
    for t in range(len(neg.terms)):
        zone = abs(h.aspiration[t] - h.reservation[t])
        width = b.range.start * (1 - b.range.narrow * h.openness) ** rounds
        # a better negotiator sees it narrower: x (lo + hi - factor) ^ power (1.2 shows 0.8^p)
        width *= (b.skill.band.lo + b.skill.band.hi - h.skill) ** b.range.skill_power
        half = Fraction(max(width, b.range.floor)) * zone
        centre = Fraction(h.reservation[t]) + Fraction(h.offsets[t] * b.range.centre) * half
        out.append(_outward(centre - half, centre + half, step_of(h.medians[t], b)))
    return tuple(out)


# --- A round (58.3) ---------------------------------------------------------------------------


def _moved_toward(term: TermSpec, before: int, after: int) -> bool:
    """The player gave ground on the term (toward the counterpart)."""
    return after > before if term.wants == "lower" else after < before


def check_moves(
    neg: Negotiation, offer: tuple[int, ...], claimed: tuple[Move, ...], b: NegotiationBalance
) -> tuple[Move, ...]:
    """The engine's checks on scored moves: a move that the offer or the facts don't bear out
    is `neutral` (58.3). At most `max_moves`, one of each kind."""
    prev = neg.offer if neg.offer is not None else neg.counter
    demand = neg.level
    y = utility(neg, offer)
    out: list[Move] = []
    seen: set[str] = set()
    for m in claimed:
        if len(out) >= b.max_moves:
            break
        if m.kind in seen:
            continue
        seen.add(m.kind)
        ok = False
        n = len(neg.terms)
        if m.kind == "concede":
            ok = (
                m.term is not None
                and 0 <= m.term < n
                and neg.offer is not None
                and _moved_toward(neg.terms[m.term], prev[m.term], offer[m.term])
            )
        elif m.kind == "anchor":
            ok = y <= demand - b.anchor_gap
        elif m.kind == "justify":
            ok = (
                m.fact is not None and 0 <= m.fact < len(neg.facts) and m.fact not in neg.used_facts
            )
        elif m.kind == "package":
            ok = (
                n >= 2  # tunable-exempt: a trade needs two terms
                and neg.offer is not None
                and m.term is not None
                and m.other is not None
                and m.term != m.other
                and 0 <= m.term < n
                and 0 <= m.other < n
                and _moved_toward(neg.terms[m.term], prev[m.term], offer[m.term])
                and _moved_toward(neg.terms[m.other], offer[m.other], prev[m.other])
            )
        elif m.kind in ("appeal", "threaten_walk", "close", "neutral"):
            ok = True
        out.append(m if ok else Move("neutral"))
    return tuple(out) or (Move("neutral"),)


def utility(neg: Negotiation, offer: tuple[int, ...]) -> float:
    """The counterpart's value of an offer: its priorities' weighted positions."""
    return sum(
        w * position(neg, t, v)
        for t, (w, v) in enumerate(zip(neg.hidden.priorities, offer, strict=True))
    )


def inside(neg: Negotiation, offer: tuple[int, ...]) -> bool:
    return all(position(neg, t, v) >= 0 for t, v in enumerate(offer))


def _mult(neg: Negotiation, kind: str, b: NegotiationBalance) -> float:
    """The negotiator's factor on a move: skill, a suiting persona trait (32.4), and for an
    appeal the relationship; always within the skill band."""
    f = neg.hidden.skill
    if kind in ("threaten_walk", "anchor") and "ruthless" in neg.persona:
        f *= b.skill.persona_mult
    if kind == "appeal" and "beloved" in neg.persona:
        f *= b.skill.persona_mult
    f = min(max(f, b.skill.band.lo), b.skill.band.hi)
    if kind == "appeal":
        f *= max(0.0, 1 + neg.relationship / b.relationship_ceiling)
    return f


def _mood(patience_left: int) -> Mood:
    if patience_left >= MOOD_OPEN:
        return "open"
    return "firm" if patience_left == MOOD_OPEN - 1 else "final"


def _clamp(v: int, lo: int, hi: int) -> int:
    return min(max(v, lo), hi)


def check_offer(neg: Negotiation, offer: tuple[int, ...]) -> None:
    from tst.sim.errors import NegotiationRuleError

    if neg.status != "open":
        raise NegotiationRuleError(f"these talks are over ({neg.status})")
    if len(offer) != len(neg.terms) or any(v <= 0 for v in offer):
        raise NegotiationRuleError(f"an offer gives {len(neg.terms)} positive values")


def play_round(
    neg: Negotiation, offer: tuple[int, ...], claimed: tuple[Move, ...], b: NegotiationBalance
) -> Negotiation:
    """One round: the moves' fixed effects on the counterpart's demand (at most move_step of
    the zone), patience (+/-1) and relationship (+/-2); then it agrees, walks or counters."""
    check_offer(neg, offer)
    moves = check_moves(neg, offer, claimed, b)
    kinds = {m.kind for m in moves}
    y = utility(neg, offer)
    concession = sum(b.effects[m.kind].concession * _mult(neg, m.kind, b) for m in moves)
    step = min(b.move_step, b.move_step * concession)
    level = max(0.0, neg.level - step)
    patience_delta = 0
    for m in moves:
        p = b.effects[m.kind].patience
        if m.kind == "appeal" and neg.relationship < b.appeal_good:
            p = min(p, 0)
        patience_delta += p
    patience_left = neg.patience_left - 1 + _clamp(patience_delta, -1, 1)
    rel_change = _clamp(sum(b.effects[m.kind].relationship for m in moves), -2, 2)
    n = len(neg.rounds) + 1
    used = neg.used_facts + tuple(
        m.fact for m in moves if m.kind == "justify" and m.fact is not None
    )
    outcome: RoundOutcome
    reason: Reason
    final: tuple[int, ...] | None = None
    tolerance = b.close_tolerance if "close" in kinds else b.accept_tolerance
    if "threaten_walk" in kinds and not inside(neg, offer):
        outcome, reason = "walked", "walked_threat"
    elif inside(neg, offer) and y >= level - tolerance:
        outcome, reason, final = "agreed", "accepted", offer
    elif patience_left <= 0 or n >= b.max_rounds:
        outcome, reason = "walked", "walked_patience"
    elif "close" in kinds:
        patience_left = min(patience_left, 1)
        outcome, reason = "final", "final_offer"
    else:
        gap = level - y
        outcome = "countered"
        reason = "far_apart" if gap > FAR else ("close" if gap <= NEAR else "moving")
        if patience_left == 1:
            reason = "final_offer"
    counter = neg.counter if outcome in ("agreed", "walked") else shown_at(neg, level, b)
    rnd = Round(
        n=n,
        offer=offer,
        claimed=claimed,
        moves=moves,
        counter_before=neg.counter,
        counter=counter,
        outcome=outcome,
        reason=reason,
        mood=_mood(max(patience_left, 1)) if outcome != "walked" else "final",
        relationship_change=rel_change,
    )
    status = {"agreed": "agreed", "walked": "walked"}.get(outcome, "open")
    return replace(
        neg,
        level=level,
        patience_left=max(patience_left, 0),
        counter=counter,
        offer=offer,
        rounds=(*neg.rounds, rnd),
        status=status,  # type: ignore[arg-type]
        final=final,
        relationship=neg.relationship + rel_change,
        used_facts=used,
    )


def accept_counter(neg: Negotiation) -> Negotiation:
    """The player takes the counterpart's offer as shown (inside its zone by construction)."""
    from tst.sim.errors import NegotiationRuleError

    if neg.status != "open":
        raise NegotiationRuleError(f"these talks are over ({neg.status})")
    return replace(neg, status="agreed", final=neg.counter)


def skip(neg: Negotiation) -> Negotiation:
    """58.4: the median outcome, today's terms, at any time while the talks are open."""
    from tst.sim.errors import NegotiationRuleError

    if neg.status != "open":
        raise NegotiationRuleError(f"these talks are over ({neg.status})")
    return replace(neg, status="skipped", final=neg.hidden.medians)


def replay(
    neg: Negotiation,
    rounds: tuple[tuple[tuple[int, ...], tuple[Move, ...]], ...],
    b: NegotiationBalance,
) -> Negotiation:
    """The negotiation after stored rounds (offer, scored moves): no LLM, same result."""
    for offer, moves in rounds:
        neg = play_round(neg, offer, moves, b)
    return neg


def zone_share(neg: Negotiation, terms: tuple[int, ...]) -> float:
    """How far terms sit from the median toward the reservation, as a share of the zone's
    width (aspiration to reservation): + better for the player than skip, - worse (58.5)."""
    h = neg.hidden
    shares = []
    for t, v in enumerate(terms):
        width = abs(h.aspiration[t] - h.reservation[t])
        if width == 0:
            shares.append(0.0)
            continue
        gain = (h.medians[t] - v) if neg.terms[t].wants == "lower" else (v - h.medians[t])
        shares.append(float(Fraction(gain, width)))
    return sum(w * s for w, s in zip(h.priorities, shares, strict=True))
