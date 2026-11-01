"""Person generation (docs/formulas.md section 2).

The caller passes a `numpy.random.Generator` from the right stream (ADR-0013): candidate
batches use `people_gen` keyed by search id; the founder uses `founder`. Draws happen in this
fixed order, one call each, so a person is reproducible from the generator state:

1. target CA                      Normal(level mean, sd), clipped to ca_clip
2. skills, in skills.yaml order    primary Normal(0, sd_p) / secondary Normal(0, sd_s) /
                                   other Uniform(min, max) -- exactly one draw per skill
3. age                            integer in the level's [min, max]
4. birth month                    integer in [0, 11]
5. potential gap                  Normal(gap_mean(age), pa_gap_sd)
6. personality, then hidden traits Normal(mean, sd) each, in personality.yaml order
7. interest count, then interests count in interest_count; weighted, without replacement
8. work style                     weighted by the role
9. tags, in tags.yaml order       one roll in [0, 10000) per tag, always drawn
10. first name, then last name    uniform from the region's pool

Rescaling the primaries to hit the target CA and the salary expectation draw nothing.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence

import numpy as np

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData, Role, Tag
from tst.sim.geo.formulas import pay_multiplier_bp, talent_bonus
from tst.sim.geo.models import ANYWHERE
from tst.sim.money import BP_DENOMINATOR
from tst.sim.people.formulas import current_ability, pa_gap_mean, salary_expectation_cents
from tst.sim.people.models import HiddenTraits, Person, Personality, Skills
from tst.sim.rng import RngFactory
from tst.sim.scale import (
    ABILITY_MAX,
    ABILITY_PER_ATTR,
    ATTR_MAX,
    ATTR_MIN,
    PRIMARY_WEIGHT,
    SECONDARY_WEIGHT,
    clamp_ability,
    clamp_attr,
)


def _weighted_pick(
    gen: np.random.Generator, weights: Mapping[str, float], keys: Sequence[str]
) -> str:
    w = np.array([weights[k] for k in keys], dtype=float)
    return keys[int(gen.choice(len(keys), p=w / w.sum()))]


def draw_traits(
    gen: np.random.Generator, keys: Sequence[str], balance: Balance
) -> dict[str, float]:
    """Normal(mean, sd) per trait, in the given order (step 6)."""
    people = balance.people
    return {k: float(gen.normal(people.personality_mean, people.personality_sd)) for k in keys}


def draw_interests(
    gen: np.random.Generator, role: Role, data: GameData, balance: Balance
) -> tuple[str, ...]:
    """Count uniform in interest_count, then weighted draws without replacement (step 7)."""
    span = balance.people.interest_count
    count = int(gen.integers(int(span.lo), int(span.hi), endpoint=True))
    keys = data.interest_keys
    w = np.array([role.interest_weights[k] for k in keys], dtype=float)
    count = min(count, int(np.count_nonzero(w)))
    picks = gen.choice(len(keys), size=count, replace=False, p=w / w.sum())
    return tuple(keys[int(i)] for i in picks)


def draw_work_style(gen: np.random.Generator, role: Role, data: GameData) -> str:
    return _weighted_pick(gen, role.work_style_weights, data.work_style_keys)


def tag_chance_bp(tag: Tag, personality: Personality) -> float:
    """base_bp, times the boost multiplier when every boost condition holds (step 7)."""
    boosted = all(c.holds(personality[c.attr]) for c in tag.boost.when)
    return tag.base_bp * (tag.boost.multiplier if boosted else 1)


def draw_tags(
    gen: np.random.Generator, personality: Personality, data: GameData, balance: Balance
) -> tuple[str, ...]:
    """One roll per tag in file order; skip excluded tags; at most max_tags (step 7)."""
    assigned: list[str] = []
    for tag in data.tags:
        roll = int(gen.integers(0, BP_DENOMINATOR))
        if len(assigned) >= balance.people.max_tags:
            continue
        if any(tag.key in data_tag.excludes for data_tag in data.tags if data_tag.key in assigned):
            continue
        if roll < tag_chance_bp(tag, personality):
            assigned.append(tag.key)
    return tuple(assigned)


def draw_name(gen: np.random.Generator, region: str, data: GameData) -> tuple[str, str]:
    pool = data.names[region]
    first = pool.first[int(gen.integers(0, len(pool.first)))]
    last = pool.last[int(gen.integers(0, len(pool.last)))]
    return first, last


def potential_ability(gen: np.random.Generator, ca: float, age: int, balance: Balance) -> float:
    """PA = min(200, CA + max(0, Normal(gap_mean(age), sd))) (step 4)."""
    gap = float(gen.normal(pa_gap_mean(age, balance.people), balance.people.pa_gap_sd))
    return clamp_ability(min(ABILITY_MAX, ca + max(0.0, gap)))


def _rescale_primaries(skills: dict[str, float], role: Role, target_ca: float) -> dict[str, float]:
    """Scale the primaries by one common factor f so CA hits the target (step 2).

    With clamping, the primary sum S(f) = sum(clamp(p_i x f)) is continuous, non-decreasing
    and linear between the breakpoints where a primary reaches 1 or 20, so f is found exactly
    by locating the segment that contains the needed sum. Targets outside what clamped
    primaries can reach get the nearest reachable CA.
    """
    primary = [skills[k] for k in role.primary]
    secondary_sum = sum(skills[k] for k in role.secondary)
    weight = PRIMARY_WEIGHT * len(role.primary) + SECONDARY_WEIGHT * len(role.secondary)
    needed = (target_ca / ABILITY_PER_ATTR * weight - SECONDARY_WEIGHT * secondary_sum) / (
        PRIMARY_WEIGHT
    )

    def total(f: float) -> float:
        return sum(clamp_attr(p * f) for p in primary)

    points = sorted({b / p for p in primary for b in (ATTR_MIN, ATTR_MAX)})
    if needed <= total(points[0]):
        factor = points[0]
    elif needed >= total(points[-1]):
        factor = points[-1]
    else:
        factor = points[-1]
        for lo, hi in itertools.pairwise(points):
            s_lo, s_hi = total(lo), total(hi)
            if s_lo <= needed <= s_hi:
                factor = lo if s_hi == s_lo else lo + (needed - s_lo) * (hi - lo) / (s_hi - s_lo)
                break
    return {**skills, **{k: clamp_attr(skills[k] * factor) for k in role.primary}}


def people_gen_stream(rng: RngFactory, turn: int, *key: int) -> np.random.Generator:
    """Stream `people_gen` (ADR-0013): key `(search_id,)` for a search's batch (section 7), or
    `(company_id, n)` for people a rival hires itself (formulas.md 15.1, 15.4). The two key
    lengths never meet; this helper is the stream's one call site."""
    return rng.stream(turn, "people_gen", *key)


