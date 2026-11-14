from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import event_cash_cents
from tst.api import schemas
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db import repository
from tst.db.repository import open_session, read_meta

GARAGE_CASH = 5_000_000
OVERHEAD = 110_000  # M1b solo founder: $500 base overhead + $600 office


@pytest.fixture
def save_dir(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def client(save_dir: Path) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=save_dir)
    with TestClient(app) as c:
        yield c


def create(client: TestClient, **overrides: Any) -> Any:
    body = {"name": "dev", "seed": 42, "scenario": "garage_bootstrap", "company_name": "Test Co"}
    body.update(overrides)
    return client.post("/api/saves", json=body)


def test_create_list_get(client: TestClient) -> None:
    assert client.get("/api/saves").json() == []
    res = create(client)
    assert res.status_code == 201
    expected = {
        "save_id": "dev",
        "company_name": "Test Co",
        "scenario_id": "garage_bootstrap",
        "difficulty": "standard",
        "turn": 0,
        "date_label": "Jan 2010",
        "display_name": "dev",  # M7b: the saves manager's columns
        "game_state": "active",
        "ironman": False,
        "busy": False,
        "mode": "campaign",  # M15b (30.2-30.3): a campaign has no score until December
        "score": None,
        "mod_name": None,  # M25: a game without a mod
    }

    def stable(body: dict[str, Any]) -> dict[str, Any]:
        assert body["size_bytes"] > 0 and body["last_played"]  # vary with the file
        return {k: v for k, v in body.items() if k not in ("size_bytes", "last_played")}

    assert stable(res.json()) == expected
    assert [stable(s) for s in client.get("/api/saves").json()] == [expected]
    assert stable(client.get("/api/saves/dev").json()) == expected


def test_overview_and_advance(client: TestClient, save_dir: Path) -> None:
    create(client)
    ov = client.get("/api/saves/dev/overview").json()
    assert ov["date_label"] == "Jan 2010"
    assert ov["cash_cents"] == GARAGE_CASH
    assert ov["monthly_burn_cents"] == 0
    assert ov["runway_months"] == 45  # $50,000 / $1,100 projected for January (M1c)
    assert ov["history"] == []

    first = client.post("/api/saves/dev/advance").json()
    assert first["date_label"] == "Feb 2010"
    assert first["cash_cents"] == GARAGE_CASH - OVERHEAD
    assert first["monthly_burn_cents"] == OVERHEAD
    assert first["runway_months"] == 44  # $48,900 / $1,100 projected for February

    second = client.post("/api/saves/dev/advance").json()
    assert second["date_label"] == "Mar 2010"
    assert second["turn"] == 2
    events = event_cash_cents(repository.save_path(save_dir, "dev"))  # M6: answered at Continue
    assert second["cash_cents"] == GARAGE_CASH - 2 * OVERHEAD + events
    assert [p["date_label"] for p in second["history"]] == ["Jan 2010", "Feb 2010"]
    assert client.get("/api/saves/dev/overview").json() == second


def test_history_keeps_last_12(client: TestClient) -> None:
    create(client)
    for _ in range(14):
        ov = client.post("/api/saves/dev/advance").json()
    assert len(ov["history"]) == 12
    assert ov["history"][0]["date_label"] == "Mar 2010"
    assert ov["history"][-1]["date_label"] == "Feb 2011"


def test_missing_seed_is_generated_and_stored(client: TestClient, save_dir: Path) -> None:
    res = create(client, seed=None)
    assert res.status_code == 201
    with open_session(save_dir / "dev.tst.sqlite") as session:
        seed = read_meta(session).master_seed
    assert 0 <= seed < 2**63


@pytest.mark.parametrize(
    ("overrides", "status", "code"),
    [
        ({"scenario": "nope"}, 400, "unknown_scenario"),
        ({"scenario": "mineral_first_prospector"}, 400, "scenario_unavailable"),
        ({"name": "Bad Name"}, 400, "invalid_save_name"),
        ({"difficulty": "nightmare"}, 400, "unknown_difficulty"),
        ({"company_name": "   "}, 400, "invalid_company_name"),
        ({"seed": -1}, 422, "invalid_request"),
        ({"company_name": ""}, 422, "invalid_request"),
    ],
)
def test_create_errors(
    client: TestClient, overrides: dict[str, Any], status: int, code: str
) -> None:
    res = create(client, **overrides)
    assert res.status_code == status
    body = res.json()
    assert set(body) == {"code", "message"}
    assert body["code"] == code


