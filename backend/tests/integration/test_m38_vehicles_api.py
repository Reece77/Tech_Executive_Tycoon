"""M38's API and hidden-value tests (docs/formulas.md 49.7; CLAUDE.md section 8). A stage-4 save in
2027 with a car line: the Vehicles route, a car's page and the actions answer; a cell plant's
overrun, a region's drawn S-curve speed, the learning rate and incident draws are never served,
and the event and LLM code never read them."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import with_company, with_product, with_product_segment

JAN_2026 = 192


def _save(tmp_path: Path, loaded: LoadedData) -> tuple[Path, int]:
    path = create_save(
        "cars", 5, "funded_spinout", company_name="Car Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session:
        old = load_state(session)
        new = replace(old, turn=JAN_2026 - 1)
        new = with_company(new, replace(new.player, stage=4))
        pid, ids = new.next_ids.take("product")
        car = Product(
            id=pid,
            company_id=new.player.id,
            category="vehicles",
            name="Volta One",
            status="live",
            quality=60.0,
            feature_points=500.0,
            brand=40.0,
            marketing_budget_cents=0,
            created_turn=new.turn,
            launched_turn=new.turn,
        )
        new = replace(with_product(new, car), next_ids=ids)
        new = with_product_segment(new, ProductSegment(pid, "consumer", 3_100_000, 100.0))
        sync_state(session, old, new)
        cash = LedgerEntry.transfer(
            turn=new.turn - 1,
            company_id=new.player.id,
            memo="Test funding",
            debit=CASH,
            credit=COMMON_EQUITY,
            amount=10_000_000_000_00,
        )
        session.add(entry_to_row(cash))
        session.execute(text("UPDATE save_meta SET current_turn = :t"), {"t": JAN_2026 - 1})
        session.commit()
    return path, pid


def test_vehicles_route_actions_and_hidden_values(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path, pid = _save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        api.post(f"{base}/advance")  # December 2025: the world's paths are drawn
        api.post(f"{base}/advance")  # January 2026
        body = api.get(f"{base}/vehicles")
        assert not body["in_history"]
        regions = {r["region"]: r for r in body["regions"]}
        assert set(regions) == set(loaded.game_data.region_keys)
        assert regions["east_asia"]["ev_share"] > regions["africa"]["ev_share"]
        assert {r["company"] for r in body["rivals"]} >= {"Tesla", "BYD"}
        assert body["battery"]["cell_cents"] > 0
        car = api.get(f"{base}/vehicles/cars/{pid}")
        assert car["name"] == "Volta One" and car["unit_cost_cents"] > 0
        assert next(x["line"] for x in car["unit_cost"]) == "Battery pack"
        # actions: a bad design is a rule error; then a design, a cell plant and a network
        bad = {
            "pack_kwh": 500,
            "chemistry": "lfp",
            "charge_kw": 150,
            "autonomy": "l2",
            "platform": "licensed",
            "cells": "catl",
        }
        api.post(f"{base}/vehicles/cars/{pid}/spec", bad, 400)
        out = api.post(f"{base}/vehicles/cars/{pid}/spec", {**bad, "pack_kwh": 75})
        assert out["vehicles"]["cars"][0]["spec"]["pack_kwh"] == 75
        out = api.post(
            f"{base}/vehicles/cell-plants",
            {"region": "north_america", "mwh_month": 250, "chemistry": "lfp"},
        )
        plant = out["vehicles"]["cell_plants"][0]
        assert plant["status"] == "building" and plant["estimate_cents"] > 0
        api.post(
            f"{base}/vehicles/charging",
            {"region": "europe", "chargers": 50, "exclusive": True},
        )
        body = api.get(f"{base}/vehicles")
        assert body["charging"][0]["exclusive"] is True
        page = api.get(f"{base}/vehicles/cars/{pid}")
        explain = api.get(f"{base}/explain/car_unit_cost?entity={pid}")
        battery = api.get(f"{base}/explain/battery_price")
        text_out = json.dumps([body, page, explain, battery])
        with open_session(path) as session:
            state = load_state(session)
    cp = state.cell_plants[0]
    f = state.facility(cp.facility_id)
    assert f is not None
    # the true capex is the quote x (1 + overrun): only the quote is served
    assert body["cell_plants"][0]["estimate_cents"] == cp.estimate_cents
    if cp.overrun > 0:
        assert str(f.capex_cents) not in text_out  # type: ignore[union-attr]
    world = state.vehicle_world
    assert world.learning_rate is not None and world.k
    for word in ("overrun", "learning_rate", "draw", "chance", "probability", "logit"):
        assert word not in text_out
    for _, k in world.k:
        assert f"{k}" not in text_out
    assert f"{world.learning_rate}" not in text_out
    from tst.api.schemas import vehicles as schemas

    names: set[str] = set()
    for cls in vars(schemas).values():
        if isinstance(cls, type) and hasattr(cls, "model_fields"):
            names |= set(cls.model_fields)
    hidden = {"overrun", "k", "learning_rate", "logit", "incident_rate", "approval_chance"}
    assert not names & hidden


def test_prompts_never_read_vehicle_draws() -> None:
    """The event and LLM code (ADR-0005) never read a cell plant's overrun, the S-curve's speeds,
    the learning rate or incident draws."""
    root = Path(__file__).resolve().parents[2] / "tst"
    for package in ("events", "llm"):
        for source in (root / package).rglob("*.py"):
            code = source.read_text(encoding="utf-8")
            for name in ("vehicle_world", "vehicles.draws", "vehicles.autonomy", "overrun",
                         "learning_rate", "cell_plants"):  # fmt: skip
                assert name not in code, (source, name)
