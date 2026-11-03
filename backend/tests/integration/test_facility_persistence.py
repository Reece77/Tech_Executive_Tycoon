"""M12a persistence: facilities, goods' months, contracts and the Cloud hosting product
survive a save and reload; the cached state matches a fresh load (live_view)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import fund_save, play_turn
from tst.db.repository import create_save, open_session, run_action
from tst.db.state_io import live_view, load_state
from tst.loader import LoadedData
from tst.sim.actions import BuildFacility, SellCapacity, SellFacility, SignContract


def test_facilities_round_trip(
    tmp_path: Path, loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TST_STATE_CACHE_CHECK", "1")
    path = create_save(
        "fac", 4, "funded_spinout", company_name="Fac Co", data=loaded, save_dir=tmp_path
    )
    fund_save(path, 50_000_000_00)
    run_action(path, loaded, SignContract(1, "server", 12, 500))
    run_action(path, loaded, BuildFacility(1, "data_centre_general", "north_america", 100, 1))
    run_action(path, loaded, SellCapacity(1))
    for _ in range(3):
        play_turn(path, loaded)
    with open_session(path) as session:
        state = load_state(session)
    assert live_view(state) == state
    (facility,) = state.facilities
    assert facility.capex_paid_cents == 3 * facility.capex_cents // 12
    (contract,) = state.contracts
    assert contract.used == 100
    assert {g.good for g in state.supply} == {
        "server",
        "gpu",
        "device_bom",  # M12b (26.2, 26.3)
        "server_bom",
        "equipment",
        "foundry_wafer",
    }
    assert all(g.turn == 2 for g in state.supply)
    cloud = [p for p in state.products if p.category == "cloud_hosting" and p.company_id == 1]
    assert len(cloud) == 1
    run_action(path, loaded, SellFacility(1, facility.id))
    with open_session(path) as session:
        state = load_state(session)
    assert state.facilities == ()
    play_turn(path, loaded)
