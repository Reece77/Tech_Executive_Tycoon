from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from tst.api import schemas
from tst.api.app import create_app
from tst.config import Settings, get_settings
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
    }
    assert res.json() == expected
    assert client.get("/api/saves").json() == [expected]
    assert client.get("/api/saves/dev").json() == expected


def test_overview_and_advance(client: TestClient) -> None:
    create(client)
    ov = client.get("/api/saves/dev/overview").json()
    assert ov["date_label"] == "Jan 2010"
    assert ov["cash_cents"] == GARAGE_CASH
    assert ov["monthly_burn_cents"] == 0
    assert ov["runway_months"] is None
    assert ov["history"] == []

    first = client.post("/api/saves/dev/advance").json()
    assert first["date_label"] == "Feb 2010"
    assert first["cash_cents"] == GARAGE_CASH - OVERHEAD
    assert first["monthly_burn_cents"] == OVERHEAD
    assert first["runway_months"] == 44  # $48,900 / $1,100

    second = client.post("/api/saves/dev/advance").json()
    assert second["date_label"] == "Mar 2010"
    assert second["turn"] == 2
    assert second["cash_cents"] == GARAGE_CASH - 2 * OVERHEAD
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


def _response_models() -> list[type[BaseModel]]:
    from tst.api.schemas import common, meta, saves

    models = []
    for module in (common, meta, saves):
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, BaseModel) and value is not BaseModel:
                models.append(value)
    return models


def test_no_hidden_fields_in_api_models() -> None:
    """ADR-0007: API models never carry true/hidden values."""
    assert schemas is not None
    forbidden = ("true_", "potential", "hidden", "master_seed")
    models = _response_models()
    assert models
    for model in models:
        for field in model.model_fields:
            assert not any(f in field for f in forbidden), f"{model.__name__}.{field}"


def test_openapi_declares_response_models(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    for path, ops in spec["paths"].items():
        for op in ops.values():
            assert "200" in op["responses"] or "201" in op["responses"], path
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
