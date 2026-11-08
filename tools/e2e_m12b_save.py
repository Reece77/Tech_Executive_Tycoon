"""Create and edit saves for the M12b Playwright flows (an e2e fixture tool). Never used by
the game.

- `device <save dir> <name>`: a funded spinout with $50M of extra cash and a device in
  development, ready to launch but for a manufacturing source (quality 45, feature score 60,
  priced at $320 to consumers).
- `live_device <save dir> <name>`: `device`, launched, on a 20,000-unit Foxconn contract in
  Shenzhen signed this month.
- `plant_ready <save dir> <name>`: every assembly plant still building goes live now, staffed
  by a new unit of 20 senior manufacturing engineers.
- `chip <save dir> <name>`: a funded spinout with an AI accelerator in development, ready to
  launch but for a wafer contract.

Usage: uv run --project backend python tools/e2e_m12b_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.config import Settings
from tst.db.repository import create_save, existing_save_path, load_state, open_session
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import CreateUnit, apply_action
from tst.sim.hardware.models import ProductionContract
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.products.formulas import expected_features
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_company,
    with_employment,
    with_facility,
    with_person,
    with_person_state,
    with_product,
    with_product_segment,
    with_production_contract,
)

SEED = 5
FOUNDER = 1
EXTRA_CASH = 50_000_000_00


def _product(
    state: GameState, data: LoadedData, category: str, segment: str, price: int, name: str
) -> GameState:
    pid, ids = state.next_ids.take("product")
    cat = data.game_data.category(category)
    product = Product(
        id=pid,
        company_id=1,
        category=category,
        name=name,
        status="in_development",
        quality=45.0,
        feature_points=expected_features(cat, state.turn) * 0.6,
        brand=30.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
    )
    state = replace(with_product(state, product), next_ids=ids)
    state = with_product_segment(state, ProductSegment(pid, segment, price, 0.0, False, 0))
    return with_company(state, replace(state.player, root_product_id=pid))


def _edit(path: Path, change) -> None:  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, change(before))


def _create(save_dir: Path, name: str, data: LoadedData) -> Path:
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
    from tst.db.mappers import entry_to_row

    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))
    return path


def _launch_with_contract(state: GameState) -> GameState:
    product = next(p for p in state.products if p.company_id == 1 and p.category == "devices")
    state = with_product(state, replace(product, status="live", launched_turn=state.turn))
    cid, ids = state.next_ids.take("production_contract")
    contract = ProductionContract(
        id=cid,
        company_id=1,
        product_id=product.id,
        kind="assembly",
        supplier="foxconn",
        units=20_000,
        price_millicents=1_300_000,
        signed_turn=state.turn,
        end_turn=state.turn + 23,
        city="shenzhen",
    )
    return with_production_contract(replace(state, next_ids=ids), contract)


def _plants_ready(state: GameState, data: LoadedData) -> GameState:
    rng = RngFactory(SEED)
    out = apply_action(
        state, CreateUnit(FOUNDER, "team", "Line"), rng, data.balance, data.game_data, {}, seq=1
    )
    state = out.new_state
    unit = max(u.id for u in state.units)
    role = data.game_data.role("manufacturing_engineer")
    for i in range(20):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        person = generate_person(
            rng.stream(0, "misc", 200 + i),
            data.game_data,
            data.balance,
            state.turn,
            role,
            "senior",
            "east_asia",
            person_id=pid,
        )
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=eid,
                person_id=pid,
                company_id=1,
                role="manufacturing_engineer",
                level="senior",
                salary_cents=9_000_000,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
                unit_id=unit,
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    for f in state.facilities:
        if f.kind == data.balance.hardware.plant_kind and f.status == "building":
            state = with_facility(
                state,
                replace(
                    f,
                    ordered_turn=state.turn - 12,
                    ready_turn=state.turn,
                    late_turn=state.turn,
                    capex_paid_cents=f.capex_cents,
                    status="live",
                    unit_id=unit,
                ),
            )
    return state


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    if mode in ("device", "live_device"):
        path = _create(save_dir, name, data)
        _edit(path, lambda s: _product(s, data, "devices", "consumer", 32_000, "Pebble Phone"))
        if mode == "live_device":
            _edit(path, _launch_with_contract)
    elif mode == "chip":
        path = _create(save_dir, name, data)
        _edit(
            path,
            lambda s: _product(
                s, data, "chips_ai_accelerator", "hyperscalers", 150_000, "Kestrel TPU"
            ),
        )
    elif mode == "plant_ready":
        path = existing_save_path(save_dir, name)
        _edit(path, lambda s: _plants_ready(s, data))
    else:
        print(__doc__)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
