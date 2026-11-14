"""M31's API and hidden-value tests (docs/formulas.md 44.10; CLAUDE.md section 8; ADR-0021 6).
A save moved to January 2026 with a consumer app of the player's, a month played: the Platforms
route shows public facts (rivals' developer shares as ranges), the actions answer with rule
errors, and no gatekeeper's chance or draw, or rival's plan, is stored, served or prompted."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, open_session
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.platforms import data as pdata
from tst.sim.platforms import models
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import with_product, with_product_segment

JAN_2026 = 192
APP_ID = 990_001


def _save(tmp_path: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "platforms", 5, "ex_big_tech_founders", company_name="Platform Co", data=loaded,
        save_dir=tmp_path,
    )  # fmt: skip
    with open_session(path) as session:
        old = load_state(session)
        new = pdata.materialise(replace(old, turn=JAN_2026), loaded.balance, loaded.game_data)
        app = Product(
            id=APP_ID, company_id=new.player.id, category="consumer_apps", name="Test App",
            status="live", quality=60.0, feature_points=200.0, brand=40.0,
            marketing_budget_cents=0, created_turn=JAN_2026 - 12, launched_turn=JAN_2026 - 6,
        )  # fmt: skip
        new = with_product_segment(
            with_product(new, app), ProductSegment(APP_ID, "consumer", 40, 1_000_000.0)
        )
        sync_state(session, old, new)
        session.execute(text("UPDATE save_meta SET current_turn = :t"), {"t": JAN_2026})
        session.commit()
    return path


def test_platforms_route_and_hidden_values(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path = _save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        api.post(f"{base}/advance")
        body = api.get(f"{base}/platforms")
        assert body["started"] and body["fees_posting"]
        keys = {p["key"] for p in body["platforms"]}
        assert {"ios", "android_play", "android_china"} <= keys
        ios = next(p for p in body["platforms"] if p["key"] == "ios")
        na = next(r for r in ios["regions"] if r["region"] == "north_america")
        assert na["developer_share"] is None  # a rival's: a range only
        lo, hi = na["developer_range"]
        assert hi - lo <= 0.05 + 1e-9
        assert na["goodwill"] is None and ios["settings"] is None
        mine = next(a for a in body["apps"] if a["product_id"] == APP_ID)
        assert mine["fees_total_cents"] > 0
        # rule errors: switching a device line that does not exist, complying with nothing
        api.post(
            f"{base}/platforms/device-platform",
            {"product_id": APP_ID, "platform_id": 0},
            status=400,
        )
        api.post(f"{base}/platforms/comply", {"product_id": APP_ID}, status=400)
        api.post(f"{base}/platforms/steering", {"product_id": APP_ID, "on": True})
        text_out = json.dumps(body)
        with open_session(path) as session:
            state = load_state(session)
    # No chance or draw is served, and none is stored on any record.
    for word in ("chance", "draw", "probability"):
        assert word not in text_out
    from tst.api.schemas import platforms as schemas

    names: set[str] = set()
    for cls in vars(schemas).values():
        if isinstance(cls, type) and hasattr(cls, "model_fields"):
            names |= set(cls.model_fields)
    # the only odds the API serves are appeals' public range (balance.yaml, shown in the event)
    assert {n for n in names if "odds" in n or "chance" in n} == {"appeal_odds"}
    assert body["appeal_odds"] == list(loaded.balance.platforms.review.appeal_odds)
    fields = {
        name
        for cls in vars(models).values()
        if isinstance(cls, type)
        for name in getattr(cls, "__dataclass_fields__", {})
    }
    assert not {"chance", "odds", "draw", "probability", "plan"} & fields
    assert state.steering_products == (APP_ID,)


def test_prompts_never_read_review_chances() -> None:
    """The event and LLM code (ADR-0005) never read a gatekeeper's chance or the rivals' plans."""
    root = Path(__file__).resolve().parents[2] / "tst"
    for package in ("events", "llm"):
        for source in (root / package).rglob("*.py"):
            code = source.read_text(encoding="utf-8")
            for name in ("gatekeep.chance", "import chance", "rivals_month", "platforms.rivals"):
                assert name not in code, (source, name)
