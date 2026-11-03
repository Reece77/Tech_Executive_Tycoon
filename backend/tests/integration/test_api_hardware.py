"""M12b API, persistence and CLI (docs/formulas.md 26.5): the Hardware screen, a device on a
contract with its BOM and margin, a plant that takes over, selling spare plant capacity, a
chip with a wafer contract and the GPU capex it saves. The Client checks every response for
hidden fields."""

from __future__ import annotations

from collections.abc import Iterator
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
from tst.db.state_io import live_view, sync_state
from tst.loader import LoadedData

SAVE = "hw"
BASE = f"/api/saves/{SAVE}"


@pytest.fixture
def setup(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path, Path]]:
    save_dir = tmp_path / "saves"
    path = create_save(
        SAVE, 5, "funded_spinout", company_name="Pebble", data=loaded, save_dir=save_dir
    )
    fund_save(path, 20_000_000_00)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = with_product(
            before,
            category="devices",
            prices={"consumer": 38_000},
            quality=70.0,
            brand=50.0,
            feature_points=10_000.0,
            name="Pebble Phone",
        )
        state = with_product(
            state,
            category="chips_ai_accelerator",
            prices={"hyperscalers": 150_000},
            quality=70.0,
            brand=40.0,
            feature_points=10_000.0,
            name="Pebble TPU",
            root=False,
        )
        sync_state(session, before, state)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path, save_dir


def _pid(path: Path, name: str) -> int:
    with open_session(path) as session:
        state = load_state(session)
    return next(p.id for p in state.products if p.name == name)


def test_device_contract_plant_and_cm(setup: tuple[Client, Path, Path], loaded: LoadedData) -> None:
    api, path, _ = setup
    out = api.get(f"{BASE}/hardware")
    assert out["plants"] == [] and out["contracts"] == [] and not out["cm"]["can_start"]
    assert [c["good"] for c in out["components"]] == [
        "device_bom",
        "server_bom",
        "equipment",
        "foundry_wafer",
    ]
    phone = _pid(path, "Pebble Phone")
    panel = api.get(f"{BASE}/products/{phone}/manufacturing")
    assert [line["line"] for line in panel["lines"]] == ["Bill of materials", "Chip", "Assembly"]
    assert panel["unit_cost_cents"] == 23_300 and not panel["can_launch_source"]
    assert panel["gross_margin"] == pytest.approx((38_000 - 23_300) / 38_000)
    body = {
        "product_id": phone,
        "manufacturer": "foxconn",
        "city": "shenzhen",
        "units": 20_000,
        "months": 24,
    }
    out = api.post(f"{BASE}/hardware/contracts", body)["hardware"]
    assert out["contracts"][0]["units"] == 20_000 and out["contracts"][0]["price_cents"] == 1_300
    api.post(f"{BASE}/hardware/contracts", {**body, "months": 48}, status=400)
    play_turn(path, loaded)
    panel = api.get(f"{BASE}/products/{phone}/manufacturing")
    assert panel["units_sold"] > 0 and panel["cogs_cents"] > 0
    assert panel["sources"][0]["source"] == "contract"
    out = api.post(f"{BASE}/hardware/plants", {"city": "shenzhen", "units": 20_000})["hardware"]
    (plant,) = out["plants"]
    assert plant["status"] == "building" and plant["city"] == "shenzhen"
    assert out["cm"]["can_start"]
    out = api.post(f"{BASE}/hardware/contract-manufacturing")["hardware"]
    assert out["cm"]["started"]
    api.post(f"{BASE}/hardware/plants", {"city": "shenzhen", "units": 7}, status=400)
    with open_session(path) as session:
        state = load_state(session)
        assert live_view(state) == state


def test_chip_wafer_contract_and_gpu_capex(setup: tuple[Client, Path, Path]) -> None:
    api, path, _ = setup
    chip = _pid(path, "Pebble TPU")
    out = api.post(
        f"{BASE}/hardware/wafer-contracts",
        {"product_id": chip, "foundry": "tsmc", "wafers": 50, "months": 24},
    )["hardware"]
    (c,) = out["chips"]
    assert c["chip_type"] == "ai_accelerator" and c["wafers"] == 50
    assert c["gpu_capex_factor"] < 0.8
    after = api.get(f"{BASE}/infrastructure/build-preview?kind=data_centre_gpu&units=500")
    full = 500 * 2_000_000  # 500 CU x $20,000 at the GPU index 1.0 (January 2010)
    assert after["capex_cents"] == pytest.approx(full * c["gpu_capex_factor"], abs=2)
    panel = api.get(f"{BASE}/products/{chip}/manufacturing")
    assert [line["line"] for line in panel["lines"]] == ["Wafer", "Packaging and test"]


def test_cli_hardware(setup: tuple[Client, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _, path, save_dir = setup
    monkeypatch.setenv("TST_SAVE_DIR", str(save_dir))
    get_settings.cache_clear()
    runner = CliRunner()

    def run(*args: str) -> str:
        result = runner.invoke(cli_app, list(args))
        assert result.exit_code == 0, result.output
        return result.output

    phone, chip = _pid(path, "Pebble Phone"), _pid(path, "Pebble TPU")
    out = run(
        "cm-contract", "--save", SAVE, "--product", str(phone), "--units", "5000", "--months", "12"
    )
    assert "5,000 units a month at $13.00" in out
    assert "Ordered assembly plant" in run(
        "build-plant", "--save", SAVE, "--city", "shenzhen", "--units", "5000"
    )
    assert "Wafer contract" in run(
        "wafer-contract", "--save", SAVE, "--product", str(chip), "--wafers", "10", "--months", "12"
    )
    out = run("hardware", "--save", SAVE)
    assert "Pebble Phone" in out and "Assembly plant" in out and "Pebble TPU" in out


def test_a_software_product_has_an_empty_panel(setup: tuple[Client, Path, Path]) -> None:
    """Every GET route answers for any of the player's products (the ten-year crawl)."""
    api, path, _ = setup
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, with_product(before, name="Pipeline", root=False))
    panel = api.get(f"{BASE}/products/{_pid(path, 'Pipeline')}/manufacturing")
    assert not panel["sells_units"] and panel["lines"] == [] and panel["sources"] == []
