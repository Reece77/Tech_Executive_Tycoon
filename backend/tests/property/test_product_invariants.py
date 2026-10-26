"""Product invariants over random teams and products (formulas.md 11.3-11.5).

Development: quality and brand stay in [0, 100], output is never negative (feature points
never fall), and a product nobody works on only loses quality.
"""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game, make_person, with_employee, with_product
from tst.loader import load_all
from tst.sim.products.phases import brand_and_demand, develop
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_person

LOADED = load_all(DATA_DIR)
BASE = fresh_game(LOADED)
PRODUCT = 13
ROLES = ("software_engineer", "designer", "marketer", "account_executive", "recruiter")
TAGS = ("quiet_genius", "toxic_high_performer", "perfectionist", "maverick", "politician", "")


@st.composite
def teams(draw: st.DrawFn) -> GameState:
    state = BASE
    for pid in range(2, 2 + draw(st.integers(min_value=0, max_value=12))):
        role = draw(st.sampled_from(ROLES))
        person = make_person(LOADED, pid, role)
        tag = draw(st.sampled_from(TAGS))
        skill = draw(st.floats(min_value=1, max_value=20))
        skills = person.skills.updated(dict.fromkeys(person.skills.keys(), skill))
        person = replace(person, tags=(tag,) if tag else (), skills=skills)
        morale = draw(st.floats(min_value=0, max_value=100))
        state = with_employee(LOADED, state, person, 9_000_000, morale=morale)
        state = with_person(state, person)
    category = draw(st.sampled_from([c.key for c in LOADED.game_data.categories]))
    segment = LOADED.game_data.category(category).segment_keys[0]
    return with_product(
        state,
        category=category,
        prices={segment: 1000},
        status=draw(st.sampled_from(["in_development", "live"])),
        quality=draw(st.floats(min_value=0, max_value=100)),
        brand=draw(st.floats(min_value=0, max_value=100)),
        budget_cents=draw(st.integers(min_value=0, max_value=50_000_000)),
        root=draw(st.booleans()),
    )


def months(state: GameState, seed: int, turns: int) -> list[GameState]:
    rng = RngFactory(seed)
    out = []
    for _ in range(turns):
        state, _ = develop(state, rng, LOADED.balance, LOADED.game_data)
        state = brand_and_demand(state, LOADED.balance, LOADED.game_data)
        out.append(state)
        state = replace(state, turn=state.turn + 1)
    return out


@settings(max_examples=60, deadline=None)
@given(teams(), st.integers(min_value=0, max_value=2**32))
def test_scores_stay_in_range_and_output_is_never_negative(state: GameState, seed: int) -> None:
    before = state.product(PRODUCT)
    assert before is not None
    points = before.feature_points
    for month in months(state, seed, 6):
        product = month.product(PRODUCT)
        assert product is not None
        assert 0 <= product.quality <= 100
        assert 0 <= product.brand <= 100
        assert product.feature_points >= points  # o >= 0
        points = product.feature_points


@settings(max_examples=40, deadline=None)
@given(teams(), st.integers(min_value=0, max_value=2**32))
def test_a_product_with_no_units_only_loses_quality(state: GameState, seed: int) -> None:
    state = replace(
        state, companies=(replace(state.player, root_product_id=None), *state.companies[1:])
    )
    before = state.product(PRODUCT)
    assert before is not None
    quality, points = before.quality, before.feature_points
    for month in months(state, seed, 6):
        product = month.product(PRODUCT)
        assert product is not None
        assert product.quality <= quality and product.feature_points == points
        quality = product.quality
