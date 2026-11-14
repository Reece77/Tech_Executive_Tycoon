"""M28's hidden-value test (docs/formulas.md 41.9; CLAUDE.md section 8): no rival's valuation of
the player, no facility's cost position, no capex intention before its news and no seeded cycle
path reaches the API or an event prompt. A save in the living world (a game moved to 2026, its
world brought into being, then a month played) is read through every world route; each response
passes the forbidden-field check, and the numbers that are hidden appear nowhere in it."""

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
from tst.db.state_io import insert_entries, load_state, sync_state
from tst.loader import LoadedData
from tst.sim.rng import RngFactory
from tst.sim.world import bids, models
from tst.sim.world.setup import materialise

JAN_2026 = 192


def _world_save(tmp_path: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "hidden", 9, "ex_big_tech_founders", company_name="Hidden Co", data=loaded,
        save_dir=tmp_path,
    )  # fmt: skip
    with open_session(path) as session:
        old = load_state(session)
        new, entries = materialise(
            replace(old, turn=JAN_2026), RngFactory(9), loaded.balance, loaded.game_data
        )
        sync_state(session, old, new)
        insert_entries(session, entries)
        session.execute(text("UPDATE save_meta SET current_turn = :t"), {"t": JAN_2026})
        session.commit()
    return path


def test_no_hidden_world_value_reaches_the_api(tmp_path: Path, loaded: LoadedData) -> None:
    saves = tmp_path / "saves"
    path = _world_save(saves, loaded)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as c:
        api = Client(c)
        base = f"/api/saves/{path.name.removesuffix('.tst.sqlite')}"
        api.post(f"{base}/advance")
        with open_session(path) as session:
            state = load_state(session)
        bodies = [api.get(f"{base}/world-news"), api.get(f"{base}/chain")]
        for rec in state.chain_companies[:8]:
            bodies.append(api.get(f"{base}/rivals/{rec.company_id}"))
        bodies.append(api.get(f"{base}/commodities"))
    text_out = json.dumps(bodies)
    for f in state.world_facilities:
        assert f'"cost": {f.cost}' not in text_out
    for c in state.region_cycles:
        assert repr(c.level) not in text_out, ("cycle level", c)
        assert repr(c.multiplier) not in text_out, ("cycle", c)
    for g in state.world_goods:
        assert repr(g.factor) not in text_out or g.factor == 1.0, (
            "factor",
            g.good,
            _near(text_out, repr(g.factor)),
        )
    assert bodies[2]["world"]["facilities"][0]["cost_band"] in ("low", "middle", "high")


def test_a_rival_s_view_is_never_stored_or_prompted(tmp_path: Path, loaded: LoadedData) -> None:
    """The view behind a bid is drawn and dropped (41.4): no record holds it, and the event and
    LLM code that build prompts (ADR-0005) never read the bid module or the world's records."""
    with open_session(_world_save(tmp_path, loaded)) as session:
        state = load_state(session)
    rival = next(c for c in state.rivals() if c.rival_key[:1] == (0,))
    z, _ = bids.rival_draws(state, rival.id, RngFactory(9))
    view = bids.rival_view_cents(state, rival.id, 10**12, z, loaded.balance)
    dumped = repr(state)
    assert repr(view) not in dumped and str(round(view)) not in dumped
    fields = {
        name
        for cls in vars(models).values()
        if isinstance(cls, type)
        for name in getattr(cls, "__dataclass_fields__", {})
    }
    assert not {"view", "valuation", "view_cents", "valuation_cents"} & fields
    root = Path(__file__).resolve().parents[2] / "tst"
    for package in ("events", "llm"):
        for source in (root / package).rglob("*.py"):
            code = source.read_text(encoding="utf-8")
            for name in ("rival_view", "world.bids", "world_bids", "chain_companies"):
                assert name not in code, (source, name)


def _near(text: str, needle: str) -> str:
    i = text.find(needle)
    return text[max(0, i - 300) : i + 50]
