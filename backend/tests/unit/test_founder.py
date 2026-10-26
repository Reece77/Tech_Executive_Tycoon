from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.errors import InvalidFounderError
from tst.sim.people.founder import FounderSpec, build_founder, founder_skills
from tst.sim.people.models import PA_KEY, best_fit_role
from tst.sim.people.reveal import revealed_range
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, PLAYER_COMPANY_ID, new_game


def build(loaded: LoadedData, spec: FounderSpec, seed: int = 42):  # type: ignore[no-untyped-def]
    return build_founder(spec, RngFactory(seed), loaded.game_data, loaded.balance, 0, person_id=1)


def test_engineer_default_skills(loaded: LoadedData) -> None:
    skills = founder_skills(FounderSpec("engineer"), loaded.game_data, loaded.balance)
    # base 5 + default allocation + background bonus
    assert skills["software_engineering"] == 5 + 8 + 3
    assert skills["infrastructure"] == 5 + 7 + 2
    assert skills["product"] == 5 + 8
    assert skills["geology"] == 5
    base = loaded.balance.founder.skill_base * len(loaded.game_data.skills)
    assert sum(v for _, v in skills.items) == base + 70 + 5


@pytest.mark.parametrize("background", ["engineer", "salesperson", "academic", "ex_big_tech"])
def test_every_v1_background_builds(loaded: LoadedData, background: str) -> None:
    person = build(loaded, FounderSpec(background))
    assert person.is_founder and person.role is None and person.level is None
    assert person.age(0) == 28
    assert person.region == "north_america"
    assert person.potential_ability >= best_fit_role(person.skills, loaded.game_data)[1]


def test_same_seed_same_founder(loaded: LoadedData) -> None:
    assert build(loaded, DEFAULT_FOUNDER, 5) == build(loaded, DEFAULT_FOUNDER, 5)
    assert build(loaded, DEFAULT_FOUNDER, 5) != build(loaded, DEFAULT_FOUNDER, 6)


def test_preset_personality_is_exact(loaded: LoadedData) -> None:
    person = build(loaded, FounderSpec("engineer", personality_preset="operator"))
    preset = loaded.game_data.preset("operator")
    assert preset is not None
    assert person.personality.as_dict() == {k: float(v) for k, v in preset.values.items()}


def test_interests_and_work_style_use_best_fit_role(loaded: LoadedData) -> None:
    data = loaded.game_data
    person = build(loaded, FounderSpec("salesperson"))
    role, _ = best_fit_role(person.skills, data)
    assert role.key in ("sales_representative", "account_executive")
    for interest in person.interests:
        assert role.interest_weights[interest] > 0
    assert role.work_style_weights[person.work_style] > 0


def test_overrides(loaded: LoadedData) -> None:
    spec = FounderSpec(
        "academic",
        age=45,
        region="europe",
        first_name="Ada",
        last_name="Okafor",
        interests=("ai", "climate"),
        work_style="researcher",
    )
    person = build(loaded, spec)
    assert person.age(0) == 45
    assert (person.first_name, person.last_name, person.region) == ("Ada", "Okafor", "europe")
    assert person.interests == ("ai", "climate")
    assert person.work_style == "researcher"


