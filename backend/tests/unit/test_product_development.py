"""Phase 3 product development (formulas.md 11.3, 11.4, 11.10): teams, output, quality,
features, rot, tags, and the static incumbents (ADR-0017)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import FIRST_PRODUCT, fresh_game, make_person, with_employee, with_product
from tst.loader import LoadedData
from tst.sim.data_models import Balance
from tst.sim.org.models import OrgUnit
from tst.sim.org.rules import org_view
from tst.sim.products import formulas as f
from tst.sim.products.phases import develop, team_of
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_person, with_unit

PRODUCT = FIRST_PRODUCT


def quiet(balance: Balance) -> Balance:
    """Development noise off, for worked examples."""
    products = balance.products.model_copy(update={"dev_noise_sd": 0.0, "maverick_noise_sd": 0.0})
    return balance.model_copy(update={"products": products})


def flat_skills(state: GameState, person_id: int, value: float) -> GameState:
    """Every skill at `value`, so d = value for any category; no tags."""
    person = state.person(person_id)
    skills = person.skills.updated(dict.fromkeys(person.skills.keys(), value))
    return with_person(state, replace(person, skills=skills, tags=()))


def worked_example_team(loaded: LoadedData) -> GameState:
    """The 11.14 team in the root: founder d 12, engineers d 10.5 (morale 58), 9 (54)."""
    state = flat_skills(fresh_game(loaded), 1, 12.0)
    for pid, d, morale in ((2, 10.5, 58.0), (3, 9.0, 54.0)):
        person = replace(make_person(loaded, pid), tags=())
        state = with_employee(loaded, state, person, 9_000_000, morale=morale)
        state = flat_skills(state, pid, d)
    state = replace(state, next_ids=replace(state.next_ids, person=4))
    return with_product(state, status="in_development", prices={"smb": None}, quality=10)


def play_dev(state: GameState, balance: Balance, loaded: LoadedData, turns: int) -> GameState:
    rng = RngFactory(state.save_meta.master_seed)
    for _ in range(turns):
        state, _ = develop(state, rng, balance, loaded.game_data)
        state = replace(state, turn=state.turn + 1)
    return state


def test_worked_example_through_phase_3(loaded: LoadedData) -> None:
    balance = quiet(loaded.balance)
    state = worked_example_team(loaded)
    product = state.product(PRODUCT)
    assert product is not None
    team = team_of(state, org_view(state, 1), product, balance, loaded.game_data)
    assert [b.person_id for b in team.builders] == [1, 2, 3]
    assert team.base_output(balance) == pytest.approx(3.222, abs=5e-4)
    seen = {}
    for turn in range(12):
        state = play_dev(state, balance, loaded, 1)
        p = state.product(PRODUCT)
        assert p is not None
        seen[turn] = (round(p.quality, 1), round(p.feature_points, 1))
    assert [seen[t][0] for t in (0, 5, 8, 11)] == [13.5, 27.1, 32.9, 37.4]
    assert [seen[t][1] for t in (5, 8, 11)] == [19.3, 29.0, 38.7]


def test_only_members_of_the_assigned_unit_work_on_it(loaded: LoadedData) -> None:
    state = worked_example_team(loaded)
    state = with_unit(state, OrgUnit(1, 1, "team", "Core", None, None, None, 0))
    employment = state.employment_of(3)
    assert employment is not None
    state = replace(
        state,
        employments=tuple(
            replace(e, unit_id=1) if e.person_id == 3 else e for e in state.employments
        ),
    )
    product = state.product(PRODUCT)
    assert product is not None
    team = team_of(state, org_view(state, 1), product, loaded.balance, loaded.game_data)
    assert [b.person_id for b in team.builders] == [1, 2]  # person 3 is in a child unit
    state = with_unit(state, replace(state.units[0], product_id=PRODUCT))
    team = team_of(state, org_view(state, 1), product, loaded.balance, loaded.game_data)
    assert [b.person_id for b in team.builders] == [1, 2, 3]
    assert team.unit_ids == (None, 1)


def test_functions_by_role(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    for pid, role in ((2, "account_executive"), (3, "marketer"), (4, "recruiter")):
        state = with_employee(loaded, state, make_person(loaded, pid, role), 9_000_000)
    state = with_product(state)
    product = state.product(PRODUCT)
    assert product is not None
    team = team_of(state, org_view(state, 1), product, loaded.balance, loaded.game_data)
    assert [b.person_id for b in team.builders] == [1]  # the founder builds
    assert [s.person_id for s in team.sellers] == [2]
    assert [m.person_id for m in team.marketers] == [3]
    assert team.capacity("mid_market", loaded.balance) > 0
    assert team.capacity("smb", loaded.balance) == 0  # self-serve: no capacity


def test_no_team_rots_and_notes_it_once(loaded: LoadedData) -> None:
    state = with_product(fresh_game(loaded), quality=30, root=False, feature_points=50)
    rng = RngFactory(1)
    state, logs = develop(state, rng, loaded.balance, loaded.game_data)
    product = state.product(PRODUCT)
    assert product is not None
    assert product.quality == 29.5 and product.feature_points == 50 and product.rotting
    assert [i.template for i in logs] == ["product_rotting"]
    state, logs = develop(replace(state, turn=1), rng, loaded.balance, loaded.game_data)
    assert logs == ()  # still rotting: no repeat


def test_tags_change_output_and_cap(loaded: LoadedData) -> None:
    balance = quiet(loaded.balance)
    base = worked_example_team(loaded)
    product = base.product(PRODUCT)
    assert product is not None
    plain = team_of(base, org_view(base, 1), product, balance, loaded.game_data)
    genius = with_person(base, replace(base.person(2), tags=("quiet_genius",)))
    team = team_of(genius, org_view(genius, 1), product, balance, loaded.game_data)
    assert team.builders[1].output == pytest.approx(plain.builders[1].output * 1.25)
    perfect = with_person(base, replace(base.person(2), tags=("perfectionist",)))
    team = team_of(perfect, org_view(perfect, 1), product, balance, loaded.game_data)
    assert team.builders[1].output == pytest.approx(plain.builders[1].output * 0.85)
    plain_cap, cap = plain.qcap(balance), team.qcap(balance)
    assert plain_cap is not None and cap is not None and cap > plain_cap
    maverick = with_person(base, replace(base.person(2), tags=("maverick",)))
    team = team_of(maverick, org_view(maverick, 1), product, balance, loaded.game_data)
    assert team.mavericks == 1
    assert f.dev_noise_sd(team.mavericks, loaded.balance.products) == pytest.approx(0.25)


def test_noise_is_seeded_per_product(loaded: LoadedData) -> None:
    state = worked_example_team(loaded)
    a, _ = develop(state, RngFactory(7), loaded.balance, loaded.game_data)
    b, _ = develop(state, RngFactory(7), loaded.balance, loaded.game_data)
    c, _ = develop(state, RngFactory(8), loaded.balance, loaded.game_data)
    assert a.product(PRODUCT) == b.product(PRODUCT)
    pa, pc = a.product(PRODUCT), c.product(PRODUCT)
    assert pa is not None and pc is not None and pa.feature_points != pc.feature_points


def test_incumbents_hold_their_scores(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    state = play_dev(state, loaded.balance, loaded, 12)
    b2b = loaded.game_data.category("b2b_saas")
    sales_cloud = state.products[0]
    assert (sales_cloud.quality, sales_cloud.brand) == (70, 80)
    assert f.feature_score(sales_cloud.feature_points, b2b, 11) == pytest.approx(80)
    assert sales_cloud.feature_points == pytest.approx(0.8 * f.expected_features(b2b, 11))
