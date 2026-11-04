"""Executives' report voices (docs/formulas.md 27.2, M13b; data: exec_voices.yaml).

A voice is chosen from the company's displayed view of the executive: the midpoint of a
revealed personality range (ADR-0007), never the true value. The first voice whose rule
matches is used; the last voice has no rule.
"""

from __future__ import annotations

from tst.sim.org.voice_data import Voice
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState


def voice_for(
    state: GameState, company_id: int, person_id: int, voices: tuple[Voice, ...]
) -> Voice:
    """The executive's voice from what the company sees of them (27.2): a trait's displayed
    midpoint, or the last voice when the company has no reveal record."""
    reveal = state.reveal(company_id, person_id)
    person = state.person(person_id)
    for v in voices:
        if v.rule is None:
            return v
        if reveal is None or v.rule.trait not in person.personality:
            continue
        lo, hi = revealed_range(person, reveal, v.rule.trait)
        if v.rule.matches((lo + hi) / 2):
            return v
    return voices[-1]
