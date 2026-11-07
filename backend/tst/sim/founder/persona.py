"""Persona (docs/formulas.md 32.4, M24): four public traits, 0-100, raised by the founder's
choices and drifting back toward persona.start. Effects apply at persona.effect_at or more.
The month's sources are read from records stamped with the month (moments answered,
promises resolved, launches, eras, rankings, offers, loans); actions in the month that
leave no record (raises, hostile tenders) are noted as they happen."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance
from tst.sim.founder.config import SOURCES, TRAITS
from tst.sim.founder.models import FounderLife
from tst.sim.state import GameState, life_of, with_life

TRAIT_MAX = 100.0  # tunable-exempt: traits are 0-100

SOURCE_WORDS: dict[str, str] = {
    "era_caused": "caused an era",
    "bold_answer": "a bold answer to the press",
    "new_category": "a launch in a new category",
    "innovative_top": "a top place in Most innovative",
    "layoffs": "layoffs",
    "hostile_bid": "a hostile bid",
    "poach": "hired from a rival",
    "broke_no_layoffs": "broke a no-layoffs promise",
    "kept_promise": "kept a promise",
    "places_top": "a top place in Best places to work",
    "raises": "raises across the company",
    "broken_promise": "broke a promise",
    "covenant_breach": "a covenant breach",
    "failed_tender": "a failed tender",
    "pushed_on": "pushed on through burnout",
}


def _with_traits(life: FounderLife, values: dict[str, float]) -> FounderLife:
    return replace(
        life,
        visionary=values.get("visionary", life.visionary),
        ruthless=values.get("ruthless", life.ruthless),
        beloved=values.get("beloved", life.beloved),
        reckless=values.get("reckless", life.reckless),
    )


def raise_trait(
    life: FounderLife, trait: str, value: float, why: str, turn: int, balance: Balance
) -> FounderLife:
    if trait not in TRAITS or not value:
        return life
    old = life.trait(trait)
    new = max(0.0, min(TRAIT_MAX, old + value))
    causes = (*life.trait_causes, (turn, trait, new - old, why))[-balance.persona.history :]
    return _with_traits(replace(life, trait_causes=causes), {trait: new})


def apply_source(
    life: FounderLife, source: str, turn: int, balance: Balance, n: int = 1
) -> FounderLife:
    trait = SOURCES[source]
    return raise_trait(
        life, trait, balance.persona.sources[source] * n, SOURCE_WORDS[source], turn, balance
    )


def note(state: GameState, person_id: int, source: str, balance: Balance) -> GameState:
    """A source that happened in an action (a hostile tender, a failed one, a raise)."""
    from tst.sim.founder.stress import new_life

    life = life_of(state, person_id) or new_life(person_id, balance)
    return with_life(state, apply_source(life, source, state.turn, balance))


def drift(life: FounderLife, balance: Balance) -> FounderLife:
    pb = balance.persona
    moved = {}
    for trait in TRAITS:
        value = life.trait(trait)
        gap = pb.start - value
        if gap:
            moved[trait] = value + max(-pb.drift, min(pb.drift, gap))
    return _with_traits(life, moved) if moved else life


def strong(state: GameState, company_id: int, trait: str, balance: Balance) -> bool:
    """The company's founder has `trait` at persona.effect_at or more (32.4's effects)."""
    founder = state.founder_of(company_id)
    if founder is None:
        return False
    life = life_of(state, founder.id)
    return life is not None and life.trait(trait) >= balance.persona.effect_at


PUBLIC_WORDS: dict[str, str] = {  # how the press describes the strongest trait
    "visionary": "a visionary",
    "ruthless": "ruthless",
    "beloved": "well liked",
    "reckless": "reckless",
}
UNKNOWN_WORDS = "little known to the public"


def public_words(state: GameState, company_id: int, balance: Balance) -> str:
    """The founder's strongest trait in the press's words (32.4), or "little known" while
    no trait is above persona.start. Public: the traits are shown on the profile."""
    founder = state.founder_of(company_id)
    life = life_of(state, founder.id) if founder is not None else None
    if life is None:
        return UNKNOWN_WORDS
    top = top_trait(life)
    return PUBLIC_WORDS[top] if life.trait(top) > balance.persona.start else UNKNOWN_WORDS


def top_trait(life: FounderLife) -> str:
    """The strongest trait; ties go to the first in TRAITS order."""
    return max(TRAITS, key=lambda t: (life.trait(t), -TRAITS.index(t)))
