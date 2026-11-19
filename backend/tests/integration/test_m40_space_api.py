"""M40's API and hidden-value tests (docs/formulas.md 56.5; CLAUDE.md section 8). A stage-4 save in
2026 with a launch line, a launch site, a satellite plant and a broadband line: the Space routes and
their actions answer; no launch-failure draw, licence decision month, seeded debris rule or rivals'
drawn growth is served, and the event and LLM code never read them."""

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
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import GameState, with_company, with_facility, with_product, with_segments

JAN_2026 = ym_to_turn(2026, 1)


def _product(
    new: GameState, category: str, name: str, prices: dict[str, int]
) -> tuple[GameState, int]:
    pid, ids = new.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=new.player.id,
        category=category,
        name=name,
        status="live",
        quality=60.0,
        feature_points=500.0,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=new.turn,
        launched_turn=new.turn,
    )
    new = replace(with_product(new, p), next_ids=ids)
    rows = [ProductSegment(pid, seg, price, 0.0) for seg, price in prices.items()]
    return with_segments(new, rows, []), pid


def _facility(new: GameState, kind: str, capacity: int) -> GameState:
    fid, ids = new.next_ids.take("facility")
    f = Facility(
        id=fid,
        company_id=new.player.id,
        kind=kind,
        region="north_america",
        capacity=capacity,
        on_time=capacity,
        ordered_turn=0,
        ready_turn=0,
        late_turn=0,
        capex_cents=0,
        input_index=1.0,
        capex_paid_cents=0,
        status="live",
    )
    return replace(with_facility(new, f), next_ids=ids)


def _save(tmp_path: Path, loaded: LoadedData) -> tuple[Path, int, int]:
    path = create_save(
        "orbit", 6, "funded_spinout", company_name="Orbit Co", data=loaded, save_dir=tmp_path
    )
    b = loaded.balance
    with open_session(path) as session:
        old = load_state(session)
        new = replace(old, turn=JAN_2026 - 1)
        new = with_company(new, replace(new.player, stage=4))
        new, lift = _product(
            new,
            b.space.launch,
            "Lift",
            {"satellite_operators": 5_000_000_000, "government": 8_000_000_000},
        )
        new, net = _product(new, b.space.broadband, "Net", {"consumer": 9_000})
        new = _facility(new, b.space.site_kind, 2)
        new = _facility(new, b.space.plant_kind, 25)
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
    return path, lift, net


def test_space_routes_actions_and_hidden_values(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path, lift, net = _save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        api.post(f"{base}/advance")
        body = api.get(f"{base}/space")
        assert body["open"]
        assert {r["company"] for r in body["rivals"]} >= {"SpaceX", "Eutelsat OneWeb"}
        assert any(k["vehicle"] == "Falcon 9 Full Thrust" for k in body["cost_per_kg"])
        assert [u["product_id"] for u in body["undesigned"]] == [lift]
        api.post(f"{base}/space/vehicles/{lift}/spec", {"payload_kg": 5.0, "reuse": "full"}, 400)
        out = api.post(f"{base}/space/vehicles/{lift}/spec", {"payload_kg": 20000, "reuse": "full"})
        (v,) = out["space"]["vehicles"]
        assert v["level"] == "expendable" and v["cost"]["cost_per_kg_cents"] > 0
        api.post(
            f"{base}/space/constellations",
            {
                "name": "Ring",
                "kind": "broadband",
                "product_id": lift,
                "shells": 2,
                "mass_kg": 300,
                "life_months": 60,
                "build_per_month": 25,
                "launches_per_month": 1,
            },
            400,
        )
        out = api.post(
            f"{base}/space/constellations",
            {
                "name": "Ring",
                "kind": "broadband",
                "product_id": net,
                "shells": 2,
                "mass_kg": 300,
                "life_months": 60,
                "build_per_month": 25,
                "launches_per_month": 1,
                "vehicle_product_id": lift,
            },
        )
        (con,) = out["space"]["constellations"]
        api.post(f"{base}/space/licences", {"region": "north_america"})
        api.post(f"{base}/space/licences", {"region": "atlantis"}, 400)
        api.post(f"{base}/space/broadband/{net}/terminal", {"price_cents": 49_900})
        api.post(f"{base}/space/broadband/{net}/d2d", {"partner": True})
        for _ in range(3):
            answer_events(path, loaded)
            api.post(f"{base}/advance")
        space = api.get(f"{base}/space")
        launch_x = api.get(f"{base}/explain/launch_price?entity={lift}")
        payback_x = api.get(f"{base}/explain/constellation_payback?entity={con['id']}")
        text_out = json.dumps([space, launch_x, payback_x])
        with open_session(path) as session:
            state = load_state(session)
    assert space["launches"], "the constellation's launches flew"
    lic = state.space.licence(state.player.id, "north_america")
    assert lic is not None and lic.status == "applied" and lic.decision_turn is not None
    assert space["licences"][0]["status"] == "applied"
    assert state.space.world.debris_turn is not None and state.space.world.growth
    for word in ("decision", "draw", "debris_turn", "growth", "probability"):
        assert word not in text_out
    assert space["debris_rule"] is None  # not before it comes
    for _, g in state.space.world.growth:
        assert f"{g}" not in text_out
    from tst.api.schemas import space as schemas

    names: set[str] = set()
    for cls in vars(schemas).values():
        if isinstance(cls, type) and hasattr(cls, "model_fields"):
            names |= set(cls.model_fields)
    hidden = {"decision_turn", "growth", "debris_turn", "event_turn", "reuse_started", "pending"}
    assert not names & hidden


def test_prompts_never_read_space_draws() -> None:
    """The event and LLM code (ADR-0005) never read the space world, a licence's decision month,
    the debris rule or the space stream."""
    root = Path(__file__).resolve().parents[2] / "tst"
    for package in ("events", "llm"):
        for source in (root / package).rglob("*.py"):
            code = source.read_text(encoding="utf-8")
            for name in ("space.world", "space.draws", "debris_turn", "failure_rate",
                         "decision_turn", "tst.sim.space.policy"):  # fmt: skip
                assert name not in code, (source, name)
