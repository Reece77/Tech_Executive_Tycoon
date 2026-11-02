"""M12a API and CLI (docs/formulas.md 22.6): the Infrastructure screen, the Build preview, a
build that goes live and serves your products, a contract, Cloud hosting, a sale; component
indexes shown up to the current month and never a future one. The Client checks every
response for hidden fields."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tests.helpers import fund_save, play_turn, with_product
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.cli import app as cli_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, load_state, open_session
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities import goods
from tst.sim.rng import RngFactory

SAVE = "infra"
BASE = f"/api/saves/{SAVE}"


@pytest.fixture
def setup(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path, Path]]:
    save_dir = tmp_path / "saves"
    path = create_save(
        SAVE, 5, "funded_spinout", company_name="Infra Co", data=loaded, save_dir=save_dir
    )
    fund_save(path, 20_000_000_00)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, with_product(before, customers={"smb": 50_000.0}))
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path, save_dir


def test_build_serve_sell_capacity_and_sell(
    setup: tuple[Client, Path, Path], loaded: LoadedData
) -> None:
    api, path, _ = setup
    out = api.get(f"{BASE}/infrastructure")
    assert out["facilities"] == [] and not out["cloud"]["can_start"]
    assert [c["good"] for c in out["components"]] == ["server", "gpu"]
    assert out["components"][0]["index"] == 1.0 and out["components"][0]["allocation"] == 1.0
    assert {s["good"]: s["cents_per_unit"] for s in out["spot"]}["compute_general"] == 100_000
    assert out["break_even_utilization"] == pytest.approx(0.65)
    preview = api.get(
        f"{BASE}/infrastructure/build-preview"
        "?kind=data_centre_general&region=north_america&units=100"
    )
    assert preview["capex_cents"] == 240_000_000 and preview["staff_needed"] == 1
    assert preview["cost_per_unit_full_cents"] == 65_000 and preview["can_afford"]
    api.post(f"{BASE}/infrastructure/contracts", {"good": "server", "months": 24, "volume": 100})
    built = api.post(
        f"{BASE}/infrastructure/facilities",
        {
            "kind": "data_centre_general",
            "region": "north_america",
            "units": 100,
            "contract_id": 1,
        },
    )
    (f,) = built["infrastructure"]["facilities"]
    assert f["status"] == "building" and f["ready"] == "Jan 2011"
    assert built["infrastructure"]["contracts"][0]["used"] == 100
    sold = api.post(f"{BASE}/infrastructure/cloud", {})
    assert sold["infrastructure"]["cloud"]["selling"]
    with open_session(path) as session:
        state = load_state(session)
    with open_session(path) as session:  # jump the build to its last month
        f0 = state.facilities[0]
        moved = replace(
            state,
            facilities=(
                replace(
                    f0,
                    ordered_turn=-11,
                    ready_turn=1,
                    late_turn=1,
                    capex_paid_cents=f0.capex_cents * 11 // 12,
                ),
            ),
        )
        sync_state(session, state, moved)
        session.commit()
    play_turn(path, loaded)
    out = api.get(f"{BASE}/infrastructure")
    (f,) = out["facilities"]
    assert f["status"] == "live" and f["own_use"] > 0
    assert f["utilization"] > 0 and f["cost_per_used_cents"] is not None
    assert f["reliability"] == 0 and f["staff"] == 0  # nobody staffs it yet
    api.post(f"{BASE}/infrastructure/facilities/{f['facility_id']}/sell", {})
    assert api.get(f"{BASE}/infrastructure")["facilities"] == []


def test_cli_facilities_build_and_contract(
    setup: tuple[Client, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, save_dir = setup
    monkeypatch.setenv("TST_SAVE_DIR", str(save_dir))
    get_settings.cache_clear()
    runner = CliRunner()

    def run(*args: str) -> str:
        result = runner.invoke(cli_app, list(args))
        assert result.exit_code == 0, result.output
        return result.output

    assert "No data centres" in run("facilities", "--save", SAVE)
    assert "Contract 1" in run(
        "contract", "--save", SAVE, "--index", "gpu", "--months", "12", "--cu", "100"
    )
    out = run(
        "build-dc",
        "--save",
        SAVE,
        "--region",
        "north_america",
        "--kind",
        "gpu",
        "--cu",
        "100",
        "--contract",
        "1",
    )
    assert "Ordered data centre 1: 100 CU" in out
    listing = run("facilities", "--save", SAVE)
    assert "GPU data centre #1" in listing and "building" in listing
    get_settings.cache_clear()


def _jump_past_history(path: Path, loaded: LoadedData, to_turn: int) -> list:
    """Write the save as if played to `to_turn`, with every goods month before it."""
    rng = RngFactory(5)
    with open_session(path) as session:
        old = load_state(session)
        new = old
        months = []
        for turn in range(to_turn):
            nxt = goods.supply_phase(replace(new, turn=turn), rng, loaded.balance, loaded.game_data)
            nxt = replace(nxt, turn=old.turn)
            sync_state(session, new, nxt)
            new = nxt
            months.append(nxt.supply)
        read_meta(session).current_turn = to_turn
        session.commit()
    return months


def test_no_future_index_after_2025(setup: tuple[Client, Path, Path], loaded: LoadedData) -> None:
    """The API shows indexes up to the month just played, never the next (22.6)."""
    api, path, _ = setup
    now = ym_to_turn(2027, 6)
    months = _jump_past_history(path, loaded, now)
    out = api.get(f"{BASE}/infrastructure")
    server = out["components"][0]
    assert max(p["turn"] for p in server["history"]) == now - 1
    assert server["index"] == pytest.approx(months[-1][0].index)
    state = replace(load_state_at(path), turn=now)
    ahead = goods.supply_phase(state, RngFactory(5), loaded.balance, loaded.game_data)
    text = json.dumps(out)
    for g in ahead.supply:
        assert g.turn == now
        assert str(round(g.index, 6))[:8] not in text


def load_state_at(path: Path):  # type: ignore[no-untyped-def]
    with open_session(path) as session:
        return load_state(session)
