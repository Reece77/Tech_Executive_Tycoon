"""Create saves for the M17 Playwright flows (an e2e fixture tool). Never used by the game.

- `y2023 <save dir> <name>`: a funded spinout in June 2023 (inside history, so no stored
  commodity months are needed).
- `device2020 <save dir> <name>`: a funded spinout in February 2020 with $50M of extra cash and a
  live device on a 20,000-unit Foxconn contract that sold 10,000 units last month.
- `power <save dir> <name>`: a funded spinout in June 2023 with two live 100-CU GPU data
  centres, one in North America and one in South and Southeast Asia.

Usage: uv run --project backend python tools/e2e_m17_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, load_state, open_session
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.hardware.models import ProductionContract, ProductionMonth
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.products.formulas import expected_features
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import (
    GameState,
    with_company,
    with_facility,
    with_product,
    with_product_segment,
    with_production_contract,
)

SEED = 5
EXTRA_CASH = 50_000_000_00
UNITS = 10_000


def _create(save_dir: Path, name: str, data: LoadedData, turn: int) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name="Kestrel", data=data, save_dir=save_dir
    )
    entry = LedgerEntry.transfer(
        turn=0,
        company_id=1,
        memo="E2E funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=EXTRA_CASH,
    )
    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))
        before = load_state(session)
        sync_state(session, before, replace(before, turn=turn))
        read_meta(session).current_turn = turn
    return path


def _edit(path: Path, change) -> None:  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, change(before))


def _device(state: GameState, data: LoadedData) -> GameState:
    pid, ids = state.next_ids.take("product")
    cat = data.game_data.category("devices")
    product = Product(
        id=pid,
        company_id=1,
        category="devices",
        name="Pebble Phone",
        status="live",
        quality=55.0,
        feature_points=expected_features(cat, state.turn) * 0.8,
        brand=30.0,
        marketing_budget_cents=0,
        created_turn=state.turn - 6,
        launched_turn=state.turn - 1,
    )
    state = replace(with_product(state, product), next_ids=ids)
    state = with_product_segment(state, ProductSegment(pid, "consumer", 32_000, 0.0, False, 0))
    state = with_company(state, replace(state.player, root_product_id=pid))
    cid, ids = state.next_ids.take("production_contract")
    contract = ProductionContract(
        id=cid,
        company_id=1,
        product_id=pid,
        kind="assembly",
        supplier="foxconn",
        units=20_000,
        price_millicents=1_300_000,
        signed_turn=state.turn - 1,
        end_turn=state.turn + 23,
        city="shenzhen",
    )
    state = with_production_contract(replace(state, next_ids=ids), contract)
    row = ProductionMonth(state.turn - 1, pid, 1, capacity=20_000, units=UNITS)
    return replace(state, production=(row,))


def _data_centres(state: GameState, data: LoadedData) -> GameState:
    kind = data.balance.facility.kinds["data_centre_gpu"]
    for region in ("north_america", "south_southeast_asia"):
        fid, ids = state.next_ids.take("facility")
        capex = 100 * kind.capex_per_unit_cents
        facility = Facility(
            id=fid,
            company_id=1,
            kind="data_centre_gpu",
            region=region,
            capacity=100,
            on_time=100,
            ordered_turn=state.turn - kind.build_months,
            ready_turn=state.turn - 1,
            late_turn=state.turn - 1,
            capex_cents=capex,
            input_index=1.0,
            capex_paid_cents=capex,
            status="live",
        )
        state = with_facility(replace(state, next_ids=ids), facility)
    return state


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    if mode == "y2023":
        _create(save_dir, name, data, ym_to_turn(2023, 6))
    elif mode == "device2020":
        path = _create(save_dir, name, data, ym_to_turn(2020, 2))
        _edit(path, lambda s: _device(s, data))
    elif mode == "power":
        path = _create(save_dir, name, data, ym_to_turn(2023, 6))
        _edit(path, lambda s: _data_centres(s, data))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
