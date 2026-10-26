"""M2b API additions the screens need: unit rename, unit headcounts, manager labels, a person's
unit and manager, raise ratios, the Overview org tile, inbox paging, and plan owner status."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.test_api_org import BASE, make_api  # noqa: F401 - fixture
from tests.unit.test_org_actions import act, org_game, run
from tst.loader import LoadedData
from tst.sim.actions import CreateUnit, RenameUnit, action_from_payload, action_payload
from tst.sim.errors import OrgRuleError, UnknownUnitError
from tst.sim.org.formulas import manager_label


def test_rename_unit_in_the_sim(loaded: LoadedData) -> None:
    state = run(loaded, org_game(loaded), CreateUnit(1, "team", "A"), CreateUnit(1, "team", "B"))
    energy = state.person_state(1).energy
    renamed = run(loaded, state, RenameUnit(1, 1, "  Platform  "))
    assert renamed.unit(1).name == "Platform"  # type: ignore[union-attr]
    assert renamed.person_state(1).energy == energy  # free
    for bad, error in (
        (RenameUnit(1, 1, "B"), OrgRuleError),
        (RenameUnit(1, 1, "A"), OrgRuleError),
        (RenameUnit(1, 9, "C"), UnknownUnitError),
    ):
        with pytest.raises(error):
            act(loaded, state, bad)
    assert action_from_payload(action_payload(RenameUnit(1, 1, "X"))) == RenameUnit(1, 1, "X")


@pytest.mark.parametrize(
    ("term", "label"), [(2.0, "strong"), (1.9, "fine"), (-1.9, "fine"), (-2.0, "stretched")]
)
def test_manager_label_bands(loaded: LoadedData, term: float, label: str) -> None:
    assert manager_label(term, loaded.balance.org) == label


def test_org_counts_labels_and_person_org(make_api: Any) -> None:  # noqa: F811
    api = make_api(12, leaders=(2,))
    org = api.get(f"{BASE}/org")
    founder = next(m for m in org["managers"] if m["person_id"] == 1)
    assert founder["over_span"] and founder["label"] == "stretched"  # 12 reports: W -3.68
    assert org["managers_over_span"] == 1 and org["units"][0]["headcount"] == 13
    api.post(f"{BASE}/org/units", {"kind": "department", "name": "Eng"}, 201)
    api.post(f"{BASE}/org/units", {"kind": "team", "name": "Web", "parent_id": 1}, 201)
    for pid in (2, 3):
        api.post(f"{BASE}/org/people/{pid}/move", {"unit_id": 1})
    for pid in (4, 5, 6):
        api.post(f"{BASE}/org/people/{pid}/move", {"unit_id": 2})
    out = api.post(f"{BASE}/org/units/1/leader", {"person_id": 2})
    root, eng, web = out["org"]["units"]
    assert (root["headcount"], eng["headcount"], web["headcount"]) == (13, 5, 3)
    lead = next(m for m in out["org"]["managers"] if m["person_id"] == 2)
    assert lead["label"] == "strong"  # leadership 14 with 4 reports: W +2.0
    renamed = api.post(f"{BASE}/org/units/2/rename", {"name": "Platform"})
    assert renamed["org"]["units"][2]["name"] == "Platform"
    assert renamed["energy"]["energy"] == out["energy"]["energy"]
    preview = api.post(
        f"{BASE}/org/preview", {"change": "rename_unit", "unit_id": 2, "name": "Eng"}
    )
    assert not preview["allowed"] and "already a unit" in preview["problem"]

    person = api.get(f"{BASE}/people/4")
    assert person["org"] == {
        "unit_id": 2,
        "unit_name": "Platform",
        "parent_unit_name": "Eng",
        "manager_id": 2,
        "manager_name": person["org"]["manager_name"],
        "leads_unit_id": None,
    }
    lead_person = next(p for p in api.get(f"{BASE}/people") if p["person_id"] == 2)
    assert lead_person["org"]["leads_unit_id"] == 1 and lead_person["org"]["manager_id"] == 1
    founder_person = api.get(f"{BASE}/people/1")
    assert founder_person["org"]["manager_id"] is None and founder_person["energy"] is not None


def test_raise_preview_ratios_and_costs(make_api: Any) -> None:  # noqa: F811
    api = make_api(1)
    market = api.get(f"{BASE}/people/2")["employment"]["market_rate_cents"]
    pv = api.post(f"{BASE}/people/2/raise-preview", {"salary_cents": 9_450_000})
    assert pv["salary_change_bp"] == 500
    assert pv["market_ratio"] == pytest.approx(9_000_000 / market)
    assert pv["new_market_ratio"] == pytest.approx(9_450_000 / market)
    assert pv["monthly_cost_change_cents"] == 45_000  # +$375 salary + $75 benefits a month
    promo = api.post(f"{BASE}/people/2/promote-preview")
    assert promo["below_market"] and promo["salary_change_bp"] == 0
    assert promo["new_market_ratio"] == pytest.approx(9_000_000 / promo["new_market_rate_cents"])


def test_overview_org_tile_pool_and_network_bonus(make_api: Any) -> None:  # noqa: F811
    api = make_api(12)
    ov = api.get(f"{BASE}/overview")
    assert ov["org"] == {"units": 0, "managers_over_span": 1, "manager_label": "stretched"}
    assert ov["option_pool_left_bp"] == 1000
    assert ov["network_bonus_candidates"] in (0, 1)
    api.post(f"{BASE}/org/units", {"kind": "team", "name": "A"}, 201)
    assert api.get(f"{BASE}/overview")["org"]["units"] == 1


def test_inbox_paging(make_api: Any) -> None:  # noqa: F811
    api = make_api(1)
    for _ in range(3):
        api.post(f"{BASE}/advance")
    api.post(
        f"{BASE}/recruitment/searches", {"role": "software_engineer", "channel": "network"}, 201
    )
    api.post(f"{BASE}/advance")
    everything = api.get(f"{BASE}/inbox")
    total = everything["total"]
    assert total == len(everything["items"]) and total >= 1
    page = api.get(f"{BASE}/inbox?limit=1&offset=0")
    assert page["total"] == total and len(page["items"]) == 1 and page["offset"] == 0
    last = api.get(f"{BASE}/inbox?limit=50&offset={total - 1}")
    assert [i["item_id"] for i in last["items"]] == [everything["items"][-1]["item_id"]]


def test_plan_owner_status(make_api: Any) -> None:  # noqa: F811
    api = make_api(2)
    body = {"owner_id": 2, "role": "designer", "target": 1, "ratio_bp": 10_000}
    plan = api.post(f"{BASE}/hiring-plans", body, 201)
    assert plan["owner_on_staff"] and plan["owner_role_label"] == "Software engineer"
    api.post(f"{BASE}/people/2/fire")
    (paused,) = api.get(f"{BASE}/hiring-plans")
    assert paused["status"] == "paused" and not paused["owner_on_staff"]
