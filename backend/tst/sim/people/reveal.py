"""Per-observer knowledge of people (ADR-0007, docs/formulas.md section 4)."""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.people.models import PA_KEY, Person, RevealRecord, RevealState
from tst.sim.rng import RngFactory

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
    hw 0; PA keeps its normal initial hw, formulas.md section 5).
    """
    gen = rng.stream(turn, "reveal", observer_company_id, person.id)
    initial = balance.reveal.initial_hw
    keys = [*data.skill_keys, *data.personality_keys, PA_KEY]
    skill_keys = set(data.skill_keys)
    records = []
    for key in keys:
        offset = float(gen.uniform(OFFSET_LOW, OFFSET_HIGH))
        if key == PA_KEY:
            hw = initial.pa
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