def test_custom_allocation(loaded: LoadedData) -> None:
    allocation = {
        "software_engineering": 10,  # 5 + 10 + 3 bonus = 18 (the cap)
        "infrastructure": 11,  # 5 + 11 + 2 bonus = 18
        "product": 13,
        "strategy": 13,
        "leadership": 13,
        "data": 10,
    }
    assert sum(allocation.values()) == 70
    person = build(loaded, FounderSpec("engineer", allocation=allocation))
    assert person.skills["software_engineering"] == 18
    assert person.skills["infrastructure"] == 18
    assert person.skills["product"] == 18
    assert person.skills["data"] == 15
    assert person.skills["sales"] == 5


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (
            FounderSpec("engineer", allocation={"software_engineering": 10, "product": 61}),
            "spends 71 points; only 70 are available",
        ),
        (
            FounderSpec("engineer", allocation={"software_engineering": 10}),
            "spends 10 points; spend all 70",
        ),
        (
            FounderSpec("engineer", allocation={"software_engineering": 11, "product": 59}),
            "above the cap of 18: software_engineering = 19, product = 64",
        ),
        (FounderSpec("engineer", allocation={"cooking": 70}), "unknown skills in allocation"),
        (FounderSpec("astronaut"), "unknown background 'astronaut'"),
        (FounderSpec("geologist"), "background 'geologist' unlocks in v3"),
        (FounderSpec("engineer", personality_preset="dreamer"), "unknown personality preset"),
        (FounderSpec("engineer", age=21), "age must be 22-60, got 21"),
        (FounderSpec("engineer", age=61), "age must be 22-60, got 61"),
        (FounderSpec("engineer", region="mars"), "unknown region 'mars'"),
        (FounderSpec("engineer", interests=("ai",)), "choose 2-4 interests"),
        (FounderSpec("engineer", interests=("ai", "ai")), "interests must not repeat"),
        (FounderSpec("engineer", interests=("ai", "knitting")), "unknown interests"),
        (FounderSpec("engineer", work_style="dreamer"), "unknown work style"),
        (FounderSpec("engineer", first_name=" ", last_name="X"), "first name must be"),
    ],
)
def test_invalid_specs(loaded: LoadedData, spec: FounderSpec, message: str) -> None:
    with pytest.raises(InvalidFounderError) as info:
        build(loaded, spec)
    assert message in str(info.value)
    assert info.value.code == "invalid_founder"


def test_new_game_creates_founder_employment_and_knowledge(loaded: LoadedData) -> None:
    scenario = loaded.game_data.scenario("garage_bootstrap")
    assert scenario is not None
    state, _ = new_game(
        save_name="dev",
        master_seed=42,
        scenario=scenario,
        difficulty="standard",
        company_name="Test Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    (person,) = state.people
    (employment,) = state.employments
    assert person.is_founder
    assert (employment.role, employment.level, employment.salary_cents) == ("founder", "exec", 0)
    assert (employment.equity_bp, employment.start_turn, employment.status) == (0, 0, "active")
    assert state.staff(PLAYER_COMPANY_ID) == (employment,)

    reveal = state.reveal(PLAYER_COMPANY_ID, person.id)
    assert reveal is not None
    for key in [*loaded.game_data.skill_keys, *loaded.game_data.personality_keys]:
        assert reveal.record(key).hw == 0
    assert (
        reveal.record(PA_KEY).hw == loaded.balance.reveal.founder_pa_hw
    )  # 40, formulas.md 5 (M2b)
    assert reveal.profile_revealed_turn == 0
    assert reveal.revealed_tags == tuple((tag, 0) for tag in person.tags)
    offsets = [rec.offset for _, rec in reveal.attributes]
    assert all(-0.5 <= o <= 0.5 for o in offsets)
    assert len(set(offsets)) == len(offsets)


def test_founding_company_sees_founder_exactly(loaded: LoadedData) -> None:
    scenario = loaded.game_data.scenario("garage_bootstrap")
    assert scenario is not None
    state, _ = new_game(
        save_name="dev",
        master_seed=3,
        scenario=scenario,
        difficulty="standard",
        company_name="Test Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    person = state.people[0]
    reveal = state.reveal(PLAYER_COMPANY_ID, person.id)
    assert reveal is not None
    assert revealed_range(person, reveal, "software_engineering") == (16, 16)
    ambition = round(person.personality["ambition"])
    assert revealed_range(person, reveal, "ambition") == (ambition, ambition)
    lo, hi = revealed_range(person, reveal, PA_KEY)
    assert lo <= person.potential_ability <= hi
    assert hi - lo >= 40  # PA keeps its initial half-width of 40
