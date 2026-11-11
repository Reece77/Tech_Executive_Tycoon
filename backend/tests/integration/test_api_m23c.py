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
