"""M55's API and hidden-value tests (docs/formulas.md 65; CLAUDE.md section 8). A stage-3 save in
January 2016 with cash and a video line: the media routes and their actions answer (sign a lead,
green-light a series with them, overrule them, refuse an ad tier before its month), and no
audience draw before release, no lead's ego or loyalty and no true creative or vision is served;
the event, LLM and conversation code never read them."""

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

JAN_2016 = ym_to_turn(2016, 1)


def _save(tmp_path: Path, loaded: LoadedData) -> tuple[Path, int]:
    path = create_save(
        "nova", 6, "funded_spinout", company_name="Nova Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session:
        old = load_state(session)
        new = replace(old, turn=JAN_2016)
        new = with_company(new, replace(new.player, stage=3))
        pid, ids = new.next_ids.take("product")
        p = Product(
            id=pid,
            company_id=new.player.id,
            category="streaming",
            name="Nova Stream",
            status="live",
            quality=60.0,
            feature_points=40.0,
            brand=40.0,
            marketing_budget_cents=0,
            created_turn=new.turn,
            launched_turn=new.turn,
        )
        new = replace(with_product(new, p), next_ids=ids)
        new = with_segments(new, [ProductSegment(pid, "viewers", 900, 0.0)], [])
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
        session.execute(text("UPDATE save_meta SET current_turn = :t"), {"t": JAN_2016})
        session.commit()
    return path, pid


def _keys(node: object, out: set[str]) -> set[str]:
    if isinstance(node, dict):
        for k, v in node.items():
            out.add(k)
            _keys(v, out)
    elif isinstance(node, list):
        for x in node:
            _keys(x, out)
    return out


def test_media_routes_actions_and_hidden_values(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path, pid = _save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        answer_events(path, loaded)
        api.post(f"{base}/advance")
        body = api.get(f"{base}/media")
        offers = body["studio"]["offers"]
        assert offers, "January's leads are on offer"
        o = offers[0]
        api.post(f"{base}/media/leads", {"year": o["year"], "n": o["n"], "years": 99}, 400)
        out = api.post(f"{base}/media/leads", {"year": o["year"], "n": o["n"], "years": 3})
        (lead,) = out["media"]["studio"]["leads"]
        series = next(k for k in out["media"]["studio"]["kinds"] if k["key"] == "series")
        green = {
            "name": "Harbour Lights",
            "kind": "series",
            "budget_cents": series["typical_budget_cents"],
            "lead_person_id": lead["person_id"],
            "window": "own",
            "service_product_id": pid,
        }
        api.post(f"{base}/media/titles", {**green, "budget_cents": 1}, 400)
        out = api.post(f"{base}/media/titles", green)
        (title,) = out["media"]["studio"]["slate"]
        assert title["audience"] is None and title["quality"] is None and title["expected"] is None
        out = api.post(f"{base}/media/titles/{title['id']}/overrule")
        inbox = api.get(f"{base}/inbox")
        assert any("Morale warning" in json.dumps(x) for x in inbox["items"]), "the warning"
        api.post(f"{base}/media/lines/{pid}", {"ad_tier": True}, 400)  # before November 2022
        months = series["dev_months"]
        texts = []
        for _ in range(months + 1):
            answer_events(path, loaded)
            api.post(f"{base}/advance")
            texts.append(json.dumps(api.get(f"{base}/media")))
        media = api.get(f"{base}/media")
        explain = api.get(f"{base}/explain/title_result?entity={title['id']}")
        assert explain["value"] is not None and explain["items"]
        with open_session(path) as session:
            state = load_state(session)
    released = media["studio"]["released"]
    assert released and released[0]["audience"] is not None, "its audience at release"
    t = state.media.title(title["id"])
    assert t is not None and t.audience is not None
    # hidden values: no ego, loyalty, true creative or vision, nor an audience before release
    keys = set()
    for x in (body, out, media):
        _keys(x, keys)
    for word in ("ego", "loyalty", "creative_off", "vision_off", "draw", "morale_sum", "grievance"):
        assert word not in keys
    for x in state.media.leads:
        assert f"{x.ego}" not in "".join(texts)
        assert f"{x.loyalty}" not in "".join(texts)
        assert f"{x.creative}" not in "".join(texts)
    before = [s for s in texts if '"stage": "development"' in s and title["name"] in s]
    assert before
    from tst.api.schemas import media as schemas

    names: set[str] = set()
    for cls in vars(schemas).values():
        if isinstance(cls, type) and hasattr(cls, "model_fields"):
            names |= set(cls.model_fields)
    assert not names & {"ego", "loyalty", "creative_off", "vision_off", "draws", "grievance"}


def test_prompts_never_read_media_hidden_values() -> None:
    """The event, LLM and conversation code (ADR-0005) never read a lead's hidden traits, the
    audience draw or the media stream."""
    root = Path(__file__).resolve().parents[2] / "tst"
    for package in ("events", "llm", "conversations"):
        for source in (root / package).rglob("*.py"):
            code = source.read_text(encoding="utf-8")
            for name in ("media.leads", "talent.candidate", "draw_audience", "media.draws",
                         "tst.sim.media.draws", "creative_off", ".grievance"):  # fmt: skip
                assert name not in code, (source, name)
