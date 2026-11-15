"""M32's API and hidden-value tests (docs/formulas.md 46.9; CLAUDE.md section 8; ADR-0022 5).
A save moved to January 2027 at stage 4: the Power route, siting, quotes and actions answer; a
plant's hidden overrun and true completion, outage draws and seeded future paths are never
served, and the event and LLM code never read them."""

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
from tst.sim.state import with_company

JAN_2027 = 204


def _save(tmp_path: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "power", 5, "funded_spinout", company_name="Power Co", data=loaded, save_dir=tmp_path,
    )  # fmt: skip
    with open_session(path) as session:
        old = load_state(session)
        new = replace(old, turn=JAN_2027)
        new = with_company(new, replace(new.player, stage=4))
        sync_state(session, old, new)
        session.execute(text("UPDATE save_meta SET current_turn = :t"), {"t": JAN_2027})
        session.commit()
    return path


def test_power_route_actions_and_hidden_values(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path = _save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        api.post(f"{base}/advance")  # a month: the year's paths are drawn
        body = api.get(f"{base}/power")
        assert body["unlocked"] and {t["key"] for t in body["plant_types"]} >= {"gas", "nuclear"}
        na = next(r for r in body["regions"] if r["region"] == "north_america")
        assert na["queue_lo_months"] < na["queue_hi_months"] and na["grid_usd_mwh"] > 0
        siting = api.get(f"{base}/power/siting?kind=data_centre_gpu&capacity=10000")
        assert siting["mw"] > 20 and len(siting["sites"]) == len(loaded.game_data.cities)
        quote = api.get(f"{base}/power/quote/plant?plant_type=nuclear&mw=1000&region=north_america")
        assert quote["allowed"] and quote["build_months"] == 84
        api.get(f"{base}/power/quote/plant?plant_type=fusion&mw=1000&region=north_america", 422)
        ppa = api.get(
            f"{base}/power/quote/ppa?region=north_america&producer=nextera&mwh_month=500&years=10"
        )
        assert ppa["price_usd_mwh"] < ppa["forward_usd_mwh"]
        # actions: a plant too small for a reactor is a rule error; then a reactor and a PPA
        api.post(
            f"{base}/power/plants", {"plant_type": "nuclear", "mw": 100, "region": "europe"}, 400
        )
        gas = api.get(f"{base}/power/quote/plant?plant_type=gas&mw=50&region=north_america")
        out = api.post(
            f"{base}/power/plants", {"plant_type": "gas", "mw": 50, "region": "north_america"}
        )
        plant = out["power"]["plants"][0]
        assert plant["status"] == "building" and plant["queue_lo_months"] is not None
        assert plant["estimate_cents"] == gas["capex_cents"]
        api.post(
            f"{base}/power/ppas",
            {"region": "north_america", "producer": "nextera", "mwh_month": 500, "years": 10},
        )
        body = api.get(f"{base}/power")
        page = api.get(f"{base}/power/plants/{plant['facility_id']}")
        text_out = json.dumps([body, page])
        with open_session(path) as session:
            state = load_state(session)
    p = state.plants[0]
    f = state.facility(p.facility_id)
    assert f is not None
    # the true capex and completion stay in the engine: the page shows the quote and the payments
    assert page["estimate_cents"] == p.estimate_cents and page["paid_cents"] == f.capex_paid_cents
    assert page["expected_turn"] <= max(f.ready_turn, state.turn)
    assert str(f.capex_cents) not in text_out or f.capex_cents == p.estimate_cents
    for word in ("overrun", "complete_turn", "draw", "chance", "probability", "hazard"):
        assert word not in text_out
    assert len(body["ppas"]) == 1 and body["ppas"][0]["status"] == "active"
    from tst.api.schemas import power as schemas

    names: set[str] = set()
    for cls in vars(schemas).values():
        if isinstance(cls, type) and hasattr(cls, "model_fields"):
            names |= set(cls.model_fields)
    assert not {n for n in names if "overrun" in n or "complete" in n or "chance" in n}
    # nothing beyond this year's path is stored
    years = {rp.year for rp in state.region_paths}
    assert years <= {2027}


def test_prompts_never_read_power_draws() -> None:
    """The event and LLM code (ADR-0005) never read a plant's overrun, the outage or queue draws,
    or the seeded paths."""
    root = Path(__file__).resolve().parents[2] / "tst"
    for package in ("events", "llm"):
        for source in (root / package).rglob("*.py"):
            code = source.read_text(encoding="utf-8")
            for name in ("power.plants", "power.paths", "power.queues", "power.outages",
                         "complete_turn", "draw_overrun"):  # fmt: skip
                assert name not in code, (source, name)
