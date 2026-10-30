"""Monthly skill growth and aging (docs/formulas.md section 3; turn phase 8).

Applies to everyone with an active or notice employment, including the founder. Age is
derived from birth_turn, so aging needs no update. Noise is multiplicative on the growth
term and comes from stream `growth` keyed by person id: one Normal(0, noise_rel_sd) draw per
role skill (primary and secondary), in skills.yaml order. Skills outside the role draw
nothing and change only by -d(age).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData, band_value
from tst.sim.people.formulas import growth_delta
from tst.sim.people.models import Person, growth_role, role_ability
from tst.sim.rng import RngFactory


def grow_person(
    person: Person,
    turn: int,
    rng: RngFactory,
    data: GameData,
    balance: Balance,
    mentoring: float = 1.0,
) -> Person:
    """One month of growth: role skills grow toward PA, every skill declines with age.

    `mentoring` is the manager's M_growth (formulas.md 13.5); 1 for the founder.
    """
    growth = balance.growth
    role = growth_role(person, data)  # the founder's best fit is recomputed each month
    in_role = set(role.primary) | set(role.secondary)
    ca = role_ability(person.skills, role)
    age = person.age(turn)
    professionalism = person.personality["professionalism"]
    gen = rng.stream(turn, "growth", person.id)

    current = person.skills.as_dict()
    decline = band_value(growth.decline, age)  # growth_delta for a skill outside the role
    changes = {}
    for key in data.skill_keys:
        if key not in in_role:
            changes[key] = current[key] - decline
            continue
        noise = float(gen.normal(0.0, growth.noise_rel_sd))
        delta = growth_delta(
            in_role=True,
            age=age,
            ca=ca,
            pa=person.potential_ability,
            professionalism=professionalism,
            growth=growth,
            noise=noise,
            mentoring=mentoring,
        )
        changes[key] = current[key] + delta
    return replace(person, skills=person.skills.updated(changes))  # updated() clamps
