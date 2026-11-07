"""Per-observer knowledge of people (ADR-0007, docs/formulas.md section 4)."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import UnknownKnowledgeActionError
from tst.sim.people.formulas import displayed_range, narrow, narrow_pa
from tst.sim.people.models import PA_KEY, Person, RevealRecord, RevealState
from tst.sim.rng import RngFactory
from tst.sim.scale import ABILITY_MAX, ABILITY_MIN, ATTR_MAX, ATTR_MIN

OFFSET_LOW = -0.5  # tunable-exempt: centre offset o ~ Uniform(-0.5, 0.5) (formulas.md 4)
OFFSET_HIGH = 0.5  # tunable-exempt: centre offset o ~ Uniform(-0.5, 0.5) (formulas.md 4)


def new_reveal_state(
    *,
    observer_company_id: int,
    person: Person,
    turn: int,
    rng: RngFactory,
    data: GameData,
    balance: Balance,
    knows_exactly: bool = False,
) -> RevealState:
    """Create an observer's first knowledge record of a person.

    Offsets come from stream `reveal` keyed (observer, person), one per attribute in order:
    skills (skills.yaml), personality (personality.yaml), then PA. All are drawn even when
    `knows_exactly` (the founding company and its founder: skills and personality start at
    hw 0; PA starts at reveal.founder_pa_hw, formulas.md sections 4-5).
    """
    gen = rng.stream(turn, "reveal", observer_company_id, person.id)
    initial = balance.reveal.initial_hw
    keys = [*data.skill_keys, *data.personality_keys, PA_KEY]
    skill_keys = set(data.skill_keys)
    records = []
    for key in keys:
        offset = float(gen.uniform(OFFSET_LOW, OFFSET_HIGH))
        if key == PA_KEY:  # the founding company reads its own founder's potential better (M2b)
            hw = balance.reveal.founder_pa_hw if knows_exactly else initial.pa
        elif knows_exactly:
            hw = 0.0
        else:
            hw = initial.skill if key in skill_keys else initial.personality
        records.append((key, RevealRecord(hw=hw, offset=offset, last_updated_turn=turn)))
    return RevealState(
        observer_company_id=observer_company_id,
        person_id=person.id,
        attributes=tuple(records),
        profile_revealed_turn=turn if knows_exactly else None,
        revealed_tags=tuple((tag, turn) for tag in person.tags) if knows_exactly else (),
    )


# --- Knowledge actions (formulas.md section 4) ----------------------------------------------

SKILLS = "skills"
PERSONALITY = "personality"
PA = "pa"
# Which attribute groups each action narrows (formulas.md section 4 table).
ACTION_GROUPS: Final = MappingProxyType(
    {
        "job_post_screen": frozenset({SKILLS, PA}),
        "network_intro": frozenset({SKILLS, PERSONALITY, PA}),
        "interview": frozenset({SKILLS, PERSONALITY, PA}),
        "reference_check": frozenset({PERSONALITY, PA}),
        "scouting_month": frozenset({SKILLS, PERSONALITY, PA}),
        "employed_month": frozenset({SKILLS, PERSONALITY, PA}),
    }
)
# Interests and work style are shown exactly after the first of these (formulas.md section 4).
PROFILE_ACTIONS: Final = frozenset({"network_intro", "interview"})


def _group(key: str, skill_keys: frozenset[str]) -> str:
    if key == PA_KEY:
        return PA
    return SKILLS if key in skill_keys else PERSONALITY


def apply_knowledge_action(
    reveal: RevealState,
    action: str,
    scout_judgment: float,
    balance: Balance,
    *,
    turn: int,
    skill_keys: frozenset[str],
) -> RevealState:
    """Narrow every attribute the action applies to: hw <- hw x (1 - strength x scout_factor),
    with PA's own strength and scout factor (formulas.md section 4, M2b).

    Ranges never widen: hw can only shrink. Offsets never change.
    """
    if action not in ACTION_GROUPS:
        raise UnknownKnowledgeActionError(f"unknown knowledge action {action!r}")
    cfg = balance.reveal
    groups = ACTION_GROUPS[action]
    # narrow() is hw x a factor that depends only on the action and the judgment: computed
    # once, and applied as narrow() does (M14 turn time: 41,000 calls a month at 220 staff)
    unit = (
        narrow(1.0, cfg.strength[action], scout_judgment, cfg) if action in cfg.strength else None
    )

    def narrowed(key: str, rec: RevealRecord) -> RevealRecord:
        if _group(key, skill_keys) not in groups:
            return rec
        if key == PA_KEY:  # potential uses its own strength and scout factor (M2b)
            hw = narrow_pa(rec.hw, cfg.pa_strength[action], scout_judgment, cfg)
        else:
            hw = (
                rec.hw * unit
                if unit is not None
                else narrow(rec.hw, cfg.strength[action], scout_judgment, cfg)
            )
        return RevealRecord(hw, rec.offset, turn)

    attributes = tuple((key, narrowed(key, rec)) for key, rec in reveal.attributes)
    profile = reveal.profile_revealed_turn
    if profile is None and action in PROFILE_ACTIONS:
        profile = turn
    return replace(reveal, attributes=attributes, profile_revealed_turn=profile)


def revealed_range(person: Person, reveal: RevealState, attribute: str) -> tuple[int, int]:
    """The (min, max) an observer sees for one of a person's attributes, from true values."""
    rec = reveal.record(attribute)
    if attribute == PA_KEY:
        true_value, lo, hi = person.potential_ability, ABILITY_MIN, ABILITY_MAX
    elif attribute in person.skills:
        true_value, lo, hi = person.skills[attribute], ATTR_MIN, ATTR_MAX
    else:
        true_value, lo, hi = person.personality[attribute], ATTR_MIN, ATTR_MAX
    return displayed_range(true_value, rec.hw, rec.offset, lo, hi)


def shown_rating(person: Person, reveal: RevealState, skills: tuple[str, ...]) -> float:
    """A person's rating as an observer sees it (M7b, formulas.md 17.2): the mean midpoint of
    the displayed ranges of `skills` (their role's primary skills). Displayed values only."""
    mids = [sum(revealed_range(person, reveal, key)) / 2 for key in skills]
    return sum(mids) / len(mids) if mids else 0.0
