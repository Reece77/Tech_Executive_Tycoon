"""Org actions (formulas.md 6, 13.1, 13.7-13.10): rules, energy and one-off morale."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, with_candidates, with_employee
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    ActionResult,
    ClosePlan,
    CreatePlan,
    CreateUnit,
    DissolveUnit,
    Fire,
    GiveRaise,
    MovePerson,
    MoveUnit,
    Promote,
    Scout,
    SetLeader,
    SetPolicy,
    UpdatePlan,
    action_from_payload,
    action_payload,
    apply_action,
)
from tst.sim.errors import (
    InsufficientEnergyError,
    InvalidActionError,
    OrgRuleError,
    SimError,
    UnknownPersonError,
    UnknownPlanError,
    UnknownUnitError,
)
from tst.sim.org.rules import org_view
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_company

FOUNDER = 1
START_MORALE = 60.0


def org_game(loaded: LoadedData, staff: int = 4) -> GameState:
    state = fresh_game(loaded)
    for pid in range(2, 2 + staff):
        state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000, morale=60)
    return state


def act(loaded: LoadedData, state: GameState, action: Action) -> ActionResult:
    return apply_action(
        state,
        action,
        RngFactory(state.save_meta.master_seed),
        loaded.balance,
        loaded.game_data,
        {},
        seq=1,
    )


def run(loaded: LoadedData, state: GameState, *actions: Action) -> GameState:
    for action in actions:
        state = act(loaded, state, action).new_state
    return state


def energy(state: GameState) -> int | None:
    return state.person_state(FOUNDER).energy


def morale(state: GameState, pid: int) -> float | None:
    return state.person_state(pid).morale


def with_team(loaded: LoadedData, state: GameState, *people: int) -> GameState:
    state = run(loaded, state, CreateUnit(FOUNDER, "team", "Platform"))
    return run(loaded, state, *(MovePerson(FOUNDER, p, 1) for p in people))


# --- Units ----------------------------------------------------------------------------------


def test_create_team_costs_energy_and_changes_no_morale(loaded: LoadedData) -> None:
    state = org_game(loaded)
    after = run(loaded, state, CreateUnit(FOUNDER, "team", "  Platform   team "))
    unit = after.units[0]
    assert (unit.id, unit.kind, unit.name, unit.parent_id, unit.leader_id) == (
        1,
        "team",
        "Platform team",
        None,
        None,
    )
    assert energy(after) == 98 and after.next_ids.unit == 2
    assert all(morale(after, p) == START_MORALE for p in range(2, 6))


@pytest.mark.parametrize(
    ("action", "error", "message"),
    [
        (CreateUnit(FOUNDER, "team", "   "), OrgRuleError, "needs a name"),
        (CreateUnit(FOUNDER, "team", "x" * 65), OrgRuleError, "at most 64"),
        (CreateUnit(FOUNDER, "team", "platform"), OrgRuleError, "already a unit"),
        (CreateUnit(FOUNDER, "squad", "Q"), OrgRuleError, "unknown unit kind"),  # type: ignore[arg-type]
        (CreateUnit(FOUNDER, "team", "Q", parent_id=1), OrgRuleError, "not a team"),
        (CreateUnit(FOUNDER, "team", "Q", parent_id=9), UnknownUnitError, "no unit 9"),
        (CreateUnit(FOUNDER, "department", "Eng"), OrgRuleError, "departments unlock at 10"),
        (CreateUnit(99, "team", "Q"), UnknownPersonError, "not on staff"),
    ],
)
def test_create_unit_rules(
    loaded: LoadedData, action: CreateUnit, error: type[SimError], message: str
) -> None:
    state = run(loaded, org_game(loaded), CreateUnit(FOUNDER, "team", "Platform"))
    with pytest.raises(error, match=message):
        act(loaded, state, action)


def test_departments_unlock_at_ten_staff_or_stage_two(loaded: LoadedData) -> None:
    nine = org_game(loaded, staff=8)
    with pytest.raises(OrgRuleError):
        act(loaded, nine, CreateUnit(FOUNDER, "department", "Eng"))
    ten = org_game(loaded, staff=9)
    state = run(loaded, ten, CreateUnit(FOUNDER, "department", "Eng"))
    assert state.units[0].kind == "department"
    state = run(loaded, state, CreateUnit(FOUNDER, "team", "Web", parent_id=1))
    assert state.units[1].parent_id == 1
    with pytest.raises(OrgRuleError, match="directly under the company"):
        act(loaded, state, CreateUnit(FOUNDER, "department", "Sub", parent_id=1))
    staged = with_company(nine, replace(nine.player, stage=2))
    assert run(loaded, staged, CreateUnit(FOUNDER, "department", "Eng")).units


def test_dissolve_moves_members_and_child_teams_to_the_parent(loaded: LoadedData) -> None:
    state = org_game(loaded, staff=9)
    state = run(
        loaded,
        state,
        CreateUnit(FOUNDER, "department", "Eng"),
        CreateUnit(FOUNDER, "team", "Web", parent_id=1),
        MovePerson(FOUNDER, 2, 1),
        MovePerson(FOUNDER, 3, 1),
        MovePerson(FOUNDER, 4, 2),
        SetLeader(FOUNDER, 1, 2),
        CreatePlan(FOUNDER, 3, "designer", 1, "network", 10_000, unit_id=1),
    )
    before = {p: morale(state, p) for p in (2, 3, 4)}
    spent = energy(state)
    after = run(loaded, state, DissolveUnit(FOUNDER, 1))
    assert energy(after) == (spent or 0) - 2
    assert after.unit(1) is not None and after.unit(1).status == "dissolved"  # type: ignore[union-attr]
    assert after.unit(2) is not None and after.unit(2).parent_id is None  # type: ignore[union-attr]
    assert [after.employment_of(p).unit_id for p in (2, 3, 4)] == [None, None, 2]  # type: ignore[union-attr]
    assert after.plans[0].unit_id is None
    assert morale(after, 2) == (before[2] or 0) - 2 and morale(after, 3) == (before[3] or 0) - 2
    assert morale(after, 4) == before[4]  # child-team members are not members of the unit
    with pytest.raises(UnknownUnitError):
        act(loaded, after, DissolveUnit(FOUNDER, 1))


# --- Leaders and moves ----------------------------------------------------------------------


def test_set_and_replace_leader_morale(loaded: LoadedData) -> None:
    state = with_team(loaded, org_game(loaded), 2, 3, 4)
    m = {p: morale(state, p) or 0 for p in (2, 3, 4, 5)}
    state = run(loaded, state, SetLeader(FOUNDER, 1, 2))
    assert state.units[0].leader_id == 2
    assert [morale(state, p) for p in (2, 3, 4, 5)] == [m[2], m[3] - 1, m[4] - 1, m[5]]
    state = run(loaded, state, SetLeader(FOUNDER, 1, 3))  # replaced: -5 for 2, -1 for 4
    assert [morale(state, p) for p in (2, 3, 4)] == [m[2] - 5, m[3] - 1, m[4] - 2]
    state = run(loaded, state, SetLeader(FOUNDER, 1, None))  # removed: -5 for 3, -1 for others
    assert state.units[0].leader_id is None
    assert [morale(state, p) for p in (2, 3, 4)] == [m[2] - 6, m[3] - 6, m[4] - 3]


@pytest.mark.parametrize(
    ("action", "message"),
    [
        (SetLeader(FOUNDER, 1, 5), "must be a member"),
        (SetLeader(FOUNDER, 1, FOUNDER), "founder cannot lead"),
        (SetLeader(FOUNDER, 1, 2), "already lead"),
        (SetLeader(FOUNDER, 2, 2), "must be a member"),  # so nobody can lead two units
        (MovePerson(FOUNDER, 2, None), "replace or remove them as leader"),
        (MovePerson(FOUNDER, 3, 1), "already in that unit"),
        (MovePerson(FOUNDER, FOUNDER, 1), "founder cannot"),
    ],
)
def test_leader_and_move_rules(loaded: LoadedData, action: Action, message: str) -> None:
    state = with_team(loaded, org_game(loaded), 2, 3)
    state = run(loaded, state, SetLeader(FOUNDER, 1, 2), CreateUnit(FOUNDER, "team", "Second"))
    state = run(loaded, state, MovePerson(FOUNDER, 4, 2))
    with pytest.raises(OrgRuleError, match=message):
        act(loaded, state, action)
    with pytest.raises(OrgRuleError, match="no leader to remove"):
        act(loaded, state, SetLeader(FOUNDER, 2, None))


def test_move_costs_one_energy_and_two_morale(loaded: LoadedData) -> None:
    state = run(loaded, org_game(loaded), CreateUnit(FOUNDER, "team", "Platform"))
    before = morale(state, 2) or 0
    after = run(loaded, state, MovePerson(FOUNDER, 2, 1))
    assert energy(after) == 97 and morale(after, 2) == before - 2
    assert after.employment_of(2).unit_id == 1  # type: ignore[union-attr]


def test_firing_a_leader_clears_the_post_and_pauses_their_plans(loaded: LoadedData) -> None:
    state = with_team(loaded, org_game(loaded), 2)
    state = run(
        loaded,
        state,
        SetLeader(FOUNDER, 1, 2),
        CreatePlan(FOUNDER, 2, "designer", 2, "network", 10_000),
    )
    out = act(loaded, state, Fire(FOUNDER, 2))
    assert out.new_state.units[0].leader_id is None
    assert out.new_state.plans[0].status == "paused"
    kinds = [i.template for i in out.log_items]
    assert kinds == ["fired", "unit_leader_left", "plan_paused"]


# --- Policies -------------------------------------------------------------------------------


def test_set_policy(loaded: LoadedData) -> None:
    state = run(loaded, org_game(loaded), CreateUnit(FOUNDER, "team", "Platform"))
    state = run(loaded, state, SetPolicy(FOUNDER, 1, "remote"))
    assert state.units[0].policy == "remote" and energy(state) == 97
    state = run(loaded, state, SetPolicy(FOUNDER, 1, None), SetPolicy(FOUNDER, None, "remote"))
    assert state.units[0].policy is None and state.player.work_policy == "remote"
    for bad, message in (
        (SetPolicy(FOUNDER, None, None), "no parent"),
        (SetPolicy(FOUNDER, None, "remote"), "already remote"),
        (SetPolicy(FOUNDER, 1, None), "already has"),
        (SetPolicy(FOUNDER, 1, "beach"), "unknown work-location"),  # type: ignore[arg-type]
    ):
        with pytest.raises(OrgRuleError, match=message):
            act(loaded, state, bad)


# --- Raises and promotions ------------------------------------------------------------------


def test_raise_morale_once_per_twelve_turns(loaded: LoadedData) -> None:
    state = org_game(loaded)
    start = morale(state, 2) or 0
    state = run(loaded, state, GiveRaise(FOUNDER, 2, 9_450_000))  # +5%
    employment = state.employment_of(2)
    assert employment is not None
    assert (employment.salary_cents, employment.last_raise_turn) == (9_450_000, 0)
    assert morale(state, 2) == start + 3 and energy(state) == 98
    state = run(loaded, state, GiveRaise(FOUNDER, 2, 10_000_000))  # again, within 12 turns
    assert morale(state, 2) == start + 3
    later = replace(state, turn=12)
    later = run(loaded, later, GiveRaise(FOUNDER, 2, 10_500_000))
    assert morale(later, 2) == start + 6
    assert later.employment_of(2).last_raise_turn == 12  # type: ignore[union-attr]


def test_small_raise_and_pay_cut(loaded: LoadedData) -> None:
    state = org_game(loaded)
    start = morale(state, 2) or 0
    state = run(loaded, state, GiveRaise(FOUNDER, 2, 9_449_999))  # under 5%: nothing
    assert morale(state, 2) == start
    assert state.employment_of(2).last_raise_turn is None  # type: ignore[union-attr]
    state = run(loaded, state, GiveRaise(FOUNDER, 2, 8_000_000))
    assert morale(state, 2) == start - 10
    for bad in (GiveRaise(FOUNDER, 2, 8_000_000), GiveRaise(FOUNDER, 2, 0)):
        with pytest.raises(InvalidActionError):
            act(loaded, state, bad)
    with pytest.raises(OrgRuleError, match="founder"):
        act(loaded, state, GiveRaise(FOUNDER, FOUNDER, 100))


def test_promote(loaded: LoadedData) -> None:
    state = org_game(loaded)
    start = morale(state, 2) or 0
    assert state.employment_of(2).level == "mid"  # type: ignore[union-attr]
    state = run(loaded, state, Promote(FOUNDER, 2))
    assert state.employment_of(2).level == "senior"  # type: ignore[union-attr]
    assert morale(state, 2) == start + 5 and energy(state) == 97
    state = run(loaded, state, Promote(FOUNDER, 2), Promote(FOUNDER, 2))
    assert state.employment_of(2).level == "principal"  # type: ignore[union-attr]
    with pytest.raises(InvalidActionError, match="highest level"):
        act(loaded, state, Promote(FOUNDER, 2))
    with pytest.raises(OrgRuleError, match="founder"):
        act(loaded, state, Promote(FOUNDER, FOUNDER))


# --- Hiring plans ---------------------------------------------------------------------------


def test_create_update_close_plan(loaded: LoadedData) -> None:
    state = run(loaded, org_game(loaded), CreateUnit(FOUNDER, "team", "Platform"))
    assert state.person_state(2).energy is None
    state = run(loaded, state, CreatePlan(FOUNDER, 2, "software_engineer", 3, "any", 11_000, 10, 1))
    plan = state.plans[0]
    assert (plan.id, plan.owner_id, plan.unit_id, plan.status, plan.hired) == (1, 2, 1, "active", 0)
    assert state.person_state(2).energy == 100  # the delegate's own budget
    assert energy(state) == 96
    update = UpdatePlan(FOUNDER, 1, 3, "designer", 1, "network", 12_000, 0, None)
    state = run(loaded, state, update)
    plan = state.plans[0]
    assert (plan.owner_id, plan.role, plan.unit_id, plan.ratio_bp) == (3, "designer", None, 12_000)
    assert energy(state) == 94
    state = run(loaded, state, ClosePlan(FOUNDER, 1))
    assert state.plans[0].status == "closed" and energy(state) == 94  # closing is free
    with pytest.raises(UnknownPlanError):
        act(loaded, state, ClosePlan(FOUNDER, 1))


@pytest.mark.parametrize(
    ("action", "error", "message"),
    [
        (CreatePlan(FOUNDER, FOUNDER, "designer", 1, "any", 10_000), OrgRuleError, "founder"),
        (CreatePlan(FOUNDER, 99, "designer", 1, "any", 10_000), UnknownPersonError, "staff"),
        (CreatePlan(FOUNDER, 2, "astronaut", 1, "any", 10_000), SimError, "unknown role"),
        (CreatePlan(FOUNDER, 2, "designer", 0, "any", 10_000), InvalidActionError, "target"),
        (CreatePlan(FOUNDER, 2, "designer", 1, "fax", 10_000), InvalidActionError, "channel"),  # type: ignore[arg-type]
        (CreatePlan(FOUNDER, 2, "designer", 1, "any", 12_001), InvalidActionError, "12000 bp"),
        (CreatePlan(FOUNDER, 2, "designer", 1, "any", 0), InvalidActionError, "ratio"),
        (CreatePlan(FOUNDER, 2, "designer", 1, "any", 10_000, 201), InvalidActionError, "equity"),
        (CreatePlan(FOUNDER, 2, "designer", 1, "any", 10_000, 0, 7), UnknownUnitError, "unit"),
    ],
)
def test_plan_rules(
    loaded: LoadedData, action: CreatePlan, error: type[SimError], message: str
) -> None:
    with pytest.raises(error, match=message):
        act(loaded, org_game(loaded), action)


def test_paused_plan_restarts_with_a_new_owner(loaded: LoadedData) -> None:
    state = run(
        loaded,
        org_game(loaded),
        CreatePlan(FOUNDER, 2, "designer", 2, "network", 10_000),
        Fire(FOUNDER, 2),
    )
    assert state.plans[0].status == "paused"
    state = run(loaded, state, UpdatePlan(FOUNDER, 1, 3, "designer", 2, "network", 10_000, 0, None))
    assert state.plans[0].status == "active" and state.plans[0].owner_id == 3


def test_scout_narrows_every_open_candidate_for_the_role(loaded: LoadedData) -> None:
    state = with_candidates(loaded, org_game(loaded), 3)
    state = run(loaded, state, CreatePlan(FOUNDER, 2, "software_engineer", 1, "any", 10_000))
    before = [state.reveal(1, c.person_id) for c in state.candidates]
    after = run(loaded, state, Scout(2, "software_engineer"))
    assert after.person_state(2).energy == 80 and energy(after) == energy(state)
    for old, cand in zip(before, after.candidates, strict=True):
        new = after.reveal(1, cand.person_id)
        assert old is not None and new is not None
        assert all(
            n.hw < o.hw for (_, o), (_, n) in zip(old.attributes, new.attributes, strict=True)
        )
    with pytest.raises(InvalidActionError, match="no open candidates"):
        act(loaded, after, Scout(2, "designer"))
    drained = after
    for _ in range(4):
        drained = run(loaded, drained, Scout(2, "software_engineer"))
    with pytest.raises(InsufficientEnergyError):
        act(loaded, drained, Scout(2, "software_engineer"))


def test_org_actions_round_trip_as_payloads() -> None:
    actions: list[Action] = [
        CreateUnit(1, "team", "A", None),
        DissolveUnit(1, 2),
        MoveUnit(1, 2, None),
        SetLeader(1, 2, None),
        MovePerson(1, 3, None),
        SetPolicy(1, None, "remote"),
        GiveRaise(1, 3, 100),
        Promote(1, 3),
        CreatePlan(1, 3, "designer", 2, "any", 10_000, 5, None),
        UpdatePlan(1, 1, 3, "designer", 2, "any", 10_000, 5, 2),
        ClosePlan(1, 1),
        Scout(3, "designer"),
    ]
    for action in actions:
        assert action_from_payload(action_payload(action)) == action


def test_energy_runs_out_for_org_actions(loaded: LoadedData) -> None:
    state = org_game(loaded)
    state = replace(
        state,
        person_states=tuple(
            replace(ps, energy=1) if ps.person_id == FOUNDER else ps for ps in state.person_states
        ),
    )
    with pytest.raises(InsufficientEnergyError):
        act(loaded, state, CreateUnit(FOUNDER, "team", "A"))


# --- Moving a team (13.1) -------------------------------------------------------------------


def test_move_unit_reparents_a_team(loaded: LoadedData) -> None:
    state = org_game(loaded, staff=9)
    state = run(
        loaded,
        state,
        CreateUnit(FOUNDER, "department", "Eng"),
        CreateUnit(FOUNDER, "team", "Web"),
        MovePerson(FOUNDER, 2, 2),
        MovePerson(FOUNDER, 3, 2),
        SetLeader(FOUNDER, 2, 2),
        MovePerson(FOUNDER, 4, 1),
        SetLeader(FOUNDER, 1, 4),
    )
    before = {p: morale(state, p) for p in range(2, 11)}
    spent = energy(state) or 0
    after = run(loaded, state, MoveUnit(FOUNDER, 2, 1))
    assert after.unit(2).parent_id == 1  # type: ignore[union-attr]
    assert energy(after) == spent - 2
    assert {p: morale(after, p) for p in range(2, 11)} == before  # no one-off morale
    view = org_view(after, 1)
    assert view.manager_of[2] == 4  # the team lead now reports to the department head
    back = run(loaded, after, MoveUnit(FOUNDER, 2, None))
    assert back.unit(2).parent_id is None  # type: ignore[union-attr]
    assert org_view(back, 1).manager_of[2] == FOUNDER


@pytest.mark.parametrize(
    ("action", "error", "message"),
    [
        (MoveUnit(FOUNDER, 1, None), OrgRuleError, "only teams move"),
        (MoveUnit(FOUNDER, 2, 3), OrgRuleError, "not a team"),
        (MoveUnit(FOUNDER, 2, None), OrgRuleError, "already there"),
        (MoveUnit(FOUNDER, 2, 9), UnknownUnitError, "no unit 9"),
        (MoveUnit(FOUNDER, 9, 1), UnknownUnitError, "no unit 9"),
    ],
)
def test_move_unit_rules(
    loaded: LoadedData, action: MoveUnit, error: type[SimError], message: str
) -> None:
    state = run(
        loaded,
        org_game(loaded, staff=9),
        CreateUnit(FOUNDER, "department", "Eng"),
        CreateUnit(FOUNDER, "team", "Web"),
        CreateUnit(FOUNDER, "team", "App"),
    )
    with pytest.raises(error, match=message):
        act(loaded, state, action)
