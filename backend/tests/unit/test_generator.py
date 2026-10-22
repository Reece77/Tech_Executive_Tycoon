from __future__ import annotations

import pickle

import pytest

from tst.loader import LoadedData
from tst.sim.data_models import LEVELS
from tst.sim.people.formulas import current_ability
from tst.sim.people.generator import (
    _rescale_primaries,
    generate_person,
    generate_pool,
    tag_chance_bp,
)
from tst.sim.people.models import Person, Personality
from tst.sim.rng import RngFactory
from tst.sim.scale import ABILITY_MAX, ATTR_MAX, ATTR_MIN


def make(loaded: LoadedData, seed: int, level: str = "senior", n: int = 1) -> tuple[Person, ...]:
    gen = RngFactory(seed).stream(0, "misc", 1)
    role = loaded.game_data.role("software_engineer")
    return generate_pool(
        gen, loaded.game_data, loaded.balance, 0, role, [level] * n, first_person_id=1
    )


def test_same_seed_is_byte_identical(loaded: LoadedData) -> None:
    a, b = make(loaded, 7, n=20), make(loaded, 7, n=20)
    assert a == b
    assert pickle.dumps(a) == pickle.dumps(b)
    assert make(loaded, 8, n=20) != a


def test_generated_person_is_complete(loaded: LoadedData) -> None:
    data = loaded.game_data
    (person,) = make(loaded, 11)
    assert person.id == 1
    assert person.role == "software_engineer" and person.level == "senior"
    assert person.region in data.region_keys
    assert person.first_name in data.names[person.region].first
    assert person.last_name in data.names[person.region].last
    assert person.skills.keys() == tuple(data.skill_keys)
    assert person.personality.keys() == tuple(data.personality_keys)
    assert person.hidden.keys() == tuple(data.hidden_keys)
    assert 2 <= len(person.interests) <= 4
    assert len(set(person.interests)) == len(person.interests)
    assert person.work_style in data.work_style_keys
    assert 29 <= person.age(0) <= 45
    assert person.salary_expectation_cents is not None
    assert person.salary_expectation_cents % loaded.balance.payroll.salary_round_to_cents == 0
    assert not person.is_founder


def test_ca_and_pa_in_range_across_levels(loaded: LoadedData) -> None:
    role = loaded.game_data.role("software_engineer")
    gen = RngFactory(3).stream(0, "misc", 2)
    for i in range(200):
        level = LEVELS[i % len(LEVELS)]
        p = generate_person(
            gen, loaded.game_data, loaded.balance, 0, role, level, "europe", person_id=i
        )
        ca = current_ability(p.skills.as_dict(), role.primary, role.secondary)
        assert ATTR_MIN * 10 <= ca <= ABILITY_MAX
        assert p.potential_ability >= ca


def test_rescale_hits_target_exactly_when_reachable(loaded: LoadedData) -> None:
    role = loaded.game_data.role("software_engineer")
    base = {k: 5.0 for k in loaded.game_data.skill_keys}
    base.update({"software_engineering": 9.0, "infrastructure": 7.0})
    for target in (60.0, 100.0, 135.0):  # max reachable here is 140 (primaries at 20)
        out = _rescale_primaries(base, role, target)
        assert current_ability(out, role.primary, role.secondary) == pytest.approx(target)
        assert out["data"] == base["data"]  # only primaries move
    # 200 is unreachable with secondaries at 5: primaries cap at 20.
    out = _rescale_primaries(base, role, 200.0)
    assert out["software_engineering"] == out["infrastructure"] == ATTR_MAX


def test_tag_chance_boost(loaded: LoadedData) -> None:
    data = loaded.game_data
    mentor = next(t for t in data.tags if t.key == "mentor")
    calm_social = Personality.build(data.personality_keys, {k: 13.0 for k in data.personality_keys})
    plain = Personality.build(data.personality_keys, {k: 10.0 for k in data.personality_keys})
    assert tag_chance_bp(mentor, calm_social) == 1200  # 400 bp x 3
    assert tag_chance_bp(mentor, plain) == 400


def test_tags_respect_exclusions_and_cap(loaded: LoadedData) -> None:
    data = loaded.game_data
    excludes = {t.key: set(t.excludes) for t in data.tags}
    people = make(loaded, 21, level="mid", n=2000)
    for p in people:
        assert len(p.tags) <= loaded.balance.people.max_tags
        for tag in p.tags:
            assert not (excludes[tag] & set(p.tags))
    share = sum(1 for p in people if p.tags) / len(people)
    # formulas.md section 2 step 7: about 25% of generated people carry at least one tag.
    assert 0.18 <= share <= 0.32, share


@pytest.mark.parametrize("level", LEVELS)
def test_distribution_by_level(loaded: LoadedData, level: str) -> None:
    """5,000 people per level: mean CA within 3 of target, attributes in range, PA >= CA."""
    data, balance = loaded.game_data, loaded.balance
    role = data.role("software_engineer")
    gen = RngFactory(2010).stream(0, "misc", LEVELS.index(level))
    total = 0.0
    n = 5000
    for i in range(n):
        p = generate_person(gen, data, balance, 0, role, level, "north_america", person_id=i)
        ca = current_ability(p.skills.as_dict(), role.primary, role.secondary)
        total += ca
        for attrs in (p.skills, p.personality, p.hidden):
            assert all(ATTR_MIN <= v <= ATTR_MAX for _, v in attrs.items)
        assert ca <= p.potential_ability <= ABILITY_MAX
    assert abs(total / n - balance.people.level_ca[level].mean) <= 3
