"""M39's API and hidden-value tests (docs/formulas.md 53.5; CLAUDE.md section 8). A stage-4 save in
2027 with a vehicle plant, L4 capability and a robotaxi service: the Robotics and Mobility routes
and their actions answer; a zone's decision month, the installations' drawn growth, the home
humanoid window and incident or approval draws are never served, and the event and LLM code never
read them."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.helpers import answer_events
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.facilities.models import Facility
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.products.models import Product
from tst.sim.research.models import ResearchLead
from tst.sim.state import with_company, with_facility, with_product, with_research_lead

JAN_2027 = 204


def _product(new, category: str, name: str, quality: float):  # type: ignore[no-untyped-def]
    pid, ids = new.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=new.player.id,
        category=category,
        name=name,
        status="live",
        quality=quality,
        feature_points=500.0,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=new.turn,
        launched_turn=new.turn,
    )
    return replace(with_product(new, p), next_ids=ids), pid


def _save(tmp_path: Path, loaded: LoadedData) -> tuple[Path, int, int]:
    path = create_save(
        "robots", 6, "funded_spinout", company_name="Robo Co", data=loaded, save_dir=tmp_path
    )
    b = loaded.balance
    with open_session(path) as session:
        old = load_state(session)
        new = replace(old, turn=JAN_2027 - 1)
        new = with_company(new, replace(new.player, stage=4))
        new, _ = _product(new, "ai_models", "Mind", 90.0)
        new, ride = _product(new, "mobility", "Ride", 60.0)
        new = with_research_lead(new, ResearchLead(new.player.id, b.vehicles.domain, 60.0))
        fid, ids = new.next_ids.take("facility")
        plant = Facility(
            id=fid,
            company_id=new.player.id,
            kind="vehicle_plant",
            region="north_america",
            capacity=2000,
            on_time=2000,
            ordered_turn=0,
            ready_turn=0,
            late_turn=0,
            capex_cents=2000 * 6_000_000,
            input_index=1.0,
            capex_paid_cents=2000 * 6_000_000,
            status="live",
        )
        new = replace(with_facility(new, plant), next_ids=ids)
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
        session.execute(text("UPDATE save_meta SET current_turn = :t"), {"t": JAN_2027 - 1})
        session.commit()
    return path, ride, fid


def test_robotics_routes_actions_and_hidden_values(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path, ride, fid = _save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        api.post(f"{base}/advance")
        body = api.get(f"{base}/robotics")
        assert {r["region"] for r in body["regions"]} == set(loaded.game_data.region_keys)
        assert {m["company"] for m in body["makers"]} >= {"FANUC", "KUKA", "Tesla Optimus"}
        (plant,) = body["plants"]
        assert plant["robots"] == 0 and plant["max_robots"] > 0
        api.post(f"{base}/robotics/plants/{fid}/robots", {"robots": 10**6}, 400)
        out = api.post(f"{base}/robotics/plants/{fid}/robots", {"robots": 100})
        after = out["robotics"]["plants"][0]
        assert after["robots"] == 100
        assert after["cost_with"]["total_cents"] < after["cost_without"]["total_cents"]
        mob = api.get(f"{base}/mobility")
        assert mob["options"]["can_drive_l4"]
        phoenix = next(x for x in mob["cities"] if x["key"] == "phoenix")
        assert phoenix["l4_approved"]
        api.post(
            f"{base}/mobility/zones", {"product_id": ride, "city": "phoenix", "size": "huge"}, 400
        )
        out = api.post(
            f"{base}/mobility/zones", {"product_id": ride, "city": "phoenix", "size": "small"}
        )
        (zone,) = out["mobility"]["zones"]
        assert zone["status"] == "applied"
        api.post(f"{base}/mobility/zones/{zone['zone_id']}/cars", {"cars": 20})
        api.post(f"{base}/mobility/depots", {"city": "phoenix", "capacity": 50})
        api.post(f"{base}/mobility/zones/{zone['zone_id']}/price", {"price_cents": 900})
        answer_events(path, loaded)
        api.post(f"{base}/advance")
        robotics = api.get(f"{base}/robotics")
        mobility = api.get(f"{base}/mobility")
        explain = api.get(f"{base}/explain/automation_saving?entity={fid}")
        ride_x = api.get(f"{base}/explain/ride_contribution?entity={zone['zone_id']}")
        text_out = json.dumps([robotics, mobility, explain, ride_x])
        with open_session(path) as session:
            state = load_state(session)
    z = state.zone(zone["zone_id"])
    assert z is not None and z.decision_turn is not None
    for word in (
        "decision",
        "draw",
        "chance",
        "probability",
        "logit",
        "incident_rate",
        "home_turn",
    ):
        assert word not in text_out
    assert state.robotics_world.growth
    for _, _, g in state.robotics_world.growth:
        assert f"{g}" not in text_out
    from tst.api.schemas import robotics as schemas

    names: set[str] = set()
    for cls in vars(schemas).values():
        if isinstance(cls, type) and hasattr(cls, "model_fields"):
            names |= set(cls.model_fields)
    hidden = {
        "decision_turn",
        "growth",
        "home_turn",
        "adoption_logit",
        "incident_rate",
        "approval_chance",
        "refusal_share",
        "serious_share",
        "event_turn",
    }
    assert not names & hidden


def test_prompts_never_read_robotics_draws() -> None:
    """The event and LLM code (ADR-0005) never read the robotics world, a zone's decision month,
    incident rates or the robotics stream."""
    root = Path(__file__).resolve().parents[2] / "tst"
    for package in ("events", "llm"):
        for source in (root / package).rglob("*.py"):
            code = source.read_text(encoding="utf-8")
            for name in ("robotics_world", "robotics.draws", "decision_turn", "incident_rate",
                         "home_turn", "robotics.robotaxi"):  # fmt: skip
                assert name not in code, (source, name)
