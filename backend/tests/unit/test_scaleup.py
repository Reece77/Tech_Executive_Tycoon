"""M8 divisions, executive seats and support (formulas.md 18.1-18.5): rules, effects in
18.5 order, vacancies, coverage and the ledger's division dimension."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, with_employee, with_product
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    ActionResult,
    AppointExecutive,
    AssignUnit,
    CreateUnit,
    DissolveUnit,
    MovePerson,
    MoveUnit,
    OpenSearch,
    RemoveExecutive,
    SetLeader,
    SetProductDivision,
    SetSharedServices,
    apply_action,
)
from tst.sim.errors import InvalidActionError, OrgRuleError
from tst.sim.finance.fundraising import base_value
from tst.sim.hiring.phases import candidate_batches, monthly_cost_lines, payroll
from tst.sim.org import executives as ex
from tst.sim.org.divisions import division_months, support_pools
from tst.sim.org.morale import morale_terms
from tst.sim.org.rules import org_view
from tst.sim.org.scaleup import modifiers
from tst.sim.products.phases import team_of
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, reach_stage, with_company, with_person, with_person_state

FOUNDER = 1


def game(loaded: LoadedData, staff: int = 6, stage: int = 3, role: str = "software_engineer"):
    state = fresh_game(loaded)
    for pid in range(2, 2 + staff):
        state = with_employee(loaded, state, make_person(loaded, pid, role, "senior"), 12_000_000)
    state = with_company(state, reach_stage(state.player, stage, 0))
    return state


def act(loaded: LoadedData, state: GameState, action: Action) -> ActionResult:
    return apply_action(state, action, RngFactory(3), loaded.balance, loaded.game_data, {}, seq=1)


def run(loaded: LoadedData, state: GameState, *actions: Action) -> GameState:
    for action in actions:
        state = act(loaded, state, action).new_state
        ps = state.person_state(FOUNDER)
        state = with_person_state(state, replace(ps, energy=60))
    return state


def skilled(state: GameState, person_id: int, value: float) -> GameState:
    """Every skill of a person at `value` (true values; tests only)."""
    person = state.person(person_id)
    skills = person.skills.updated(dict.fromkeys(person.skills.keys(), value))
    return with_person(state, replace(person, skills=skills))


# --- Before stage 3 nothing changes (18 intro) ---------------------------------------------


def test_before_stage_3_nothing_applies(loaded: LoadedData) -> None:
    state = game(loaded, stage=2)
    view = org_view(state, 1)
    assert modifiers(state, view, loaded.balance, loaded.game_data) is None
    assert ex.effects(state, 1, loaded.balance) == {
        s: 0.0 for s in ex.effects(state, 1, loaded.balance)
    }
    assert ex.k_coo(state, 1, loaded.balance) == 1.0
    with pytest.raises(OrgRuleError, match="divisions unlock"):
        act(loaded, state, CreateUnit(FOUNDER, "division", "Platform"))
    with pytest.raises(OrgRuleError, match="seats open"):
        act(loaded, state, AppointExecutive(FOUNDER, "cto", 2))
    with pytest.raises(InvalidActionError, match="exec searches"):
        act(loaded, state, OpenSearch(FOUNDER, "software_engineer", "network", level="exec"))
    employment = state.employment_of(2)
    assert employment is not None
    terms = morale_terms(state, view, employment, loaded.balance, loaded.game_data, 0, 0)
    assert terms.support == 0.0
    # monthly costs are one line per cost, as in v1
    assert all(
        d is None for *_, d in monthly_cost_lines(state, 1, loaded.balance, loaded.game_data)
    )


# --- Divisions (18.1) and the layer tax (18.2) ----------------------------------------------


def test_division_rules_and_president(loaded: LoadedData) -> None:
    state = game(loaded)
    out = act(loaded, state, CreateUnit(FOUNDER, "division", "Platform"))
    assert out.log_items[0].template == "division_created"
    state = run(loaded, state, CreateUnit(FOUNDER, "division", "Platform"))
    div = state.units[-1].id
    with pytest.raises(OrgRuleError, match="directly under"):
        act(loaded, state, CreateUnit(FOUNDER, "division", "X", parent_id=div))
    state = run(
        loaded,
        state,
        CreateUnit(FOUNDER, "department", "Eng", parent_id=div),
        CreateUnit(FOUNDER, "team", "Core", parent_id=state.units[-1].id + 1),
        MovePerson(FOUNDER, 2, div),
        SetLeader(FOUNDER, div, 2),
    )
    dept, team = state.units[-2].id, state.units[-1].id
    assert state.unit(team).parent_id == dept
    with pytest.raises(OrgRuleError, match="president cannot"):
        act(loaded, state, AppointExecutive(FOUNDER, "cto", 2))
    # a department may move to the root and back under the division
    state = run(loaded, state, MoveUnit(FOUNDER, dept, None), MoveUnit(FOUNDER, dept, div))
    assert state.unit(dept).parent_id == div


def test_max_divisions(loaded: LoadedData) -> None:
    state = game(loaded)
    for i in range(loaded.balance.org.max_divisions):
        state = run(loaded, state, CreateUnit(FOUNDER, "division", f"D{i}"))
    with pytest.raises(OrgRuleError, match="at most"):
        act(loaded, state, CreateUnit(FOUNDER, "division", "One too many"))


def _deep_team(loaded: LoadedData, state: GameState) -> tuple[GameState, int, int]:
    """Platform > Eng > Core with persons 2-4 in Core building a product."""
    state = run(loaded, state, CreateUnit(FOUNDER, "division", "Platform"))
    div = state.units[-1].id
    state = run(loaded, state, CreateUnit(FOUNDER, "department", "Eng", parent_id=div))
    dept = state.units[-1].id
    state = run(loaded, state, CreateUnit(FOUNDER, "team", "Core", parent_id=dept))
    team = state.units[-1].id
    state = with_product(state, root=False)
    product = state.products[-1].id
    state = run(
        loaded,
        state,
        *(MovePerson(FOUNDER, p, team) for p in (2, 3, 4)),
        AssignUnit(FOUNDER, product, team),
    )
    return state, team, div


def _output(loaded: LoadedData, state: GameState) -> float:
    product = state.products[-1]
    return team_of(
        state, org_view(state, 1), product, loaded.balance, loaded.game_data
    ).base_output(loaded.balance)


def test_layer_tax_and_cross_division(loaded: LoadedData) -> None:
    """Depth 3 x 0.97 (and the vacant COO's k = 1.25); a second division's unit on the same
    product adds x 0.90."""
    state, _team, _div = _deep_team(loaded, game(loaded))
    mods = modifiers(state, org_view(state, 1), loaded.balance, loaded.game_data)
    assert mods is not None
    k = 1 - 0.5 * -0.5  # COO vacant: e = -0.5
    cto = 1 + 0.10 * -0.5
    pools = support_pools(state, org_view(state, 1), loaded.balance, loaded.game_data)
    support = 1 - 0.15 * (1 - pools[None].coverage) * k
    assert mods.builder[2] == pytest.approx((1 - 0.03 * k) * support * cto)
    one = _output(loaded, state)
    state = run(loaded, state, CreateUnit(FOUNDER, "division", "Fintech"))
    other = state.units[-1].id
    state = run(loaded, state, CreateUnit(FOUNDER, "team", "Pay", parent_id=other))
    state = run(loaded, state, AssignUnit(FOUNDER, state.products[-1].id, state.units[-1].id))
    assert _output(loaded, state) == pytest.approx(one * 0.90)


def test_dissolving_a_division_makes_its_products_corporate(loaded: LoadedData) -> None:
    state, _, div = _deep_team(loaded, game(loaded))
    product = state.products[-1].id
    state = run(loaded, state, SetProductDivision(FOUNDER, product, div))
    assert state.product(product).division_id == div
    state = run(loaded, state, DissolveUnit(FOUNDER, div))
    assert state.product(product).division_id is None


def test_ledger_division_lines(loaded: LoadedData) -> None:
    """Salaries go to the employee's division, a product's revenue and hosting to its
    division, base overhead to corporate; lines still sum to the old totals."""
    state, _team, div = _deep_team(loaded, game(loaded))
    product = state.products[-1].id
    state = run(loaded, state, SetProductDivision(FOUNDER, product, div))
    lines = monthly_cost_lines(state, 1, loaded.balance, loaded.game_data)
    salaries = {d: a for memo, _, a, d in lines if memo == "Salaries"}
    assert salaries[div] == 3 * round(12_000_000 / 12)
    assert salaries[None] == 3 * round(12_000_000 / 12)  # persons 5-7 at the root
    assert [d for memo, *_, d in lines if memo == "Base overhead"] == [None]
    entries, _ = payroll(state, loaded.balance, loaded.game_data)
    mine = [e for e in entries if e.company_id == 1]
    assert sum(ln.amount for ln in mine[0].lines) == 0
    months = division_months(state)
    assert [(m.division_id, m.headcount) for m in months] == [(None, 4), (div, 3)]


# --- Executive seats (18.3) -----------------------------------------------------------------


def test_appoint_and_remove(loaded: LoadedData) -> None:
    state = game(loaded)
    before = state.person_state(2).morale or 0
    out = act(loaded, state, AppointExecutive(FOUNDER, "cto", 2))
    state = out.new_state
    assert state.seat_holder(1, "cto") == 2
    assert state.employment_of(2).level == "exec"  # type: ignore[union-attr]
    assert state.person_state(2).morale == pytest.approx(before + 5)
    assert state.person_state(FOUNDER).energy == 60 - 5
    assert out.log_items[0].template == "exec_appointed"
    with pytest.raises(OrgRuleError, match="already hold"):
        act(loaded, state, AppointExecutive(FOUNDER, "cpo", 2))
    with pytest.raises(OrgRuleError, match="filled"):
        act(loaded, state, AppointExecutive(FOUNDER, "cto", 3))
    state = act(loaded, state, RemoveExecutive(FOUNDER, "cto")).new_state
    assert state.seat_holder(1, "cto") is None
    assert state.employment_of(2).level == "exec"  # type: ignore[union-attr]
    assert state.person_state(2).morale == pytest.approx(before + 5 - 10)
    with pytest.raises(OrgRuleError, match="founder"):
        act(loaded, state, AppointExecutive(FOUNDER, "coo", FOUNDER))


def test_appointee_needs_senior_level(loaded: LoadedData) -> None:
    state = game(loaded)
    state = with_employee(loaded, state, make_person(loaded, 20, "designer", "mid"), 9_000_000)
    with pytest.raises(OrgRuleError, match="senior"):
        act(loaded, state, AppointExecutive(FOUNDER, "cpo", 20))


@pytest.mark.parametrize("seat", ["coo", "cfo", "cto", "cpo", "cmo", "cro"])
def test_each_seat_effect_and_vacancy(loaded: LoadedData, seat: str) -> None:
    """A holder of s = 14 gives e = 0.5; vacant at stage 3 gives -0.5."""
    state = game(loaded)
    coefficient = loaded.balance.exec_seats.seats[seat].effect
    assert ex.effect_of(state, 1, seat, loaded.balance) == -0.5
    state = skilled(state, 2, 14.0)
    state = run(loaded, state, AppointExecutive(FOUNDER, seat, 2))
    assert ex.effect_of(state, 1, seat, loaded.balance) == pytest.approx(0.5)
    if seat == "coo":
        assert ex.k_coo(state, 1, loaded.balance) == pytest.approx(1 - coefficient * 0.5)
    else:
        assert ex.multiplier(state, 1, seat, loaded.balance) == pytest.approx(1 + coefficient * 0.5)


def test_seats_reach_output_features_marketing_capacity_and_value(loaded: LoadedData) -> None:
    state, _, _ = _deep_team(loaded, game(loaded, staff=8))
    vacant = team_of(
        state, org_view(state, 1), state.products[-1], loaded.balance, loaded.game_data
    )
    assert vacant.feature_mult == pytest.approx(1 - 0.15 * 0.5)  # CPO vacant
    for pid, seat in zip(range(5, 10), ("cpo", "cmo", "cfo", "cto", "cro"), strict=True):
        state = skilled(state, pid, 18.0)  # s = 18: e = 1
        state = run(loaded, state, AppointExecutive(FOUNDER, seat, pid))
    team = team_of(state, org_view(state, 1), state.products[-1], loaded.balance, loaded.game_data)
    assert team.feature_mult == pytest.approx(1.15)
    pools = support_pools(state, org_view(state, 1), loaded.balance, loaded.game_data)
    assert team.marketing_mult == pytest.approx(
        (1 - 0.15 * (1 - pools[None].coverage) * 1.25) * 1.20
    )
    raw = base_value(  # seats not in play: V_base without the CFO term
        with_company(state, replace(state.player, stage=2)), 1, loaded.balance, loaded.game_data
    )
    assert base_value(state, 1, loaded.balance, loaded.game_data) == round(raw * 1.08)
    assert ex.cfo_confidence(state, 1, loaded.balance) == pytest.approx(0.5)


# --- Support and shared services (18.4) -----------------------------------------------------


def test_support_pools_central_and_embedded(loaded: LoadedData) -> None:
    """Central: corporate and central divisions share their support staff. Embedded: a
    division's own pool, its own support only, and the 1.05 bonus."""
    state = game(loaded, staff=30)
    state = with_employee(
        loaded, state, make_person(loaded, 50, "finance_manager", "senior"), 9_000_000
    )
    state = run(loaded, state, CreateUnit(FOUNDER, "division", "Fintech"))
    div = state.units[-1].id
    state = run(loaded, state, *(MovePerson(FOUNDER, p, div) for p in range(2, 17)))
    view = org_view(state, 1)
    pools = support_pools(state, view, loaded.balance, loaded.game_data)
    assert list(pools) == [None]
    assert (pools[None].headcount, pools[None].support, pools[None].need) == (32, 1, 3)
    assert pools[None].coverage == pytest.approx(1 / (32 / 15))
    state = run(loaded, state, SetSharedServices(FOUNDER, div, "embedded"))
    view = org_view(state, 1)
    pools = support_pools(state, view, loaded.balance, loaded.game_data)
    assert (pools[div].headcount, pools[div].support, pools[div].coverage) == (15, 0, 0.0)
    assert (pools[None].headcount, pools[None].support) == (17, 1)
    mods = modifiers(state, view, loaded.balance, loaded.game_data)
    assert mods is not None
    k = 1.25  # COO vacant
    cto = 0.95
    assert mods.builder[2] == pytest.approx((1 - 0.15 * k) * 1.05 * cto)
    employment = state.employment_of(2)
    assert employment is not None
    terms = morale_terms(state, view, employment, loaded.balance, loaded.game_data, 0, 0)
    assert terms.support == pytest.approx(-6.0)
    with pytest.raises(OrgRuleError, match="already"):
        act(loaded, state, SetSharedServices(FOUNDER, div, "embedded"))


def test_full_coverage_has_no_shortfall(loaded: LoadedData) -> None:
    state = game(loaded, staff=13)
    state = with_employee(loaded, state, make_person(loaded, 60, "recruiter", "senior"), 9_000_000)
    view = org_view(state, 1)
    pools = support_pools(state, view, loaded.balance, loaded.game_data)
    assert pools[None].coverage == 1.0
    employment = state.employment_of(2)
    assert employment is not None
    terms = morale_terms(state, view, employment, loaded.balance, loaded.game_data, 0, 0)
    assert terms.support == 0.0


def test_seat_holders_count_as_support(loaded: LoadedData) -> None:
    state = game(loaded, staff=20)
    state = run(loaded, state, AppointExecutive(FOUNDER, "cto", 2))
    pools = support_pools(state, org_view(state, 1), loaded.balance, loaded.game_data)
    assert pools[None].support == 1


# --- Exec searches (18.3) -------------------------------------------------------------------


def test_exec_search_generates_exec_candidates(loaded: LoadedData) -> None:
    state = game(loaded)
    state = run(loaded, state, OpenSearch(FOUNDER, "software_engineer", "network", level="exec"))
    assert state.searches[-1].level == "exec"
    state, _ = candidate_batches(state, RngFactory(3), loaded.balance, loaded.game_data)
    levels = {state.person(c.person_id).level for c in state.candidates}
    assert levels == {"exec"}
