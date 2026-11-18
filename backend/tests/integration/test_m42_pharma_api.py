"""M42's API and hidden-value tests (docs/formulas.md 55.7; CLAUDE.md section 8). A 2026 save with
an AI model and a programme whose hidden efficacy and safety are distinctive numbers: the Pharma
routes and their actions answer; the true values, readout draws before they happen, reviews'
drawn months and seeded rules never reach a response, and the event and LLM code never read
them."""

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
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.pharma.models import Programme

JAN_2026 = 192
TRUE_EFFICACY = 0.8123457
TRUE_SAFETY = 0.6543219


def _save(tmp_path: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "pharma", 7, "funded_spinout", company_name="Rx Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session:
        old = load_state(session)
        new = replace(old, turn=JAN_2026 - 1)
        p = Programme(
            id=1,
            company_id=new.player.id,
            name="RX-1",
            indication="obesity",
            area="metabolic",
            modality="small_molecule",
            stage="phase1",
            start_turn=new.turn - 30,
            due_turn=new.turn - 1,
            efficacy=TRUE_EFFICACY,
            safety=TRUE_SAFETY,
            status="ready",
            obs_n=1,
            obs_eff=0.55,
            obs_safety=0.7,
            patent_turn=new.turn - 60,
            ind_turn=new.turn - 30,
        )
        new = replace(new, pharma_programmes=(p,))
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
    return path


def test_pharma_routes_actions_and_hidden_values(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path = _save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        body = api.get(f"{base}/pharma")
        assert body["engaged"]
        (prog,) = body["programmes"]
        assert prog["next_stage"] == "phase2" and prog["next_chance"] is not None
        assert {r["key"] for r in body["regulators"]} == {
            "fda_drugs", "ema", "pmda_drugs", "nmpa_drugs"
        }  # fmt: skip
        assert {r["name"] for r in body["rivals"]} >= {"Pfizer", "Eli Lilly", "Teva"}
        api.post(f"{base}/pharma/trial", {"programme_id": 1, "design": "huge"}, 422)
        out = api.post(f"{base}/pharma/trial", {"programme_id": 1, "design": "large"})
        prog = out["pharma"]["programmes"][0]
        assert prog["stage"] == "phase2" and prog["status"] == "active"
        assert prog["design"] == "large" and prog["cost_cents"] > 0
        api.post(f"{base}/pharma/file", {"programme_id": 1, "regulator": "fda_drugs"}, 400)
        out = api.post(
            f"{base}/pharma/start",
            {"name": "RX-2", "indication": "lung_cancer", "modality": "biologic"},
        )
        assert [p["stage"] for p in out["pharma"]["programmes"]] == ["phase2", "discovery"]
        out = api.post(f"{base}/pharma/plant", {"kind": "api", "region": "europe"})
        assert out["pharma"]["plants"][0]["live"] is False
        api.post(f"{base}/pharma/cmo", {"kind": "biologics", "cmo": "Samsung Biologics"})
        api.post(f"{base}/pharma/stop", {"programme_id": 2})
        api.post(f"{base}/advance")
        answer_events(path, loaded)
        api.post(f"{base}/advance")
        body = api.get(f"{base}/pharma")
        text_out = json.dumps(body)
        assert body["assets"], "assets are listed each January once the company is engaged"
    for value in (TRUE_EFFICACY, TRUE_SAFETY):
        assert str(value) not in text_out and f"{value:.3f}" not in text_out
    for word in ("safety", "due_turn", "adcom_turn", "logit", "taken_by"):
        assert word not in text_out
    from tst.api.schemas import pharma as schemas

    names: set[str] = set()
    for cls in vars(schemas).values():
        if isinstance(cls, type) and hasattr(cls, "model_fields"):
            names |= set(cls.model_fields)
    assert not names & {"safety", "due_turn", "adcom_turn", "obs_safety", "true_efficacy"}
    # efficacy is served only as a range
    assert schemas.ProgrammeOut.model_fields["efficacy"].annotation is schemas.RangeOut
    assert schemas.AssetOut.model_fields["efficacy"].annotation is schemas.RangeOut


def test_prompts_never_read_pharma_hidden_values() -> None:
    """The event and LLM code (ADR-0005) never read a molecule's hidden values, a review's drawn
    month or the pharma stream."""
    root = Path(__file__).resolve().parents[2] / "tst"
    for package in ("events", "llm"):
        for source in (root / package).rglob("*.py"):
            code = source.read_text(encoding="utf-8")
            for name in ("pharma_programmes", "pharma_assets", "pharma.draws", "pharma_reviews",
                         ".efficacy", "obs_eff"):  # fmt: skip
                assert name not in code, (source, name)
