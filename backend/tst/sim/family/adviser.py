"""The adviser (docs/formulas.md 45.5): the old founder on the board gives an opinion on each
new proposal and pitch, in their voice, from their persona (templates here; an LLM wording
within 16's budget is a follow-up). When the player approves something the adviser opposed,
each voting director's confidence falls by family.adviser_oppose. The adviser retires from
the board at family.adviser_retire_age."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import SCORE_MAX, Balance
from tst.sim.family import rules
from tst.sim.family.models import Opinion
from tst.sim.founder.models import FounderLife
from tst.sim.log import LogItem, inbox_item
from tst.sim.state import GameState, life_of, with_family, with_seat

RISKY: Final = frozenset({"round", "loan", "high"})  # proposal kinds and pitch risks
SUPPORT, OPPOSE = "support", "oppose"
TITLE_MAX: Final = 80  # tunable-exempt: an opinion title's width
APPROVED: Final = frozenset({"approved", "auto_approved", "modified"})

WORDS: Final = {
    ("visionary", SUPPORT): "Go further. This is the kind of bet that built the company.",
    ("visionary", OPPOSE): "Too timid. It spends money without changing what we are.",
    ("ruthless", SUPPORT): "Sensible. It earns its keep; do it and do not look back.",
    ("ruthless", OPPOSE): "Wasteful. I would not have signed it, and neither should you.",
    ("beloved", SUPPORT): "Good for our people and for our name. I would do it.",
    ("beloved", OPPOSE): "Think of the people this lands on. I would not do it.",
    ("reckless", SUPPORT): "Do it now, before anyone else does.",
    ("reckless", OPPOSE): "There is a bolder move than this. Wait for it.",
}


def stance(life: FounderLife | None, risky: bool) -> tuple[str, str]:
    """(stance, voice): a bold adviser (Visionary + Reckless above Ruthless + Beloved)
    backs risky moves and doubts small ones; a cautious one the reverse. The voice is their
    strongest trait (32.4)."""
    if life is None:
        return SUPPORT, "beloved"
    bold = life.visionary + life.reckless >= life.ruthless + life.beloved
    from tst.sim.founder.persona import top_trait

    voice = top_trait(life)
    return (SUPPORT if bold == risky else OPPOSE), voice


def adviser_month(state: GameState, balance: Balance) -> tuple[GameState, list[LogItem]]:
    family = state.family
    if family is None or family.adviser_id is None:
        return state, []
    fb = balance.family
    logs: list[LogItem] = []
    adviser = state.person(family.adviser_id)
    if adviser.age(state.turn) >= fb.adviser_retire_age:
        return retire(state, balance)
    life = life_of(state, adviser.id)
    cid = state.player.id
    seen = {(o.subject, o.subject_id) for o in family.opinions}
    new: list[Opinion] = []
    for p in state.proposals:
        if p.company_id == cid and p.turn == state.turn and ("proposal", p.id) not in seen:
            s, voice = stance(life, p.kind in RISKY)
            new.append(
                Opinion(state.turn, "proposal", p.id, p.text[:TITLE_MAX], s, WORDS[(voice, s)])
            )
    for pt in state.pitches:
        if pt.company_id == cid and pt.turn == state.turn and ("pitch", pt.id) not in seen:
            s, voice = stance(life, pt.risk in RISKY)
            new.append(
                Opinion(state.turn, "pitch", pt.id, pt.title[:TITLE_MAX], s, WORDS[(voice, s)])
            )
    opinions = list(family.opinions) + new
    # Objections the player overruled this month (45.5).
    overruled = 0
    for i, o in enumerate(opinions):
        if o.stance != OPPOSE or o.overruled:
            continue
        if _approved_now(state, o):
            opinions[i] = replace(o, overruled=True)
            overruled += 1
    if overruled:
        for seat in state.board(cid):
            if seat.confidence is not None:
                value = max(0.0, min(SCORE_MAX, seat.confidence - fb.adviser_oppose * overruled))
                state = with_seat(state, replace(seat, confidence=value))
    family = state.family
    assert family is not None
    state = with_family(state, replace(family, opinions=tuple(opinions[-fb.adviser_memory :])))
    for o in new:
        logs.append(
            inbox_item(
                state.turn,
                cid,
                "adviser_opinion",
                name=rules.full_name(adviser),
                stance=o.stance,
                subject=o.title,
                text=o.text,
            )
        )
    return state, logs


def _approved_now(state: GameState, o: Opinion) -> bool:
    if o.subject == "proposal":
        p = next((p for p in state.proposals if p.id == o.subject_id), None)
        return p is not None and p.status == "approved" and p.resolved_turn == state.turn
    if o.subject == "pitch":
        pt = next((p for p in state.pitches if p.id == o.subject_id), None)
        return pt is not None and pt.status in APPROVED and pt.resolved_turn == state.turn
    return False


def opinion_on_one_off(state: GameState, title: str, risky: bool) -> GameState:
    """The adviser's word on a one-off the player takes (a big action): recorded, and if it
    opposes, the board's confidence falls at once (the player went ahead)."""
    family = state.family
    if family is None or family.adviser_id is None:
        return state
    life = life_of(state, family.adviser_id)
    s, voice = stance(life, risky)
    op = Opinion(
        state.turn, "one_off", 0, title[:TITLE_MAX], s, WORDS[(voice, s)], overruled=s == OPPOSE
    )
    return with_family(state, replace(family, opinions=(*family.opinions, op)))


def retire(state: GameState, balance: Balance) -> tuple[GameState, list[LogItem]]:
    """The adviser leaves the board (at family.adviser_retire_age, or by choice)."""
    family = state.family
    if family is None or family.adviser_id is None:
        return state, []
    adviser = state.person(family.adviser_id)
    seats = tuple(s for s in state.seats if s.id != family.adviser_seat_id)
    state = replace(state, seats=seats)
    family = rules.note(
        replace(family, adviser_id=None, adviser_seat_id=None),
        state.turn,
        "adviser_retired",
        f"{rules.full_name(adviser)} retired from the board",
        balance.family.history,
    )
    state = with_family(state, family)
    log = inbox_item(state.turn, state.player.id, "adviser_retired", name=rules.full_name(adviser))
    return state, [log]