def generate_person(
    gen: np.random.Generator,
    data: GameData,
    balance: Balance,
    turn: int,
    role: Role,
    level: str,
    region: str,
    *,
    person_id: int,
    city: str | None = None,
    talent_city: str | None = None,
) -> Person:
    """One generated person. `city` (M9, 19.3): their home city, which also sets their region;
    `talent_city`: the city they would work in (default `city`), whose talent bonus their role
    skills get and whose multiplier their salary expectation uses. Without a city, as v1."""
    people = balance.people
    if city is not None:
        region = data.city(city).region
    level_ca = people.level_ca[level]

    target = float(gen.normal(level_ca.mean, level_ca.sd))
    target = min(max(target, people.ca_clip.lo), people.ca_clip.hi)

    primaries, secondaries = set(role.primary), set(role.secondary)
    raw: dict[str, float] = {}
    for key in data.skill_keys:
        if key in primaries:
            noise = float(gen.normal(0.0, people.skill_noise_sd.primary))
            raw[key] = clamp_attr(target / ABILITY_PER_ATTR + noise)
        elif key in secondaries:
            noise = float(gen.normal(0.0, people.skill_noise_sd.secondary))
            raw[key] = clamp_attr(target / ABILITY_PER_ATTR - people.secondary_offset + noise)
        else:
            lo, hi = people.other_skill_range.lo, people.other_skill_range.hi
            raw[key] = clamp_attr(float(gen.uniform(lo, hi)))
    if abs(current_ability(raw, role.primary, role.secondary) - target) > people.ca_tolerance:
        raw = _rescale_primaries(raw, role, target)
    if city is not None:  # the city's talent bonus on role skills (M9, 19.1, 19.3)
        hub = data.city(talent_city or city)
        for key in (*role.primary, *role.secondary):
            raw[key] = clamp_attr(raw[key] + talent_bonus(hub, key, data))
    skills = Skills.build(data.skill_keys, raw)
    ca = current_ability(skills.as_dict(), role.primary, role.secondary)

    ages = people.level_age[level]
    age = int(gen.integers(int(ages.lo), int(ages.hi), endpoint=True))
    birth_month = int(gen.integers(0, MONTHS_PER_YEAR))
    birth_turn = turn - MONTHS_PER_YEAR * age - birth_month
    pa = potential_ability(gen, ca, age, balance)

    personality = Personality.build(
        data.personality_keys, draw_traits(gen, data.personality_keys, balance)
    )
    hidden = HiddenTraits.build(data.hidden_keys, draw_traits(gen, data.hidden_keys, balance))
    interests = draw_interests(gen, role, data, balance)
    work_style = draw_work_style(gen, role, data)
    tags = draw_tags(gen, personality, data, balance)
    first, last = draw_name(gen, region, data)

    salary = salary_expectation_cents(
        band_mid_cents=role.salary_band_mid_cents[level],
        ca=ca,
        level_mean=level_ca.mean,
        region_multiplier_bp=(
            pay_multiplier_bp(data.city(talent_city or city), balance)
            if city is not None
            else data.region(region).salary_multiplier_bp
        ),
        round_to_cents=balance.payroll.salary_round_to_cents,
    )
    return Person(
        id=person_id,
        first_name=first,
        last_name=last,
        region=region,
        birth_turn=birth_turn,
        role=role.key,
        level=level,
        skills=skills,
        personality=personality,
        hidden=hidden,
        potential_ability=pa,
        interests=interests,
        work_style=work_style,
        tags=tags,
        salary_expectation_cents=salary,
        city=city,
    )


