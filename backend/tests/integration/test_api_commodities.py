"""M17 API and CLI (docs/formulas.md 33): the Commodities tab with history to the current
month, an offtake signed through the API with its prepayment, the device cost breakdown, power
by region; and no commodity or power month after the current one ever reaches a response (33.6
target 1, the hidden-value rule of M12r). The Client checks every response for hidden fields."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tests.helpers import fund_save, with_product
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.cli import app as cli_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, load_state, open_session
from tst.db.state_io import good_month_to_row, read_meta, sync_state
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.commodities import commodity
from tst.sim.facilities import goods
from tst.sim.hardware.models import ProductionMonth
from tst.sim.rng import RngFactory

SAVE = "comm"
BASE = f"/api/saves/{SAVE}"
PLANTED = 7.654321
PLANTED_ALLOCATION = 0.4321


@pytest.fixture
def setup(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path, Path]]:
    save_dir = tmp_path / "saves"
    path = create_save(
        SAVE, 5, "funded_spinout", company_name="Comm Co", data=loaded, save_dir=save_dir
    )
    fund_save(path, 20_000_000_00)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path, save_dir


def _move_to(path: Path, turn: int, *, device: bool = False) -> int | None:
    """Set the save's month (inside history no stored months are needed), optionally with a
    live device that sold 10,000 units last month."""
    pid = None
    with open_session(path) as session, session.begin():
        old = load_state(session)
        new = replace(old, turn=turn)
        if device:
            new = with_product(new, category="devices", prices={"consumer": 40_000}, name="Phone")
            pid = next(p.id for p in new.products if p.name == "Phone")
            new = replace(new, production=(ProductionMonth(turn - 1, pid, 1, 10_000, 10_000),))
        sync_state(session, old, new)
        read_meta(session).current_turn = turn
    return pid


def test_tab_shows_2022_lithium_spike_on_a_2023_save(
    setup: tuple[Client, Path, Path], loaded: LoadedData
) -> None:
    api, path, _ = setup
    now = ym_to_turn(2023, 6)
    _move_to(path, now)
    out = api.get(f"{BASE}/commodities")
    assert [g["good"] for g in out["goods"]][:3] == ["quartz_hp", "silicon_metal", "polysilicon"]
    li = next(g for g in out["goods"] if g["good"] == "lithium_carbonate")
    peak = max(li["history"], key=lambda p: p["price"])
    assert peak["label"] == "Nov 2022" and peak["price"] == pytest.approx(80_000)
    assert max(p["turn"] for p in li["history"]) == now
    assert li["long_run"] == 11_800
    neon = next(g for g in out["goods"] if g["good"] == "neon")
    assert min(p["allocation"] for p in neon["history"]) == pytest.approx(0.6)  # Mar-Jun 2022
    power = {p["region"]: p["index"] for p in out["power"]}
    assert power["north_america"] == 1.0
    assert power["south_southeast_asia"] < power["north_america"] < power["europe"]
    assert any(s["key"] == "sqm" for s in out["suppliers"])
    molycorp = [s for s in out["suppliers"] if s["key"] == "molycorp"]
    assert molycorp == []  # gone in 2015, more than a year before


def test_offtake_through_the_api_and_the_cost_breakdown(
    setup: tuple[Client, Path, Path], loaded: LoadedData
) -> None:
    api, path, _ = setup
    pid = _move_to(path, ym_to_turn(2020, 2), device=True)
    body = {
        "good": "lithium_carbonate",
        "supplier": "sqm",
        "years": 5,
        "volume_year": 50.0,
        "prepay": 0.2,
    }
    quote = api.post(f"{BASE}/commodities/offtakes/quote", body)
    assert (quote["floor"], quote["ceiling"]) == (pytest.approx(6000), pytest.approx(10000))
    assert quote["prepaid_cents"] == round(50 * 8000 * 100 * 0.2)
    cash_before = api.get(f"/api/saves/{SAVE}/overview")["cash_cents"]
    signed = api.post(f"{BASE}/commodities/offtakes", body)
    [deal] = signed["commodities"]["deals"]
    assert deal["supplier_name"] == "SQM" and deal["status"] == "active"
    assert deal["prepaid_left_cents"] == quote["prepaid_cents"]
    cash_after = api.get(f"/api/saves/{SAVE}/overview")["cash_cents"]
    assert cash_before - cash_after == quote["prepaid_cents"]
    panel = api.get(f"/api/saves/{SAVE}/products/{pid}/manufacturing")
    lines = {x["good"]: x for x in panel["commodity_lines"]}
    assert set(lines) == set(loaded.balance.commodity.mixes["device_bom"].weights)
    assert lines["lithium_carbonate"]["hedged_share"] == pytest.approx(1.0)
    assert lines["cobalt"]["hedged_share"] == 0.0
    refused = api.client.post(f"{BASE}/commodities/offtakes", json={**body, "supplier": "lynas"})
    assert refused.status_code >= 400 and "does not sell" in refused.text


def test_cli_commodities_and_offtake(
    setup: tuple[Client, Path, Path], loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, path, save_dir = setup
    _move_to(path, ym_to_turn(2021, 3))
    monkeypatch.setenv("TST_SAVE_DIR", str(save_dir))
    runner = CliRunner()
    out = runner.invoke(cli_app, ["commodities", "--save", SAVE])
    assert out.exit_code == 0, out.output
    assert "Lithium carbonate" in out.output and "Power (x North America)" in out.output
    signed = runner.invoke(
        cli_app,
        [
            "offtake",
            "--save",
            SAVE,
            "--good",
            "copper",
            "--supplier",
            "codelco",
            "--years",
            "3",
            "--volume",
            "100",
        ],
    )
    assert signed.exit_code == 0, signed.output
    assert "Offtake 1" in signed.output


def _jump_past_history(path: Path, loaded: LoadedData, to_turn: int) -> list:  # type: ignore[type-arg]
    """Write the save as if played to `to_turn`, every good's month before it (M12a's and
    M17's)."""
    rng = RngFactory(5)
    b, d = loaded.balance, loaded.game_data
    with open_session(path) as session:
        old = load_state(session)
        new = old
        months = []
        for turn in range(to_turn):
            at = replace(new, turn=turn)
            extra = commodity.months(at, rng, b, d)
            nxt = goods.supply_phase(at, rng, b, d)
            nxt = replace(nxt, supply=nxt.supply + extra, turn=old.turn)
            sync_state(session, new, nxt)
            new = nxt
            months.append(nxt.supply)
        read_meta(session).current_turn = to_turn
        session.commit()
    return months


