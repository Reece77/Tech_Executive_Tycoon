"""M18 API (formulas.md 34.5): the Exploration screen and its actions; the differential test
(two blocks with the same revealed results but different truths give identical responses);
and the hidden-value test extended to deposits (ADR-0007)."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api import find_forbidden_keys
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.api.exploration_views import exploration_out, project_out
from tst.config import Settings, get_settings
from tst.db.repository import load_state, open_session
from tst.db.state_io import sync_state
from tst.loader import LoadedData
from tst.sim.exploration import pipeline as xp

TOOLS = Path(__file__).resolve().parents[3] / "tools"
BASE = "/api/saves/{}"


def _tools() -> Any:
    sys.path.insert(0, str(TOOLS))
    import e2e_m18_save

    return e2e_m18_save


@pytest.fixture
def saves(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def api(saves: Path) -> Iterator[Client]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as client:
        yield Client(client)


def test_screen_and_the_first_stages(api: Client, saves: Path, loaded: LoadedData) -> None:
    _tools().explorer(saves, "x", loaded)
    base = BASE.format("x")
    screen = api.get(f"{base}/exploration")
    assert find_forbidden_keys(screen) == []
    assert [e["geologists"] for e in screen["explorers"]] == [3]
    assert screen["explorers"][0]["gate"] == []
    n = loaded.balance.geology.blocks_per_region * len(loaded.game_data.region_keys)
    assert len(screen["blocks"]) == n
    assert any(b["holder"] for b in screen["blocks"])  # suppliers' licences are visible
    out = api.post(
        f"{base}/exploration/desk-study", json={"region": "latin_america", "commodity": "copper"}
    )
    assert out["exploration"]["desk_studies"][0]["done"] is False
    for _ in range(loaded.balance.exploration.desk.months):
        api.post(f"{base}/advance")
    screen = api.get(f"{base}/exploration")
    banded = [b for b in screen["blocks"] if b["region"] == "latin_america"]
    assert all("copper" in b["bands"] for b in banded)
    free = next(b for b in banded if b["bands"]["copper"] == "high" and b["holder"] is None)
    out = api.post(
        f"{base}/exploration/licence", json={"region": "latin_america", "block": free["index"]}
    )
    project = out["exploration"]["projects"][0]
    assert project["status"] == "active" and project["holes"] == []
    api.post(
        f"{base}/exploration/licence",
        json={"region": "latin_america", "block": free["index"]},
        status=400,
    )
    out = api.post(f"{base}/exploration/projects/{project['id']}/stage", json={"stage": "survey"})
    assert out["exploration"]["projects"][0]["stage"] == "survey"
    assert find_forbidden_keys(out) == []


def test_drilling_narrows_the_range(api: Client, saves: Path, loaded: LoadedData) -> None:
    _tools().sampled(saves, "d", loaded)
    base = BASE.format("d")
    project = api.get(f"{base}/exploration")["projects"][0]
    assert project["sample_grade"] is not None and project["grade"] is None
    api.post(f"{base}/exploration/projects/{project['id']}/drill", json={"holes": 20})
    widths = []
    for _ in range(5):
        api.post(f"{base}/advance")
        p = api.get(f"{base}/exploration")["projects"][0]
        widths.append(p["grade"]["pct"])
    assert len(p["holes"]) == 20 and p["holes_left"] == 0
    assert widths == sorted(widths, reverse=True) and widths[-1] < widths[0]


def test_sell_a_permitted_project(api: Client, saves: Path, loaded: LoadedData) -> None:
    _tools().permitted(saves, "s", loaded)
    base = BASE.format("s")
    project = api.get(f"{base}/exploration")["projects"][0]
    assert project["status"] == "permitted" and project["level"] == "definitive"
    if project["sale_quote_cents"] <= 0:
        pytest.skip("this deposit's NPV is below zero at the deck: nobody buys it")
    out = api.post(f"{base}/exploration/projects/{project['id']}/sell")
    sold = out["exploration"]["projects"][0]
    assert sold["status"] == "sold" and sold["sold_to"] == project["buyer"]
    assert sold["sale_cents"] == project["sale_quote_cents"]


def test_protest_is_a_critical_event(api: Client, saves: Path, loaded: LoadedData) -> None:
    _tools().protest(saves, "p", loaded)
    base = BASE.format("p")
    project = api.get(f"{base}/exploration")["projects"][0]
    assert project["protest_open"]
    events = api.get(f"{base}/events")
    open_ = [e for e in events["open"] if e["template_id"] == "community_blockade"]
    assert events["blocking_event_id"] == open_[0]["event_id"]
    assert open_ and open_[0]["severity"] == "critical"
    assert [c["key"] for c in open_[0]["choices"]] == ["A", "B", "C"]
    api.post(f"{base}/advance", status=409)  # a critical event blocks Continue


def test_differential_same_revealed_different_truth(saves: Path, loaded: LoadedData) -> None:
    """34.5: two projects whose revealed results are the same, on blocks whose truths differ
    (one holds a rich deposit, one nothing), give identical responses."""
    path = _tools().permitted(saves, "diff", loaded)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = before
        p = state.projects[0]
        blocks = [b for b in state.geo_blocks if b.region == p.region]
        rich = next(b for b in blocks if b.index == p.block)
        empty = next(
            b
            for b in blocks
            if b.true_commodity is None and xp.holder_of(state, b.region, b.index) is None
        )
        twin = replace(p, id=p.id + 1, block=empty.index)
        state = replace(state, projects=(*state.projects, twin))
        twin_holes = tuple(replace(h, project_id=twin.id) for h in xp.holes_of(state, p.id))
        state = replace(state, holes=(*state.holes, *twin_holes))
        # change every truth of both blocks: the responses must not move
        swapped = tuple(
            replace(
                b,
                true_grade=b.true_grade * 3 + 0.01,
                true_tonnage_mt=b.true_tonnage_mt + 50,
                true_recovery=0.99,
                true_sensitivity=1.0 - b.true_sensitivity,
                true_difficulty=b.true_difficulty * 2,
                depth_m=b.depth_m + 100,
                true_infra_km=b.true_infra_km + 10,
            )
            if b in (rich, empty)
            else b
            for b in state.geo_blocks
        )
        sync_state(session, before, state)
    one = project_out(state, state.projects[0], loaded).model_dump()
    two = project_out(state, state.projects[1], loaded).model_dump()
    for key in ("id", "block", "label"):
        one.pop(key), two.pop(key)
    assert one == two
    moved = replace(state, geo_blocks=swapped)
    again = project_out(moved, moved.projects[0], loaded).model_dump()
    again.pop("id"), again.pop("block"), again.pop("label")
    assert again == one
    whole = exploration_out(state, {}, loaded).model_dump()
    assert exploration_out(moved, {}, loaded).model_dump() == whole


def test_no_deposit_truth_in_a_prompt(saves: Path, loaded: LoadedData) -> None:
    """ADR-0005, 34.5: a protest's prompt carries no deposit truth (unmistakable planted
    values in the block's true_* fields never appear)."""
    from tst.events.context import Kpis, build_prompt
    from tst.sim.events.director import eligible_targets

    path = _tools().protest(saves, "prompt", loaded)
    with open_session(path) as session:
        state = load_state(session)
    p = state.projects[0]
    planted = tuple(
        replace(
            b,
            true_grade=0.0123456789,
            true_tonnage_mt=98.7654321,
            true_recovery=0.8765432,
            true_sensitivity=0.7654321,
            true_difficulty=1.2345678,
            depth_m=345.678912,
        )
        if (b.region, b.index) == (p.region, p.block)
        else b
        for b in state.geo_blocks
    )
    state = replace(state, geo_blocks=planted)
    events = [e for e in state.events if e.template_id in xp.EVENT_TEMPLATES]
    assert events
    texts = []
    for event in events:
        template = loaded.game_data.event_template(event.template_id)
        system, user = build_prompt(
            state,
            event,
            template,
            eligible_targets(state, event),
            Kpis(10**9, None, 0, 1, 0),
            loaded.balance,
            loaded.game_data,
        )
        texts.append(system + user)
    joined = "\n".join(texts)
    for value in ("0.0123", "98.76", "0.8765", "0.7654", "1.2345", "345.6"):
        assert value not in joined
