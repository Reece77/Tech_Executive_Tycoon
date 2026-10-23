"""Founder build (docs/formulas.md section 5).

Skills: every skill starts at founder.skill_base; the player's allocation (or the
background's default) spends exactly founder.skill_points; the background adds its bonuses;
no skill may end above founder.skill_cap.

Random draws use stream `founder` (no key) at the game's start turn, in this order; a step
whose value the player supplied is skipped:

1. birth month                   integer in [0, 11]
2. personality                   Normal(mean, sd) per trait, unless a preset is chosen
3. hidden traits                 Normal(mean, sd) per trait
4. potential gap                 as for any person (formulas.md 2.4), from the best-fit CA
5. interests                     with the best-fit role's weights, unless supplied
6. work style                    with the best-fit role's weights, unless supplied
7. behavior tags                 as for any person (formulas.md 2.7)
8. first name, then last name    from the region's pool, unless both are supplied
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidFounderError
from tst.sim.people.generator import (
    draw_interests,
    draw_name,
    draw_tags,
    draw_traits,
    draw_work_style,
    potential_ability,
)
from tst.sim.people.models import HiddenTraits, Person, Personality, Skills, best_fit_role
from tst.sim.rng import RngFactory

NAME_MAX = 40  # tunable-exempt: column width of person names


@dataclass(frozen=True, slots=True)
class FounderSpec:
    background: str
    allocation: Mapping[str, int] | None = None  # None: the background's default allocation
    personality_preset: str | None = None  # None: random personality
    age: int | None = None  # None: founder.default_age
    region: str | None = None  # None: founder.default_region
    first_name: str | None = None  # names are drawn unless both are given
    last_name: str | None = None
    interests: tuple[str, ...] | None = None
    work_style: str | None = None


def _fail(message: str) -> InvalidFounderError:
    return InvalidFounderError(f"founder: {message}")


@dataclass(frozen=True, slots=True)
class FounderPreview:
    """What the setup screen shows while the player builds a founder. No randomness."""

    skills: dict[str, float]  # final values for known skills (base + allocation + bonus)
    points_spent: int
    points_remaining: int
    problems: tuple[str, ...]  # every rule the build breaks, in a fixed order


def preview_founder(spec: FounderSpec, data: GameData, balance: Balance) -> FounderPreview:
    """Check a founder build and collect every problem, in the order build_founder reports."""
    founder = balance.founder
    problems: list[str] = []
    background = data.background(spec.background)
    if background is None:
        known = [b.key for b in data.backgrounds]
        problems.append(f"unknown background {spec.background!r}; choose one of {known}")
    elif not background.selectable:
        problems.append(f"background {background.key!r} unlocks in {background.available_in}")

    if spec.allocation is not None:
        allocation = dict(spec.allocation)
    else:
        allocation = dict(background.default_allocation) if background else {}
    bonuses = background.bonuses if background else {}
    unknown = sorted(set(allocation) - set(data.skill_keys))
    if unknown:
        problems.append(f"unknown skills in allocation: {unknown}")
    negative = sorted(k for k, v in allocation.items() if v < 0)
    if negative:
        problems.append(f"negative points for {negative}")
    spent = sum(allocation.values())
    if spent > founder.skill_points:
        problems.append(
            f"allocation spends {spent} points; only {founder.skill_points} are available"
        )
    elif spent < founder.skill_points:
        problems.append(f"allocation spends {spent} points; spend all {founder.skill_points}")

    values: dict[str, float] = {}
    over: list[str] = []
    for key in data.skill_keys:
        value = founder.skill_base + allocation.get(key, 0) + bonuses.get(key, 0)
        if value > founder.skill_cap:
            over.append(f"{key} = {value:g}")
        values[key] = value
    if over:
        problems.append(f"skills above the cap of {founder.skill_cap:g}: {', '.join(over)}")

    age = founder.default_age if spec.age is None else spec.age
    if not founder.age_range.lo <= age <= founder.age_range.hi:
        problems.append(f"age must be {founder.age_range.lo:g}-{founder.age_range.hi:g}, got {age}")
    region = founder.default_region if spec.region is None else spec.region
    if region not in data.region_keys:
        problems.append(f"unknown region {region!r}")
    if spec.personality_preset is not None and data.preset(spec.personality_preset) is None:
        known = [p.key for p in data.personality_presets]
        problems.append(f"unknown personality preset {spec.personality_preset!r}; choose {known}")
    if spec.interests is not None:
        span = balance.people.interest_count
        if not span.lo <= len(spec.interests) <= span.hi:
            problems.append(f"choose {span.lo:g}-{span.hi:g} interests")
        if len(set(spec.interests)) != len(spec.interests):
            problems.append("interests must not repeat")
        bad = sorted(set(spec.interests) - set(data.interest_keys))
        if bad:
            problems.append(f"unknown interests {bad}")
    if spec.work_style is not None and spec.work_style not in data.work_style_keys:
        problems.append(f"unknown work style {spec.work_style!r}")
    if spec.first_name is not None and spec.last_name is not None:
        for label, name in (("first name", spec.first_name), ("last name", spec.last_name)):
            if not name or not name.strip() or len(name.strip()) > NAME_MAX:
                problems.append(f"{label} must be 1-{NAME_MAX} characters")
    return FounderPreview(
        skills=values,
        points_spent=spent,
        points_remaining=founder.skill_points - spent,
        problems=tuple(problems),
    )


def founder_skills(spec: FounderSpec, data: GameData, balance: Balance) -> Skills:
    """Validate the whole build and return the founder's starting skills."""
    preview = preview_founder(spec, data, balance)
    if preview.problems:
        raise _fail(preview.problems[0])
    return Skills.build(data.skill_keys, preview.skills)


def build_founder(
    spec: FounderSpec,
    rng: RngFactory,
    data: GameData,
    balance: Balance,
    turn: int,
    *,
    person_id: int,
) -> Person:
    founder = balance.founder
    skills = founder_skills(spec, data, balance)  # raises on any problem
    age = founder.default_age if spec.age is None else spec.age
    region = founder.default_region if spec.region is None else spec.region
    preset = None if spec.personality_preset is None else data.preset(spec.personality_preset)
    named = spec.first_name is not None and spec.last_name is not None

    role, ca = best_fit_role(skills, data)
    gen = rng.stream(turn, "founder")

    birth_month = int(gen.integers(0, MONTHS_PER_YEAR))
    if preset is None:
        traits = draw_traits(gen, data.personality_keys, balance)
    else:
        traits = dict(preset.values)
    personality = Personality.build(data.personality_keys, traits)
    hidden = HiddenTraits.build(data.hidden_keys, draw_traits(gen, data.hidden_keys, balance))
    pa = potential_ability(gen, ca, age, balance)
    interests = (
        draw_interests(gen, role, data, balance) if spec.interests is None else spec.interests
    )
    work_style = draw_work_style(gen, role, data) if spec.work_style is None else spec.work_style
    tags = draw_tags(gen, personality, data, balance)
    if named:
        first, last = (spec.first_name or "").strip(), (spec.last_name or "").strip()
    else:
        first, last = draw_name(gen, region, data)

    return Person(
        id=person_id,
        first_name=first,
        last_name=last,
        region=region,
        birth_turn=turn - MONTHS_PER_YEAR * age - birth_month,
        role=None,
        level=None,
        skills=skills,
        personality=personality,
        hidden=hidden,
        potential_ability=pa,
        interests=tuple(interests),
        work_style=work_style,
        tags=tags,
        salary_expectation_cents=None,
        is_founder=True,
    )