def test_duplicate_and_missing(client: TestClient) -> None:
    create(client)
    dup = create(client)
    assert dup.status_code == 409
    assert dup.json()["code"] == "save_exists"
    for method, url in [
        ("get", "/api/saves/nope"),
        ("get", "/api/saves/nope/overview"),
        ("post", "/api/saves/nope/advance"),
    ]:
        res = client.request(method, url)
        assert res.status_code == 404
        assert res.json() == {"code": "save_not_found", "message": "no save named 'nope'"}


def test_scenarios(client: TestClient) -> None:
    scenarios = {s["id"]: s for s in client.get("/api/meta/scenarios").json()}
    assert list(scenarios) == [
        "garage_bootstrap",
        "ex_big_tech_founders",
        "funded_spinout",
        "mineral_first_prospector",
    ]
    assert scenarios["garage_bootstrap"]["starting_cash_cents"] == GARAGE_CASH
    assert scenarios["garage_bootstrap"]["selectable"] is True
    assert scenarios["mineral_first_prospector"]["selectable"] is False


FORBIDDEN_NAMES = frozenset({"current_ability", "potential_ability", "master_seed"})
FORBIDDEN_PREFIXES = ("true_", "hidden_")
# formulas.md 11.13: product responses never carry Q_cap, development skill d_i, output o_i,
# sales capacity or per-person contributions, which would reveal true skills (M3a).
PRODUCT_FORBIDDEN_NAMES = frozenset(
    {
        "q_cap",
        "qcap",
        "quality_cap",
        "d_i",
        "o_i",
        "dev_skill",
        "output",
        "base_output",
        "capacity",
        "sales_capacity",
        "cap",
        "contribution",
        "contributions",
        "mu",
        "sell_skill",
        "marketing_skill",
    }
)


# formulas.md 14.9: never V_base, a firm's bias or noise, or the SAFE acceptance probability
# (M4a); the SAFE dialog gets a hint band only.
FINANCE_FORBIDDEN_NAMES = frozenset(
    {
        # M14b (29.6): a bold claim's share and backfire, rivals' decision weights
        "share_bp",
        "backfired",
        "target_mult",
        # M13 (25.8): the book's draw, the sentiment behind the price, V_f, the triggers
        "demand_draw",
        "book_demand",
        "sentiment",
        "value_cents",
        "fundamental_value_cents",
        "below_value_months",
        "below_takeover_months",
        "v_base",
        "base_value",
        "base_value_cents",
        "bias",
        "noise",
        "valuation_noise",
        "valuation_noise_sd",
        "z",
        "probability",
        "acceptance_probability",
        "safe_probability",
        "p",
        "response",
        "response_chance",
    }
)


# formulas.md 15.5-15.6 (M5): never a rival's utilities, needs, weights, noise or cash, nor
# an approach's probability; money is a label and an approach a band.
RIVAL_FORBIDDEN_NAMES = frozenset(
    {
        "utility",
        "utilities",
        "need",
        "needs",
        "personality_weights",
        "rival_cash_cents",
        "cash_months",
        "pool_headcount",
        "pool_skill",
        "approach_probability",
        "poach_probability",
        "chance",
    }
)


# formulas.md 16.9 (M6): never a trigger's strength, an effect's cap, the cash base of the caps,
# or a relationship's number; effects are words and relationships labels.
EVENT_FORBIDDEN_NAMES = frozenset(
    {
        "strength",
        "trigger_strength",
        "cap",
        "caps",
        "effect_cap",
        "cash_base_cents",
        "affinity",
        "relationship_value",
        "start_value",
        "api_key",
        "anthropic_api_key",
    }
)


# formulas.md 28.8 (M14): never a private company's V_f or its parts, a reservation, a board's
# bar, a tender's chance, a review's block probability or its draw, or problems before
# diligence (TargetOut calls revealed ones `findings`).
MNA_FORBIDDEN_NAMES = frozenset(
    {
        "reservation_cents",
        "reservation",
        "board_bar",
        "tender_chance",
        "block_probability",
        "blocked_draw",
        "fundamental_value_cents",
        "value_cents",
        "multiple",
        "premium",
        "distressed",
    }
)


# M24 (32.8): never the scandal risk, a scandal's chance, or a pending second story (a
# pitch's `risk` word is public, so test_api_founder checks the founder's schemas for it).
FOUNDER_FORBIDDEN_NAMES = frozenset({"scandal_risk", "scandal_chance", "second_story", "risk_rate"})

# M26 (37.7): never a trade's regulatory risk, the news month or investigation month drawn
# for it, its gain before a finding, a concealed conflict's discovery month, or a family-office
# manager's true skill ("risk" alone is a pitch's public risk words, M13b).
INVESTING_FORBIDDEN_NAMES = frozenset(
    {
        "regulatory_risk",
        "public_turn",
        "investigate_turn",
        "gain_cents",
        "coi_found_turn",
        "manager_skill",
    }
)

