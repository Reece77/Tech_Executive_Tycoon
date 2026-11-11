"""M26 API (formulas.md 37.7): the Investments tab and the founder's investing actions, through
the persistence path; and the hidden-value test: a trade's regulatory risk, an
investigation's draw and timing, a concealed conflict's discovery and the family-office
manager's true skill never reach a response or an LLM prompt (only a "sensitive window"
flag and the manager's revealed range)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db.repository import create_save, open_session, run_turn
from tst.db.state_io import load_state, sync_state
from tst.events.context import Kpis, build_prompt
from tst.loader import LoadedData
from tst.sim.events.director import eligible_targets
from tst.sim.events.models import GameEvent
from tst.sim.founder import personal
from tst.sim.founder.investing_models import PersonalTrade
from tst.sim.state import GameState, with_angel_stake, with_trade

SAVE = "investing"
BASE = f"/api/saves/{SAVE}"
PLANTED_RISK = 23.456789  # unmistakable hidden values
PLANTED_TURN = 4321
PLANTED_GAIN = 987_654_321


@pytest.fixture
def api(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path]]:
    save_dir = tmp_path / "saves"
    path = create_save(
        SAVE, 5, "funded_spinout", company_name="Kestrel", data=loaded, save_dir=save_dir
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as client:
        yield Client(client), path


def _edit(path: Path, change):  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, change(before))


def _state(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def _fid(state: GameState) -> int:
    founder = state.founder_of(state.player.id)
    assert founder is not None
    return founder.id


def _rich(state: GameState) -> GameState:
    return personal.credit(state, _fid(state), 60_000_000_000, "exit")  # $600M


def _until_round(path: Path, client: Client, loaded: LoadedData) -> dict:  # type: ignore[type-arg]
    for _ in range(8):
        out = client.get(f"{BASE}/founder/investments")
        if out["open_rounds"]:
            return out  # type: ignore[no-any-return]
        run_turn(path, loaded)
    raise AssertionError("no startup round opened in 8 months")


def test_investments_tab_and_actions(api: tuple[Client, Path], loaded: LoadedData) -> None:
    client, path = api
    _edit(path, _rich)
    out = _until_round(path, client, loaded)
    assert out["personal_cash_cents"] == 60_000_000_000
    assert out["net_worth"]["cash_cents"] == 60_000_000_000
    rnd = out["open_rounds"][0]
    joined = client.post(
        f"{BASE}/founder/angel", {"company_id": rnd["company_id"], "cents": 2_500_000}
    )
    (stake,) = joined["investments"]["stakes"]
    assert stake["company_id"] == rnd["company_id"] and stake["stake_pct"] > 0
    assert stake["funding"] and stake["cash_band"] in ("deep pockets", "comfortable", "tight")
    # M23c: an estimated value range from the startup's public numbers beside the round's mark
    assert 0 < stake["estimate_low_cents"] <= stake["estimate_high_cents"]
    listed = next(c for c in joined["investments"]["listed"] if not c["own"])
    bought = client.post(
        f"{BASE}/founder/shares",
        {"company_id": listed["company_id"], "side": "buy", "shares": 1000},
    )
    (holding,) = bought["investments"]["holdings"]
    assert holding["shares"] == 1000
    assert bought["investments"]["trades"][0]["sensitive"] is False
    formed = client.post(f"{BASE}/founder/family-office", {"mandate": "aggressive"})
    office = formed["investments"]["family_office"]
    assert office["mandate"] == "aggressive"
    assert 1 <= office["manager_skill_low"] <= office["manager_skill_high"] <= 20
    moved = client.post(f"{BASE}/founder/family-office/move", {"cents": 10_000_000_000})
    assert moved["investments"]["family_office"]["balance_cents"] == 10_000_000_000
    client.post(f"{BASE}/founder/family-office/mandate", {"mandate": "balanced"})
    refused = client.post(
        f"{BASE}/founder/angel", {"company_id": rnd["company_id"], "cents": 1}, status=400
    )
    assert "at least" in json.dumps(refused)
    run_turn(path, loaded)
    after = client.get(f"{BASE}/founder/investments")
    assert after["history"] and after["index"]
    assert after["family_office"]["returns"]
    founder = client.get(f"{BASE}/founder")
    assert "wealth" in founder["legacy"] and founder["legacy"]["net_worth_cents"] > 0


def _plant(state: GameState) -> GameState:
    """A sensitive trade with planted hidden values, and a concealed conflict."""
    state = _rich(state)
    fid = _fid(state)
    rival = next(c for c in state.companies if not c.is_player)
    trade = PersonalTrade(
        id=1,
        person_id=fid,
        company_id=rival.id,
        turn=state.turn,
        side="buy",
        shares=10,
        price_cents=100,
        cost_cents=1,
        sensitive_target_id=rival.id,
        risk=PLANTED_RISK,
        public_turn=PLANTED_TURN,
        investigate_turn=PLANTED_TURN,
        gain_cents=PLANTED_GAIN,
        resolved=True,
    )
    from tst.sim.founder.investing_models import AngelStake

    stake = AngelStake(
        1,
        fid,
        rival.id,
        1000,
        100,
        state.turn,
        1000,
        coi_turn=state.turn,
        coi_answer="conceal",
        coi_found_turn=PLANTED_TURN,
    )
    return with_angel_stake(with_trade(state, trade), stake)


def _planted(text: str) -> bool:
    return any(
        str(v) in text for v in (PLANTED_RISK, "23.45", PLANTED_TURN, PLANTED_GAIN, "987654")
    )


def test_regulatory_risk_never_in_the_api(api: tuple[Client, Path], loaded: LoadedData) -> None:
    client, path = api
    _edit(path, _plant)
    state = _state(path)
    office_state = client.post(f"{BASE}/founder/family-office", {"mandate": "balanced"})
    manager = _state(path).person(_state(path).family_offices[0].manager_id)
    true_skill = manager.skills["finance"]
    bodies = [
        client.get(f"{BASE}/founder/investments"),
        client.get(f"{BASE}/founder"),
        client.get(f"{BASE}/overview"),
        office_state,
    ]
    text = json.dumps(bodies)
    assert not _planted(text)
    for word in ('"risk"', "investigate_turn", "public_turn", "coi_found_turn", "gain_cents"):
        assert word not in text, word
    trade = bodies[0]["trades"][0]
    assert trade["sensitive"] is True and trade["investigation"] is None
    assert bodies[0]["stakes"][0]["conflict"] == "concealed"
    office = bodies[0]["family_office"]
    assert office["manager_skill_low"] <= round(true_skill) <= office["manager_skill_high"]
    assert 'manager_skill"' not in text and "true_skill" not in text
    schemas = client.get("/openapi.json")["components"]["schemas"]
    for model in ("InvestmentsOut", "TradeOut", "AngelStakeOut", "FamilyOfficeOut", "ListedOut"):
        fields = set(schemas[model]["properties"])
        assert not {"risk", "chance", "investigate_turn", "coi_found_turn"} & fields, model
    assert state.personal_trades[0].risk == PLANTED_RISK  # still there, in the engine


def test_regulatory_risk_never_in_a_prompt(api: tuple[Client, Path], loaded: LoadedData) -> None:
    _, path = api
    _edit(path, _plant)
    state = _state(path)
    texts = []
    for template in loaded.game_data.event_templates:
        if template.category not in ("founder", "press", "finance"):
            continue
        event = GameEvent(
            id=1,
            company_id=1,
            turn=state.turn,
            template_id=template.id,
            category=template.category,
            severity="critical" if template.is_critical else template.severities[0],
            trigger=template.trigger,
            strength=1.0,
        )
        system, user = build_prompt(
            state,
            event,
            template,
            eligible_targets(state, event),
            Kpis(10**9, None, 0, 1, 0),
            loaded.balance,
            loaded.game_data,
        )
        texts.append(system + user)
    joined = "\n".join(texts)
    assert any("personal_" in t.id for t in loaded.game_data.event_templates)
    assert texts and not _planted(joined)