def _shown(text: str) -> bool:
    return any(v in text for v in ("7.654", "0.4321"))


def test_no_future_commodity_month_reaches_the_api(
    setup: tuple[Client, Path, Path], loaded: LoadedData
) -> None:
    """A planted commodity and power row for the month about to be played, and one further
    ahead, never show in the tab, the cost breakdown or a quote (33.6 target 1)."""
    api, path, _ = setup
    now = ym_to_turn(2027, 6)
    months = _jump_past_history(path, loaded, now)
    urls = (f"{BASE}/commodities", f"/api/saves/{SAVE}/infrastructure")
    before = [api.client.get(u).text for u in urls]
    with open_session(path) as session, session.begin():
        for turn in (now, now + 6):
            for g in months[-1]:
                planted = replace(g, turn=turn, index=PLANTED, allocation=PLANTED_ALLOCATION)
                session.add(good_month_to_row(planted))
    after = [api.client.get(u).text for u in urls]
    assert after == before
    assert not any(_shown(t) for t in after)
    out = json.loads(after[0])
    li = next(g for g in out["goods"] if g["good"] == "lithium_carbonate")
    assert max(p["turn"] for p in li["history"]) == now - 1
    last = next(g for g in months[-1] if g.good == "lithium_carbonate")
    assert li["index"] == pytest.approx(last.index)
    quote = api.post(
        f"{BASE}/commodities/offtakes/quote",
        {"good": "lithium_carbonate", "supplier": "sqm", "years": 3, "volume_year": 10.0},
    )
    assert not _shown(json.dumps(quote))
    mean = loaded.game_data.commodity_history.good("lithium_carbonate").mean_2010_2019  # type: ignore[union-attr]
    assert quote["price"] == pytest.approx(last.index * mean)
