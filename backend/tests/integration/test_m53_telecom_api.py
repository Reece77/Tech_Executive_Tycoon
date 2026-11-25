"""M53's API and hidden-value tests (docs/formulas.md 62.5; CLAUDE.md section 8). A stage-4 save in
September 2020 with cash and a mobile line: the Telecom routes and their actions answer, the C-band
auction is announced and takes a bid, and no rival's auction value, seeded auction, seeded ban, 6G
month or drawn growth is served; the event and LLM code never read them."""

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
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import with_company, with_product, with_segments

SEP_2020 = ym_to_turn(2020, 9)


def _save(tmp_path: Path, loaded: LoadedData) -> tuple[Path, int]:
    path = create_save(
        "nova", 6, "funded_spinout", company_name="Nova Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session:
        old = load_state(session)
        new = replace(old, turn=SEP_2020)
        new = with_company(new, replace(new.player, stage=4))
        pid, ids = new.next_ids.take("product")
        p = Product(
            id=pid,
            company_id=new.player.id,
            category="mobile",
            name="Nova Mobile",
            status="live",
            quality=60.0,
            feature_points=40.0,
            brand=40.0,
            marketing_budget_cents=0,
            created_turn=new.turn,
            launched_turn=new.turn,
        )
        new = replace(with_product(new, p), next_ids=ids)
        new = with_segments(new, [ProductSegment(pid, "telecom_consumer", 4000, 0.0)], [])
        sync_state(session, old, new)
        cash = LedgerEntry.transfer(
            turn=new.turn - 1,
            company_id=new.player.id,
            memo="Test funding",
            debit=CASH,
            credit=COMMON_EQUITY,
            amount=100_000_000_000_00,
        )
        session.add(entry_to_row(cash))
        session.execute(text("UPDATE save_meta SET current_turn = :t"), {"t": SEP_2020})
        session.commit()
    return path, pid


def test_telecom_routes_actions_and_hidden_values(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path, pid = _save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        for _ in range(2):
            answer_events(path, loaded)
            api.post(f"{base}/advance")
        body = api.get(f"{base}/telecom")
        assert {g["key"] for g in body["generations"] if g["open"]} == {"g3", "g4", "g5"}
        (g6,) = [g for g in body["generations"] if g["key"] == "g6"]
        assert g6["first"] is None
        cband = next(a for a in body["auctions"] if a["label"].startswith("FCC Auction 107"))
        assert cband["status"] == "announced" and cband["biddable"]
        assert {o["name"] for o in body["operators"]} >= {"Verizon", "China Mobile", "Reliance Jio"}
        towers = f"{base}/telecom/towers"
        na = {"region": "north_america"}
        api.post(towers, {**na, "sites": 333, "generation": "g4", "vendor": "ericsson"}, 400)
        api.post(towers, {**na, "sites": 2500, "generation": "g4", "vendor": "huawei"}, 400)
        out = api.post(towers, {**na, "sites": 2500, "generation": "g5", "vendor": "ericsson"})
        (radio,) = out["telecom"]["radios"]
        assert radio["sites"] == 2500 and radio["generation"] == "g5"
        api.post(f"{base}/telecom/auctions/{cband['id']}/bid", {"blocks": 2, "limit_cents": 1}, 400)
        out = api.post(
            f"{base}/telecom/auctions/{cband['id']}/bid",
            {"blocks": 2, "limit_cents": cband["reserve_cents"] * 20},
        )
        mine = next(a for a in out["telecom"]["auctions"] if a["id"] == cband["id"])
        assert mine["my_blocks"] == 2
        api.post(f"{base}/telecom/lines/{pid}", {"zero_rating": True, "satellite_partner": True})
        for _ in range(3):
            answer_events(path, loaded)
            api.post(f"{base}/advance")
        tele = api.get(f"{base}/telecom")
        payback = api.get(f"{base}/explain/network_payback?entity=north_america")
        text_out = json.dumps([tele, payback])
        with open_session(path) as session:
            state = load_state(session)
    closed = next(a for a in tele["auctions"] if a["id"] == cband["id"])
    assert closed["status"] == "closed" and closed["rounds"] > 0
    assert any(w["yours"] for w in closed["awards"]), "a limit of 20x the reserve wins"
    assert tele["licences"] and tele["licences"][0]["band"] == "mid"
    assert tele["payback"] and payback["value"] is not None
    # hidden values (62.5): the seeded world is never served
    t = state.telecom
    for word in ("value_cents", "g6_turn", "next_auction", "growth", "hidden"):
        assert word not in text_out
    for _, _, g in t.world.growth:
        assert f"{g}" not in text_out
    from tst.api.schemas import telecom as schemas

    names: set[str] = set()
    for cls in vars(schemas).values():
        if isinstance(cls, type) and hasattr(cls, "model_fields"):
            names |= set(cls.model_fields)
    hidden = {"value_cents", "g6_turn", "growth", "next_auction", "world", "bid_limit_cents"}
    assert not names & hidden


def test_prompts_never_read_telecom_draws() -> None:
    """The event and LLM code (ADR-0005) never read the telecom world, the auction draws or the
    telecom stream."""
    root = Path(__file__).resolve().parents[2] / "tst"
    for package in ("events", "llm", "conversations"):
        for source in (root / package).rglob("*.py"):
            code = source.read_text(encoding="utf-8")
            for name in ("telecom.world", "telecom.draws", "_rival_bidders", "g6_turn",
                         "next_auction", "tst.sim.telecom.spectrum"):  # fmt: skip
                assert name not in code, (source, name)
