"""M54's API and hidden-value tests (docs/formulas.md 64.5; CLAUDE.md section 8). A stage-4 save in
January 2019 with cash, a fintech line, a banking line with accounts, a payments line and a line
selling in Europe: the finance routes and their actions answer, and no stress test's shock, run
draw or catastrophe is served before it happens (a run's risk only as a band); the event and LLM
code never read them."""

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
from tst.sim.geo.models import RegionalSegment
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import GameState, with_company, with_product, with_segments

JAN_2019 = ym_to_turn(2019, 1)


def _line(
    state: GameState,
    category: str,
    name: str,
    home: list[ProductSegment],
    away: list[RegionalSegment],
) -> tuple[GameState, int]:
    pid, ids = state.next_ids.take("product")
    p = Product(
        id=pid,
        company_id=state.player.id,
        category=category,
        name=name,
        status="live",
        quality=60.0,
        feature_points=40.0,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    state = replace(with_product(state, p), next_ids=ids)
    home = [replace(s, product_id=pid) for s in home]
    away = [replace(s, product_id=pid) for s in away]
    return with_segments(state, home, away), pid


def _save(tmp_path: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "fin", 6, "funded_spinout", company_name="Fin Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session:
        old = load_state(session)
        new = replace(old, turn=JAN_2019)
        new = with_company(new, replace(new.player, stage=4))
        new, _ = _line(new, "fintech", "Fin Pay", [ProductSegment(0, "smb", 6000, 500.0)], [])
        new, _ = _line(
            new,
            "banking",
            "Fin Bank",
            [
                ProductSegment(0, "bank_consumer", 800, 50_000.0),
                ProductSegment(0, "bank_business", 6000, 5_000.0),
            ],
            [],
        )
        new, _ = _line(
            new, "payments", "Fin Network", [ProductSegment(0, "pay_merchants", 57500, 100.0)], []
        )
        new, _ = _line(
            new,
            "b2b_saas",
            "Fin Cloud",
            [ProductSegment(0, "smb", 5000, 1000.0)],
            [RegionalSegment(0, "europe", "smb", 4500, 2000.0)],
        )
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
        session.execute(text("UPDATE save_meta SET current_turn = :t"), {"t": JAN_2019})
        session.commit()
    return path


def test_finserv_routes_actions_and_hidden_values(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path = _save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        body = api.get(f"{base}/finserv")
        assert body["bank"]["can_charter"] and body["bank"]["banks"] == []
        assert body["payments"]["can_launch"]
        na = {"region": "north_america"}
        out = api.post(f"{base}/finserv/partner", na)
        (bank,) = out["finserv"]["bank"]["banks"]
        assert bank["status"] == "partner"
        api.post(f"{base}/finserv/partner", na, 400)  # one bank a region
        out = api.post(f"{base}/finserv/charter", {"region": "europe"})
        eu = next(b for b in out["finserv"]["bank"]["banks"] if b["region"] == "europe")
        assert eu["status"] == "applying" and eu["charter_month"]
        api.post(
            f"{base}/finserv/banks/{eu['id']}/settings",
            {"beta": 0.95, "loan_to_deposit": 0.5, "securities_share": 0.2, "duration": 4},
            400,
        )
        api.post(
            f"{base}/finserv/banks/{eu['id']}/settings",
            {"beta": 0.3, "loan_to_deposit": 0.5, "securities_share": 0.2, "duration": 6},
        )
        out = api.post(f"{base}/finserv/networks", na)
        assert out["finserv"]["payments"]["networks"][0]["region"] == "north_america"
        api.post(f"{base}/finserv/insurance/licence", na, 400)  # no insurance line
        for _ in range(2):
            answer_events(path, loaded)
            api.post(f"{base}/advance")
        fin = api.get(f"{base}/finserv")
        eu_region = next(r for r in fin["currency"]["regions"] if r["region"] == "europe")
        assert eu_region["revenue_cents"] > 0 and eu_region["exposure_cents"] > 0
        out = api.post(
            f"{base}/finserv/forwards",
            {"region": "europe", "notional_cents": 10**15, "months": 6},
            400,
        )
        out = api.post(
            f"{base}/finserv/forwards",
            {"region": "europe", "notional_cents": eu_region["exposure_cents"] // 2, "months": 6},
        )
        assert out["finserv"]["currency"]["hedges"][0]["status"] == "open"
        out = api.post(f"{base}/finserv/programme", {"share": 0.8, "term_months": 12})
        assert out["finserv"]["currency"]["programme"]["share"] == 0.8
        explain = api.get(f"{base}/explain/fx_result?entity=europe")
        text_out = json.dumps([fin, out, explain])
        with open_session(path) as session:
            state = load_state(session)
    na_bank = next(b for b in fin["bank"]["banks"] if b["region"] == "north_america")
    assert na_bank["deposits_cents"] > 0
    assert na_bank["run_risk"] in ("low", "elevated", "high")
    # hidden values (64.5): no run chance, no stress shock before it runs, no catastrophe before
    # it happens, no index beyond this month
    assert all(b["stress"] == [] for b in fin["bank"]["banks"])  # no June test has run yet
    assert fin["insurance"]["catastrophes"] == []
    assert all(
        len(w) <= max(0, state.turn - loaded.balance.fx.start_turn + 1) for _, w in state.fx.walk
    )
    for word in ("chance", "shock", "pressure", "walk", "growth"):
        assert word not in text_out
    from tst.api.schemas import finserv as schemas

    names: set[str] = set()
    for cls in vars(schemas).values():
        if isinstance(cls, type) and hasattr(cls, "model_fields"):
            names |= set(cls.model_fields)
    hidden = {
        "run_chance",
        "chance",
        "shock",
        "rate_shock",
        "loss_mult",
        "outflow",
        "walk",
        "cats",
        "growth",
    }
    assert not names & hidden


def test_prompts_never_read_finance_draws() -> None:
    """The event and LLM code (ADR-0005) never read the finance world, the run, stress or
    catastrophe draws, the fx walk or the finserv and fx streams."""
    root = Path(__file__).resolve().parents[2] / "tst"
    for package in ("events", "llm", "conversations"):
        for source in (root / package).rglob("*.py"):
            code = source.read_text(encoding="utf-8")
            for name in ("finserv.world", "run_chance", "_stress", "draw_cats", "fx.walk",
                         "walk_month", "tst.sim.finserv.banks", '"finserv"', '"fx"'):  # fmt: skip
                assert name not in code, (source, name)