# M18 (34.5): never a block's depth, distance to infrastructure, permitting difficulty or
# community sensitivity, a permit's decision month, or a team's range factor (which would
# reveal its true skill); true_* and hidden_* fields are caught by the prefixes.
EXPLORATION_FORBIDDEN_NAMES = frozenset(
    {
        "depth_m",
        "infra_km",
        "permit_difficulty",
        "sensitivity",
        "decision_turn",
        "due_turn",
        "range_factor",
        "team_factor",
        "factor",
    }
)

# M28 (41.9): never a rival's valuation of anyone, a facility's cost position (only its band),
# a cycle's level, depth or months, a facility's mothball counters or the world's balance factor
# (caught above as `factor`).
WORLD_FORBIDDEN_NAMES = frozenset(
    {
        "cost",
        "cost_position",
        "view_cents",
        "valuation_cents",
        "rival_view",
        "phase_months",
        "phase_start",
        "below_months",
        "above_months",
        "multiplier",
        "cycle_level",
    }
)


def forbidden(name: str) -> bool:
    """ADR-0007 exact-name rule (potential_phrase is allowed), plus the 11.13 names."""
    return (
        name in FORBIDDEN_NAMES
        or name in PRODUCT_FORBIDDEN_NAMES
        or name in FINANCE_FORBIDDEN_NAMES
        or name in RIVAL_FORBIDDEN_NAMES
        or name in EVENT_FORBIDDEN_NAMES
        or name in MNA_FORBIDDEN_NAMES
        or name in FOUNDER_FORBIDDEN_NAMES
        or name in INVESTING_FORBIDDEN_NAMES
        or name in EXPLORATION_FORBIDDEN_NAMES
        or name in WORLD_FORBIDDEN_NAMES
        or name.startswith(FORBIDDEN_PREFIXES)
    )


def test_no_hidden_fields_in_api_models(client: TestClient) -> None:
    """ADR-0007: no schema in the OpenAPI contract has a hidden-value field."""
    assert schemas is not None
    components = client.get("/openapi.json").json()["components"]["schemas"]
    assert "PersonProfileOut" in components
    bad = [
        f"{model}.{field}"
        for model, schema in components.items()
        for field in schema.get("properties", {})
        if forbidden(field)
    ]
    assert bad == []
    assert not forbidden("potential_phrase")
    assert forbidden("hidden_traits") and forbidden("true_skill")
    assert "ProductOut" in components and "MarketProductOut" in components
    assert forbidden("q_cap") and forbidden("contribution") and not forbidden("pace")
    assert "CapTableOut" in components and "SafeHintOut" in components
    assert forbidden("v_base") and forbidden("bias") and not forbidden("hint")
    assert "RivalProfileOut" in components and "ApproachOut" in components
    assert forbidden("utility") and forbidden("cash_months") and not forbidden("band")


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    """Every forbidden key anywhere in a JSON response."""
    found = []
    if isinstance(value, dict):
        for key, inner in value.items():
            if forbidden(str(key)):
                found.append(f"{path}.{key}")
            found += find_forbidden_keys(inner, f"{path}.{key}")
    elif isinstance(value, list):
        for i, inner in enumerate(value):
            found += find_forbidden_keys(inner, f"{path}[{i}]")
    return found


def test_openapi_declares_response_models(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    for path, ops in spec["paths"].items():
        for op in ops.values():
            # 202: a holiday starts as a job; 204: a deleted save has no body (M7b)
            assert {"200", "201", "202", "204"} & set(op["responses"]), path
            assert op.get("operationId"), path


def test_create_with_founder(client: TestClient) -> None:
    founder = {
        "background": "academic",
        "personality_preset": "scientist",
        "age": 35,
        "first_name": "Ada",
        "last_name": "Mensah",
        "interests": ["ai", "climate"],
        "work_style": "researcher",
    }
    res = create(client, founder=founder)
    assert res.status_code == 201, res.json()


@pytest.mark.parametrize(
    ("founder", "message"),
    [
        ({"allocation": {"software_engineering": 71}}, "spends 71 points"),
        ({"background": "geologist"}, "unlocks in v3"),
        ({"age": 70}, "age must be 22-60"),
    ],
)
def test_create_with_bad_founder(client: TestClient, founder: dict[str, Any], message: str) -> None:
    res = create(client, founder=founder)
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_founder"
    assert message in res.json()["message"]
