"""M23c (playtest 5) API: an event's links to the screens that matter for it, the how-to on every
greyed-out action, and the read-only display endpoints."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.loader import LoadedData

TOOLS = Path(__file__).resolve().parents[3] / "tools"
BASE = "/api/saves/{}"


def tool(name: str) -> Any:
    sys.path.insert(0, str(TOOLS))
    return __import__(name)


@pytest.fixture
def saves(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def api(saves: Path) -> Iterator[Client]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as client:
        yield Client(client)


def test_a_mine_crash_links_to_its_mine(api: Client, saves: Path, loaded: LoadedData) -> None:
    tool("e2e_m19_save").crash(saves, "crash", loaded)
    base = BASE.format("crash")
    events = api.get(f"{base}/events")
    crash = next(e for e in events["open"] if e["template_id"] == "mine_price_crash")
    mine = api.get(f"{base}/mines")["mines"][0]
    paths = [link["path"] for link in crash["links"]]
    assert paths[0] == f"products/mines?mine={mine['id']}"
    assert crash["links"][0]["label"] == mine["name"]
    assert "products/mines" in paths and "finance/statements" in paths


# --- Every greyed-out action says how to unlock it (sub-task 3's scan) ---------------------

NEXT_STEP = (
    "none:",
    "wait",
    "drill",
    "run ",
    "re-run",
    "start",
    "finish",
    "win",
    "choose",
    "raise",
    "reach",
    "build",
    "fix",
)


def _scan(items: list[dict[str, Any]], where: str, allowed: str = "allowed") -> int:
    """Every disallowed item says how to unlock it, as a next step (not the bare reason)."""
    n = 0
    for item in items:
        if item[allowed]:
            continue
        n += 1
        how = item["how"]
        assert how, f"{where}: {item} has no how"
        assert how.startswith(NEXT_STEP), f"{where}: {how!r} is not a next step"
        assert how != item.get("reason"), f"{where}: how repeats the reason"
    return n


@pytest.mark.parametrize("mode", ["explorer", "sampled", "protest", "permitted"])
def test_every_greyed_out_exploration_stage_says_how(
    api: Client, saves: Path, loaded: LoadedData, mode: str
) -> None:
    getattr(tool("e2e_m18_save"), mode)(saves, mode, loaded)
    base = BASE.format(mode)
    x = api.get(f"{base}/exploration")
    if not x["projects"]:  # the explorer save has none: licence one, as the player would
        free = next(b for b in x["blocks"] if b["holder"] is None)
        api.post(
            f"{base}/exploration/licence", json={"region": free["region"], "block": free["index"]}
        )
        x = api.get(f"{base}/exploration")
    greyed = 0
    for p in x["projects"]:
        greyed += _scan(p["options"], f"{mode} project {p['id']}")
        assert p["holes_for_next"] is None or p["holes_for_next"] > 0
        if not p["renewable"]:
            assert p["renew_how"].startswith("none:")
    assert greyed > 0  # the scan saw greyed-out stages


def test_the_estimate_says_how_many_more_holes(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    tool("e2e_m18_save").sampled(saves, "s", loaded)
    p = api.get(f"{BASE.format('s')}/exploration")["projects"][0]
    estimate = next(o for o in p["options"] if o["stage"] == "estimate")
    need = loaded.balance.exploration.estimate.inferred
    if not estimate["allowed"] and p["stage"] is None and not p["holes_left"]:
        left = need - p["holes_drilled"]
        assert estimate["how"].startswith(f"drill {left} more holes ({need} in total)")
    definitive = next(o for o in p["options"] if o["stage"] == "definitive")
    assert not definitive["allowed"] and definitive["how"]
    assert p["next_step"].startswith("next: ")


@pytest.mark.parametrize(
    ("module", "mode"),
    [("e2e_m19_save", "holder"), ("e2e_m19_save", "building"), ("e2e_m18_save", "permitted")],
)
def test_every_greyed_out_mine_action_says_how(
    api: Client, saves: Path, loaded: LoadedData, module: str, mode: str
) -> None:
    getattr(tool(module), mode)(saves, mode, loaded)
    m = api.get(f"{BASE.format(mode)}/mines")
    _scan(m["quotes"], f"{mode} mine quotes")
    if m["group_stage"] < m["found_min_stage"]:
        assert m["found_how"].startswith("reach company stage")
    else:
        assert m["found_how"] == ""


@pytest.mark.parametrize("mode", ["smelter", "wafers"])
def test_every_greyed_out_refinery_build_says_how(
    api: Client, saves: Path, loaded: LoadedData, mode: str
) -> None:
    getattr(tool("e2e_m20_save"), mode)(saves, mode, loaded)
    base = BASE.format(mode)
    r = api.get(f"{base}/refineries")
    quotes = []
    for recipe in r["recipes"]:
        for region in ("europe", "east_asia"):
            q = f"recipe={recipe['key']}&region={region}&size={recipe['sizes'][0]}"
            quotes.append(api.get(f"{base}/refineries/quote?{q}"))
    _scan(quotes, f"{mode} refinery quotes")
    assert all("build or buy a refinery" in q["how"] for q in quotes if not q["allowed"])


@pytest.mark.parametrize("mode", ["nodes", "mature", "euv"])
def test_every_greyed_out_fab_action_says_how(
    api: Client, saves: Path, loaded: LoadedData, mode: str
) -> None:
    getattr(tool("e2e_m21_save"), mode)(saves, mode, loaded)
    base = BASE.format(mode)
    fabs = api.get(f"{base}/fabs")
    quotes = [
        api.get(f"{base}/fabs/quote?node={n['key']}&region=east_asia&size={fabs['sizes'][0]}")
        for n in fabs["timeline"]["nodes"]
    ]
    greyed = _scan(quotes, f"{mode} fab quotes")
    for f in fabs["fabs"]:
        if not f["upgrade_allowed"]:
            assert f["upgrade_how"], f
    assert greyed > 0  # the newest nodes are out of reach in every one of these saves


# --- The group: capital actions' history and the CEOs' quarterly updates (sub-task 4) -------


def test_capital_actions_are_tracked_with_what_they_accomplished(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    tool("e2e_m16_save").formed(saves, "g", loaded)
    base = BASE.format("g")
    assert api.get(f"{base}/group/history")["actions"] == []
    sub = next(e for e in api.get(f"{base}/group")["entities"] if e["role"] == "subsidiary")
    api.post(f"{base}/group/sell-stake", json={"company_id": sub["company_id"], "stake_bp": 3000})
    sale = api.get(f"{base}/group/history")["actions"][0]
    assert sale["kind"] == "stake_sale" and sale["company"] == sub["name"]
    assert (sale["stake_before_bp"], sale["stake_after_bp"]) == (10_000, 7_000)
    assert sale["proceeds_cents"] > 0 and sale["nci_cents"] != 0
    assert sale["value_note"]
    api.post(f"{base}/group/companies/{sub['company_id']}/buy-out")
    actions = api.get(f"{base}/group/history")["actions"]
    kinds = sorted(a["kind"] for a in actions)
    assert kinds == ["buyout", "stake_sale"]
    buyout = next(a for a in actions if a["kind"] == "buyout")
    assert buyout["proceeds_cents"] < 0  # the price paid
    assert (buyout["stake_before_bp"], buyout["stake_after_bp"]) == (7_000, 10_000)
    assert buyout["nci_cents"] == 0


def test_subsidiary_ceos_report_each_quarter_and_ask_a_question(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    tool("e2e_m16_save").formed(saves, "u", loaded)
    base = BASE.format("u")
    updates = api.get(f"{base}/group/updates")["updates"]
    assert updates
    for u in updates:
        assert u["ceo"] and u["body"] and u["question"].endswith("?")
        assert [a["mandate"] for a in u["advice"]] == ["grow", "margin", "return_cash"]
    # the advice is the mandate action: answering it sets the mandate
    u = updates[0]
    api.post(
        f"{base}/group/mandate",
        json={
            "company_id": u["company_id"],
            "mandate": "margin",
            "capex_limit_cents": u["capex_limit_cents"],
            "categories": u["categories"],
            "regions": u["regions"],
        },
    )
    after = next(
        x for x in api.get(f"{base}/group/updates")["updates"] if x["company_id"] == u["company_id"]
    )
    assert after["mandate"] == "margin"
    assert next(a for a in after["advice"] if a["mandate"] == "margin")["current"]


# --- Chips, wafers and foundries (sub-task 5) -----------------------------------------------


def test_a_chip_cost_splits_wafer_material_and_foundry_processing(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    tool("e2e_m20_save").wafers(saves, "w", loaded)
    base = BASE.format("w")
    api.post(f"{base}/advance")  # a month of the phone using its own SoC
    chip = next(c for c in api.get(f"{base}/hardware")["chips"] if c["name"] == "Forge SoC")
    parts = chip["material_cents"] + chip["processing_cents"] + chip["packaging_cents"]
    assert abs(parts - chip["unit_cost_cents"]) <= 2  # rounding of three parts
    assert chip["material_cents"] > 0 and chip["processing_cents"] > 0
    assert chip["processing_cents"] > chip["material_cents"]  # the foundry is most of a wafer
    assert chip["used_in"] == ["Forge Phone"]
    assert chip["internal_units"] > 0
    supply = api.get(f"{base}/refineries")["supply"]
    assert supply and all(s["unit"] for s in supply)


# --- Commodities planning (sub-task 6) ------------------------------------------------------


def test_the_planning_view_shows_need_drivers_and_cover(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    tool("e2e_m20_save").wafers(saves, "p", loaded)
    base = BASE.format("p")
    api.post(f"{base}/advance")
    plan = api.get(f"{base}/commodities/plan")
    assert plan["months"] == 12 and plan["plans"]
    top = plan["plans"][0]
    assert top["need_12m"] == pytest.approx(12 * top["need_month"])
    assert {d["name"] for d in top["drivers"]} <= {"Forge Phone", "Forge SoC"}
    assert sum(d["share"] for d in top["drivers"]) == pytest.approx(1.0)
    assert len(top["months"]) == 12
    before = top["deals_12m"]
    # a 6-month contract covers six of the twelve months
    good, volume = top["good"], top["need_12m"]
    api.post(
        f"{base}/commodities/contracts", json={"good": good, "months": 6, "volume_year": volume}
    )
    after = next(p for p in api.get(f"{base}/commodities/plan")["plans"] if p["good"] == good)
    assert after["deals_12m"] > before
    covered = [m for m in after["months"] if m["deals"] > 0]
    assert 0 < len(covered) < 12  # it ends inside the year
    assert after["deals_ending"]
    assert after["cover"] is not None and 0 < after["cover"] <= 1


# --- Explain on v3's numbers (sub-task 7) ----------------------------------------------------


def test_explain_a_projects_npv_and_a_mines_cost(
    api: Client, saves: Path, loaded: LoadedData
) -> None:
    tool("e2e_m19_save").building(saves, "e", loaded)
    base = BASE.format("e")
    api.post(f"{base}/advance")
    api.post(f"{base}/advance")
    mine = api.get(f"{base}/mines")["mines"][0]
    cost = api.get(f"{base}/explain/mine_cost?entity={mine['id']}")
    assert cost["subject"] == mine["name"] and cost["value"] is not None
    assert cost["value"] == pytest.approx(mine["cost_usd_t"] * 100)
    assert [i["label"] for i in cost["items"]][:3] == [
        "All-in sustaining cost a tonne",
        "Price a tonne (spot)",
        "Margin a tonne",
    ]
    assert cost["explanation"]
    x = api.get(f"{base}/exploration")
    studied = next(p for p in x["projects"] if p["npv_mid_cents"] is not None)
    npv = api.get(f"{base}/explain/mine_npv?entity={studied['id']}")
    assert npv["value"] == studied["npv_mid_cents"]
    assert npv["items"][0]["amount"] == studied["npv_low_cents"]
    api.get(f"{base}/explain/mine_cost?entity=999999", status=400)


def test_explain_a_fabs_cost_per_good_die(api: Client, saves: Path, loaded: LoadedData) -> None:
    tool("e2e_m21_save").mature(saves, "f", loaded)
    base = BASE.format("f")
    api.post(f"{base}/advance")  # its first production month
    fab = api.get(f"{base}/fabs")["fabs"][0]
    out = api.get(f"{base}/explain/fab_die_cost?entity={fab['id']}")
    assert out["items"][-1]["label"] == "Cost a start"
    assert out["items"][-1]["amount"] == pytest.approx(fab["month"]["cost_per_start_cents"])
    assert out["value"] == pytest.approx(fab["month"]["die_cost_cents"])


def test_explain_a_refinerys_cost_a_unit(api: Client, saves: Path, loaded: LoadedData) -> None:
    tool("e2e_m20_save").wafers(saves, "r", loaded)  # its wafer plant is past its ramp
    base = BASE.format("r")
    api.post(f"{base}/advance")
    plant = next(p for p in api.get(f"{base}/refineries")["plants"] if p["month"])
    out = api.get(f"{base}/explain/refinery_cost?entity={plant['id']}")
    assert out["value"] == pytest.approx(plant["month"]["unit_cost_cents"])
    assert len(out["items"]) == 6
