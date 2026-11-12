"""M23a API: a contract's termination is quoted before confirming, then terminated at that fee;
the counterparty's relationship falls; suppliers carry their country."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.helpers import fund_save
from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings
from tst.db import repository
from tst.loader import LoadedData
from tst.sim.actions.commodities import SignCommodityContract

BASE = "/api/saves/c"


@pytest.fixture
def setup(tmp_path: Path, loaded: LoadedData) -> Iterator[tuple[Client, Path]]:
    saves = tmp_path / "saves"
    path = repository.create_save(
        "c", 3, "funded_spinout", company_name="Breaker", data=loaded, save_dir=saves
    )
    fund_save(path, 10**11)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as client:
        yield Client(client), path


def test_quote_then_terminate_a_commodity_contract(
    setup: tuple[Client, Path], loaded: LoadedData
) -> None:
    api, path = setup
    with repository.open_session(path) as session:
        state = repository.load_state(session)
    founder = state.founder_of(state.player.id)
    assert founder is not None
    repository.run_action(path, loaded, SignCommodityContract(founder.id, "copper", 12, 600.0))
    with repository.open_session(path) as session:
        deal = repository.load_state(session).commodity_deals[-1]
    q = api.get(f"{BASE}/contracts/commodity/{deal.id}/quote")
    assert q["months_left"] == 12 and q["fee_cents"] > 0 and q["relationship"] == 1.0
    assert q["fee_cents"] == q["discounted_cents"] + q["penalty_cents"]
    api.post(f"{BASE}/contracts/terminate", {"contract": "commodity", "contract_id": deal.id})
    with repository.open_session(path) as session:
        after = repository.load_state(session)
    assert not next(x for x in after.commodity_deals if x.id == deal.id).running(after.turn)
    assert any(r.counterparty == "traders:copper" and r.score < 1 for r in after.relations)
    api.get(f"{BASE}/contracts/commodity/{deal.id}/quote", status=400)  # nothing left to break


def test_suppliers_are_listed_with_their_country(setup: tuple[Client, Path]) -> None:
    api, _ = setup
    out = api.get(f"{BASE}/commodities")
    suppliers = {s["key"]: s for s in out.get("suppliers", [])}
    if "dowa" in suppliers:
        assert suppliers["dowa"]["country_label"] == "Japan"
