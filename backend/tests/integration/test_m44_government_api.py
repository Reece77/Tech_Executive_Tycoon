"""M44's API and hidden-value tests (docs/formulas.md 57.7; CLAUDE.md section 8). A stage-4 save in
2027 with a live cloud product and staff: the Government routes and their actions answer; no
rival's bid, award or protest draw, pending clearance's decision month or outcome, tender before
its announcement or seeded budget growth is served, and the event and LLM code never read them."""

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
from tst.sim.government.models import Tender
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.products.models import Product
from tst.sim.state import with_company, with_product

JAN_2027 = 204


def _save(tmp_path: Path, loaded: LoadedData) -> tuple[Path, int, int]:
    path = create_save(
        "gov", 7, "funded_spinout", company_name="Gov Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session:
        old = load_state(session)
        new = replace(old, turn=JAN_2027 - 1)
        new = with_company(new, replace(new.player, stage=4))
        pid, ids = new.next_ids.take("product")
        p = Product(
            id=pid,
            company_id=new.player.id,
            category="cloud_hosting",
            name="Gov Cloud",
            status="live",
            quality=85.0,
            feature_points=500.0,
            brand=40.0,
            marketing_budget_cents=0,
            created_turn=new.turn,
            launched_turn=new.turn,
        )
        new = replace(with_product(new, p), next_ids=ids)
        tender = Tender(
            id=9000,
            government="us",
            area="cloud",
            buyer="civil",
            title="Test cloud",
            announce_turn=JAN_2027,
            close_turn=JAN_2027 + 2,
            award_turn=JAN_2027 + 3,
            value_cents=2_000_000_000,
            term_months=36,
            base_months=24,
            contract="fixed_price",
            clearance="none",
        )
        hidden = replace(tender, id=9001, title="Not yet", announce_turn=JAN_2027 + 6)
        new = replace(new, tenders=(tender, hidden))
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
    return path, pid, 9000


def test_government_routes_actions_and_hidden_values(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path, pid, tid = _save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        api.post(f"{base}/advance")
        body = api.get(f"{base}/government")
        assert body["enabled"]
        titles = {t["title"] for t in body["tenders"]}
        assert "Test cloud" in titles and "Not yet" not in titles  # hidden until announced
        ours = next(t for t in body["tenders"] if t["id"] == tid)
        assert ours["options"] and ours["options"][0]["product_id"] == pid
        api.post(f"{base}/government/tenders/{tid}/bid", {"product_id": pid, "price_cents": 1}, 400)
        out = api.post(
            f"{base}/government/tenders/{tid}/bid",
            {"product_id": pid, "price_cents": 1_500_000_000, "team": []},
        )
        mine = next(t for t in out["government"]["tenders"] if t["id"] == tid)["my_bid"]
        assert mine["status"] == "submitted" and mine["band"] is None
        staff = [s["person_id"] for s in body["staff"]]
        api.post(f"{base}/government/clearances", {"person_ids": staff[:1], "level": "top_secret"})
        for _ in range(4):  # the award is in March: three months after the bid's January
            answer_events(path, loaded)
            api.post(f"{base}/advance")
        screen = api.get(f"{base}/government")
        decided = next(t for t in screen["tenders"] if t["id"] == tid)
        explain = (
            api.get(f"{base}/explain/bid_score?entity={decided['my_bid']['id']}")
            if decided["my_bid"]
            else {}
        )
        text_out = json.dumps([screen, explain])
        with open_session(path) as session:
            state = load_state(session)
    bid = state.gov_bids[0]
    assert bid.status in ("won", "lost")
    assert decided["my_bid"]["band"] is not None and decided["winning_band"] is not None
    # the exact score never leaves the engine; only bands
    assert bid.terms is not None and f"{bid.terms.weighted}" not in text_out
    clearance = state.clearances[0]
    if clearance.status == "pending":
        assert "due" not in text_out
    for word in ("draw", "chance", "probability", "sustain", "due_turn", 'outcome"', "growth"):
        assert word not in text_out
    for _, _, g in state.government_world.growth:
        assert f"{g}" not in text_out
    from tst.api.schemas import government as schemas

    names: set[str] = set()
    for cls in vars(schemas).values():
        if isinstance(cls, type) and hasattr(cls, "model_fields"):
            names |= set(cls.model_fields)
    hidden = {
        "due_turn",
        "outcome",
        "sustain",
        "score",
        "growth",
        "merit",
        "rival_bids",
        "total_score",
    }
    assert not names & hidden


def test_prompts_never_read_government_draws() -> None:
    """The event and LLM code (ADR-0005) never read the government world, bids, clearances,
    protests or the defence stream."""
    root = Path(__file__).resolve().parents[2] / "tst"
    for package in ("events", "llm"):
        for source in (root / package).rglob("*.py"):
            code = source.read_text(encoding="utf-8")
            for name in ("government_world", "government.draws", "gov_bids", "clearances",
                         "protests", "government.awards"):  # fmt: skip
                assert name not in code, (source, name)
