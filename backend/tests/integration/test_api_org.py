"""M2a API: org tree, reorganizations and their previews, raises and promotions, hiring
plans, the morale breakdown, and org metadata. Every response is checked for hidden fields.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import make_person, move_save_directors, with_employee
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.state import with_person

SAVE = "org"
BASE = f"/api/saves/{SAVE}"
FOUNDER = 1


def seed_staff(
    path: Path, loaded: LoadedData, count: int, leaders: tuple[int, ...] = (), **tags: str
) -> None:
    """Put `count` employees (ids 2..) on the books. `leaders` get leadership 14,
    communication 12, mentoring 10; `tags` maps "p<id>" to one true tag."""
    move_save_directors(path)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = before
        for pid in range(2, 2 + count):
            person = make_person(loaded, pid, "software_engineer", "mid")
            person = replace(person, tags=(tags[f"p{pid}"],) if f"p{pid}" in tags else ())
            if pid in leaders:
                person = replace(
                    person,
                    skills=person.skills.updated(
                        {"leadership": 14, "communication": 12, "mentoring": 10}
                    ),
                )
            state = with_employee(loaded, state, person, 9_000_000)
            state = with_person(state, person)
        # Like a real hire, the company knows its employees' interests and work style.
        state = replace(
            state,
            reveals=tuple(replace(r, profile_revealed_turn=0) for r in state.reveals),
            next_ids=replace(state.next_ids, person=2 + count),
        )
        sync_state(session, before, state)


@pytest.fixture
def make_api(tmp_path: Path, loaded: LoadedData) -> Iterator[Any]:
    clients: list[TestClient] = []

    def build(count: int, leaders: tuple[int, ...] = (), **tags: str) -> Client:
        save_dir = tmp_path / "saves"
        path = create_save(
            SAVE, 11, "funded_spinout", company_name="Org Co", data=loaded, save_dir=save_dir
        )
        seed_staff(path, loaded, count, leaders, **tags)
        app = create_app()
        app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
        client = TestClient(app)
        clients.append(client)
        return Client(client)

    yield build
    for c in clients:
        c.close()


def term(breakdown: dict[str, Any], key: str) -> float:
    return next(t["value"] for t in breakdown["terms"] if t["key"] == key)


def morale(api: Client) -> dict[int, float]:
    return {p["person_id"]: p["morale"] for p in api.get(f"{BASE}/people") if not p["is_founder"]}


def test_three_level_org_from_the_api(make_api: Any) -> None:
    """Acceptance: company -> department -> team, with leaders, built through the API."""
    api = make_api(11, leaders=(2, 3))
    org = api.get(f"{BASE}/org")
    assert org["departments_unlocked"] and org["headcount"] == 12
    assert [u["kind"] for u in org["units"]] == ["company"]
    dept = api.post(f"{BASE}/org/units", {"kind": "department", "name": "Engineering"}, 201)
    dept_id = dept["org"]["units"][1]["unit_id"]
    team = api.post(
        f"{BASE}/org/units", {"kind": "team", "name": "Platform", "parent_id": dept_id}, 201
    )
    team_id = team["org"]["units"][2]["unit_id"]
    for pid in (2, 4, 5):
        api.post(f"{BASE}/org/people/{pid}/move", {"unit_id": dept_id})
    for pid in (3, 6, 7, 8):
        api.post(f"{BASE}/org/people/{pid}/move", {"unit_id": team_id})
    api.post(f"{BASE}/org/units/{dept_id}/leader", {"person_id": 2})
    out = api.post(f"{BASE}/org/units/{team_id}/leader", {"person_id": 3})
    org = out["org"]
    root, eng, platform = org["units"]
    assert (root["kind"], root["leader_id"], eng["leader_id"], platform["leader_id"]) == (
        "company",
        FOUNDER,
        2,
        3,
    )
    assert platform["parent_id"] == dept_id and eng["child_unit_ids"] == [team_id]
    managers = {m["person_id"]: m for m in org["managers"]}
    members = {m["person_id"]: m for u in org["units"] for m in u["members"]}
    assert members[3]["manager_id"] == 2  # the team lead reports to the department head
    assert members[6]["manager_id"] == 3 and members[4]["manager_id"] == 2
    assert members[2]["manager_id"] == FOUNDER
    assert managers[2]["reports"] == [3, 4, 5] and managers[2]["leads_unit_id"] == dept_id
    assert managers[3]["span_limit"] == 8 and managers[3]["span_factor"] == 1
    assert out["energy"]["energy"] == 60 - 2 * 2 - 7 * 1 - 2 * 2


def test_founder_penalty_and_two_leads_remove_it(make_api: Any) -> None:
    """Acceptance: 12 direct reports cost each employee 3.68 morale points of target; with
    two capable leads the founder manages two and their teams manage the rest."""
    api = make_api(12, leaders=(2, 3))
    org = api.get(f"{BASE}/org")
    founder = next(m for m in org["managers"] if m["person_id"] == FOUNDER)
    assert (founder["span_limit"], len(founder["reports"]), founder["over_span"]) == (7, 12, True)
    flat = api.get(f"{BASE}/people/9/morale")
    assert term(flat, "manager") == pytest.approx(-3.68, abs=5e-3)
    assert flat["manager_id"] == FOUNDER

    for name, lead, people in (("A", 2, range(4, 9)), ("B", 3, range(9, 14))):
        unit = api.post(f"{BASE}/org/units", {"kind": "team", "name": name}, 201)
        unit_id = unit["org"]["units"][-1]["unit_id"]
        for pid in (lead, *people):
            api.post(f"{BASE}/org/people/{pid}/move", {"unit_id": unit_id})
        api.post(f"{BASE}/org/units/{unit_id}/leader", {"person_id": lead})
    led = api.get(f"{BASE}/people/9/morale")
    assert led["manager_id"] == 3
    assert term(led, "manager") == pytest.approx(2.0)  # Q = 12.5 with 5 reports
    assert term(api.get(f"{BASE}/people/2/morale"), "manager") == pytest.approx(-0.60)
    founder = next(m for m in api.get(f"{BASE}/org")["managers"] if m["person_id"] == FOUNDER)
    assert founder["reports"] == [2, 3] and not founder["over_span"]


@pytest.mark.parametrize(
    ("setup", "change", "expected"),
    [
        ([], {"change": "move_person", "person_id": 2, "unit_id": 1}, {2: -2}),
        ([], {"change": "set_leader", "unit_id": 1, "person_id": 3}, {4: -1}),
        ([("lead", 3)], {"change": "set_leader", "unit_id": 1, "person_id": 4}, {3: -5}),
        ([], {"change": "dissolve_unit", "unit_id": 1}, {3: -2, 4: -2}),
        ([], {"change": "create_unit", "kind": "team", "name": "New"}, {}),
    ],
)
def test_reorg_preview_matches_the_action(
    make_api: Any, setup: list[tuple[str, int]], change: dict[str, Any], expected: dict[int, int]
) -> None:
    """Acceptance: each reorganization's one-off morale change matches formulas.md 13.7, and
    the preview reports it before the action."""
    api = make_api(4)
    api.post(f"{BASE}/org/units", {"kind": "team", "name": "Platform"}, 201)
    for pid in (3, 4):
        api.post(f"{BASE}/org/people/{pid}/move", {"unit_id": 1})
    for _, pid in setup:
        api.post(f"{BASE}/org/units/1/leader", {"person_id": pid})
    preview = api.post(f"{BASE}/org/preview", change)
    assert preview["allowed"] and preview["problem"] is None
    assert {c["person_id"]: c["change"] for c in preview["morale_changes"]} == expected
    before = morale(api)
    match change["change"]:
        case "move_person":
            api.post(
                f"{BASE}/org/people/{change['person_id']}/move", {"unit_id": change["unit_id"]}
            )
        case "set_leader":
            api.post(f"{BASE}/org/units/1/leader", {"person_id": change["person_id"]})
        case "dissolve_unit":
            api.post(f"{BASE}/org/units/1/dissolve")
        case "create_unit":
            api.post(f"{BASE}/org/units", {"kind": "team", "name": "New"}, 201)
    after = morale(api)
    assert {p: after[p] - before[p] for p in after if after[p] != before[p]} == pytest.approx(
        expected
    )
    assert preview["energy_cost"] in (1, 2)


def test_preview_reports_problems(make_api: Any) -> None:
    api = make_api(2)
    refused = api.post(
        f"{BASE}/org/preview", {"change": "create_unit", "kind": "department", "name": "D"}
    )
    assert not refused["allowed"] and "departments unlock at 10" in refused["problem"]
    error = api.post(f"{BASE}/org/units", {"kind": "department", "name": "D"}, 400)
    assert error["code"] == "org_rule"
    assert api.post(f"{BASE}/org/units/9/dissolve", status=404)["code"] == "unknown_unit"
    assert api.post(f"{BASE}/org/preview", {"change": "dissolve_unit"}, 400)["code"] == (
        "invalid_action"
    )


def test_raise_and_promotion_previews_and_actions(make_api: Any) -> None:
    api = make_api(2)
    person = api.get(f"{BASE}/people/2")
    market = person["employment"]["market_rate_cents"]
    preview = api.post(f"{BASE}/people/2/raise-preview", {"salary_cents": 9_450_000})
    assert preview["allowed"] and preview["morale_change"] == 3 and preview["energy_cost"] == 2
    assert (preview["salary_cents"], preview["new_salary_cents"]) == (9_000_000, 9_450_000)
    assert preview["market_rate_cents"] == market == preview["new_market_rate_cents"]
    assert preview["new_pay_term"] > preview["pay_term"]
    before = person["morale"]
    raised = api.post(f"{BASE}/people/2/raise", {"salary_cents": 9_450_000})
    assert raised["employment"]["salary_cents"] == 9_450_000
    assert raised["morale"] == pytest.approx(before + 3)
    again = api.post(f"{BASE}/people/2/raise-preview", {"salary_cents": 10_000_000})
    assert again["morale_change"] == 0  # once per 12 turns
    cut = api.post(f"{BASE}/people/2/raise-preview", {"salary_cents": 8_000_000})
    assert cut["morale_change"] == -10

    promo = api.post(f"{BASE}/people/2/promote-preview")
    assert (promo["level"], promo["new_level"], promo["morale_change"]) == ("mid", "senior", 5)
    assert promo["new_market_rate_cents"] > promo["market_rate_cents"]
    assert promo["new_pay_term"] < promo["pay_term"]  # promote and raise together
    promoted = api.post(f"{BASE}/people/2/promote")
    assert promoted["employment"]["level"] == "senior"
    founder = api.post(f"{BASE}/people/1/promote-preview")
    assert not founder["allowed"] and "founder" in founder["problem"]


def test_hiring_plans(make_api: Any) -> None:
    api = make_api(2)
    assert api.get(f"{BASE}/hiring-plans") == []
    plan = api.post(
        f"{BASE}/hiring-plans",
        {"owner_id": 2, "role": "designer", "target": 2, "channel": "any", "ratio_bp": 11_000},
        201,
    )
    assert (plan["plan_id"], plan["status"], plan["unit_name"], plan["owner_energy"]) == (
        1,
        "active",
        "Org Co",
        100,
    )
    assert plan["last_activity"] is None
    api.post(f"{BASE}/advance")
    (listed,) = api.get(f"{BASE}/hiring-plans")
    activity = listed["last_activity"]
    assert activity["turn"] == 0 and activity["searches"] == 1
    assert activity["summary"] == "opened a new search"
    inbox = api.get(f"{BASE}/inbox")["items"]
    assert any(i["kind"] == "plan_activity" for i in inbox)
    unit = api.post(f"{BASE}/org/units", {"kind": "team", "name": "Design"}, 201)
    unit_id = unit["org"]["units"][-1]["unit_id"]
    patched = api.call("PATCH", f"{BASE}/hiring-plans/1", json={"target": 3, "unit_id": unit_id})
    assert (patched["target"], patched["unit_name"], patched["owner_id"]) == (3, "Design", 2)
    patched = api.call("PATCH", f"{BASE}/hiring-plans/1", json={"unit_id": None})
    assert patched["unit_id"] is None and patched["target"] == 3
    closed = api.post(f"{BASE}/hiring-plans/1/close")
    assert closed["status"] == "closed"
    assert api.get(f"{BASE}/hiring-plans") == []
    assert api.post(f"{BASE}/hiring-plans/1/close", status=404)["code"] == "unknown_plan"
    bad = {"owner_id": 1, "role": "designer", "target": 1, "ratio_bp": 10_000}
    assert api.post(f"{BASE}/hiring-plans", bad, 400)["code"] == "org_rule"


def test_hidden_teammate_tag_shows_only_as_other(make_api: Any) -> None:
    """Acceptance: an unnoticed culture carrier's +2 is in "other", never named; once noticed
    it appears as a teammate term. No response carries the hidden tag. (Until M6 this used a
    toxic teammate; from M6 that tag acts through relationships, 16.7.)"""
    api = make_api(3, p3="culture_carrier")
    api.post(f"{BASE}/org/units", {"kind": "team", "name": "Platform"}, 201)
    for pid in (2, 3):
        api.post(f"{BASE}/org/people/{pid}/move", {"unit_id": 1})
    breakdown = api.get(f"{BASE}/people/2/morale")
    keys = [t["key"] for t in breakdown["terms"]]
    assert all(not k.startswith("teammate:") for k in keys)
    assert term(breakdown, "other") == pytest.approx(2.0)
    assert sum(t["value"] for t in breakdown["terms"]) == pytest.approx(breakdown["target"])
    for url in (f"{BASE}/people/2/morale", f"{BASE}/org", f"{BASE}/people", f"{BASE}/people/3"):
        assert "culture" not in json.dumps(api.get(url)), url
    assert term(api.get(f"{BASE}/people/4/morale"), "other") == 0  # not in the unit


def test_noticed_teammate_tag_is_named(make_api: Any, loaded: LoadedData, tmp_path: Path) -> None:
    api = make_api(3, p3="culture_carrier")
    api.post(f"{BASE}/org/units", {"kind": "team", "name": "Platform"}, 201)
    for pid in (2, 3):
        api.post(f"{BASE}/org/people/{pid}/move", {"unit_id": 1})
    path = tmp_path / "saves" / f"{SAVE}.tst.sqlite"
    with open_session(path) as session, session.begin():
        before = load_state(session)
        reveal = before.reveal(1, 3)
        assert reveal is not None
        state = replace(
            before,
            reveals=tuple(
                replace(r, revealed_tags=(("culture_carrier", 0),)) if r is reveal else r
                for r in before.reveals
            ),
        )
        sync_state(session, before, state)
    breakdown = api.get(f"{BASE}/people/2/morale")
    assert term(breakdown, "teammate:culture_carrier") == 2
    assert term(breakdown, "other") == pytest.approx(0.0)


def test_org_meta(make_api: Any) -> None:
    api = make_api(0)
    meta = api.get("/api/meta/org")
    assert meta["energy_costs"] == {
        "create_unit": 2,
        "dissolve_unit": 2,
        "move_unit": 2,
        "set_leader": 2,
        "move_person": 1,
        "set_policy": 1,
        "give_raise": 2,
        "promote": 3,
        "hiring_plan": 2,
    }
    assert (meta["department_unlock_headcount"], meta["department_unlock_stage"]) == (10, 2)
    assert meta["policies"] == ["office", "remote"] and meta["max_ratio_bp"] == 12_000
    assert meta["reorg_morale"]["replaced_leader"] == -5
    assert meta["promotion_levels"][-1] == "principal"


def test_remote_policy_through_the_api(make_api: Any) -> None:
    api = make_api(2)
    out = api.post(f"{BASE}/org/policy", {"unit_id": None, "policy": "remote"})
    root = out["org"]["units"][0]
    assert root["effective_policy"] == "remote" and all(m["remote"] for m in root["members"])
    ov = api.get(f"{BASE}/overview")
    assert all(c["account"] != "6100_rent" for c in ov["month_costs"])
    person = api.get(f"{BASE}/people/2")
    salary = person["employment"]["salary_cents"]
    monthly = round(salary / 12)
    assert person["employment"]["monthly_cost_cents"] == monthly + round(monthly * 0.2)


def test_move_unit_through_the_api(make_api: Any) -> None:
    api = make_api(10, leaders=(2, 3))
    api.post(f"{BASE}/org/units", {"kind": "department", "name": "Eng"}, 201)
    api.post(f"{BASE}/org/units", {"kind": "team", "name": "Web"}, 201)
    for pid, unit in ((2, 1), (3, 2), (4, 2)):
        api.post(f"{BASE}/org/people/{pid}/move", {"unit_id": unit})
    api.post(f"{BASE}/org/units/1/leader", {"person_id": 2})
    api.post(f"{BASE}/org/units/2/leader", {"person_id": 3})
    preview = api.post(f"{BASE}/org/preview", {"change": "move_unit", "unit_id": 2, "parent_id": 1})
    assert preview == {"allowed": True, "problem": None, "energy_cost": 2, "morale_changes": []}
    out = api.post(f"{BASE}/org/units/2/move", {"parent_id": 1})
    root, eng, web = out["org"]["units"]
    assert web["parent_id"] == 1 and eng["child_unit_ids"] == [2] and root["child_unit_ids"] == [1]
    members = {m["person_id"]: m for u in out["org"]["units"] for m in u["members"]}
    assert members[3]["manager_id"] == 2
    refused = api.post(
        f"{BASE}/org/preview", {"change": "move_unit", "unit_id": 1, "parent_id": None}
    )
    assert not refused["allowed"] and "only teams move" in refused["problem"]
    assert api.post(f"{BASE}/org/units/1/move", {"parent_id": None}, 400)["code"] == "org_rule"


def test_plan_focus_through_the_api(make_api: Any) -> None:
    api = make_api(2)
    body = {"owner_id": 2, "role": "designer", "target": 1, "ratio_bp": 10_000}
    assert api.post(f"{BASE}/hiring-plans", body, 201)["focus"] == "current"
    plan = api.post(f"{BASE}/hiring-plans", {**body, "focus": "potential"}, 201)
    assert plan["focus"] == "potential"
    patched = api.call("PATCH", f"{BASE}/hiring-plans/{plan['plan_id']}", json={"focus": "current"})
    assert patched["focus"] == "current" and patched["target"] == 1
    bad = api.post(f"{BASE}/hiring-plans", {**body, "focus": "hunch"}, 400)
    assert bad["code"] == "invalid_action"