def generate_pool(
    gen: np.random.Generator,
    data: GameData,
    balance: Balance,
    turn: int,
    role: Role,
    levels: Sequence[str],
    *,
    first_person_id: int,
    city: str | None = None,
) -> tuple[Person, ...]:
    """One person per entry in `levels`, ids counting up from `first_person_id`.

    Each person's region is drawn just before that person, weighted by
    people.region_weights in regions.yaml order. With a search `city` (M9, 19.3) that draw
    is the person's city instead: one uniform u, the search's city below
    geo.local_candidates, else a relocator's city by talent weight among the others; for
    ANYWHERE, every city by talent weight.
    """
    pool = []
    for offset, level in enumerate(levels):
        if city is None:
            region = _weighted_pick(gen, balance.people.region_weights, data.region_keys)
            pool.append(
                generate_person(
                    gen,
                    data,
                    balance,
                    turn,
                    role,
                    level,
                    region,
                    person_id=first_person_id + offset,
                )
            )
            continue
        home = draw_city(float(gen.random()), city, balance, data)
        talent = home if city == ANYWHERE else city
        pool.append(
            generate_person(
                gen,
                data,
                balance,
                turn,
                role,
                level,
                data.city(home).region,
                person_id=first_person_id + offset,
                city=home,
                talent_city=talent,
            )
        )
    return tuple(pool)


def draw_city(u: float, search_city: str, balance: Balance, data: GameData) -> str:
    """A candidate's home city from one uniform u in [0, 1) (19.3)."""
    local = balance.geo.local_candidates
    if search_city != ANYWHERE:
        if u < local:
            return search_city
        u = (u - local) / (1 - local) if local < 1 else 0.0
    others = [c for c in data.cities if c.key != search_city]
    total = sum(c.talent_weight for c in others)
    acc = 0.0
    for c in others:
        acc += c.talent_weight / total
        if u < acc:
            return c.key
    return others[-1].key
