"""Create and edit saves for the M12a Playwright flows (an e2e fixture tool). Never used by
the game.

- `product <save dir> <name>`: a funded spinout with $50M of extra cash and a live B2B SaaS
  product with 50,000 SMB customers (about 200 CU of compute).
- `ripen <save dir> <name>`: every data centre still building is moved to its last build
  month (capex all but paid), so it goes live at the next Continue.
- `cloud <save dir> <name>`: `product`, plus a live 2,000-CU general data centre in North
  America staffed by a unit of ten DevOps engineers.
- `brand <save dir> <name>`: the Cloud hosting product gets brand 60, as months of marketing
  would give it, so customers arrive within a Continue or two.
- `outage <save dir> <name>`: `product`, plus a live, unstaffed 500-CU data centre hosting it,
  and a scripted outage there this month: its critical event waits at the next Continue.

Usage: uv run --project backend python tools/e2e_m12a_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
from tst.balance import fixtures
from tst.config import Settings
from tst.db.repository import (
    create_save,
    existing_save_path,
    load_state,
    open_session,
    run_turn,
)
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import CreateUnit, apply_action
from tst.sim.facilities import compute
from tst.sim.facilities.models import Facility
from tst.sim.facilities.outages import apply_outages
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_employment,
    with_facility,
    with_person,
    with_person_state,
    with_product,
    with_product_segment,
)

SEED = 5
FOUNDER = 1
EXTRA_CASH = 50_000_000_00


def _product(state: GameState) -> GameState:
    pid, ids = state.next_ids.take("product")
    product = Product(
        id=pid,
        company_id=1,
        category="b2b_saas",
        name="Pipeline",
        status="live",
        quality=60.0,
        feature_points=200.0,
        brand=40.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    state = replace(with_product(state, product), next_ids=ids)
    return with_product_segment(state, ProductSegment(pid, "smb", 5000, 50_000.0, False, 0))


def _facility(state: GameState, data: LoadedData, units: int) -> GameState:
    kind = data.balance.facility.kinds["data_centre_general"]
    fid, ids = state.next_ids.take("facility")
    capex = units * kind.capex_per_unit_cents
    facility = Facility(
        id=fid,
        company_id=1,
        kind="data_centre_general",
        region="north_america",
        capacity=units,
        on_time=units,
        ordered_turn=state.turn - kind.build_months,
        ready_turn=state.turn,
        late_turn=state.turn,
        capex_cents=capex,
        input_index=1.0,
        capex_paid_cents=capex,
        status="live",
    )
    return with_facility(replace(state, next_ids=ids), facility)


def _staff(state: GameState, data: LoadedData, people: int) -> GameState:
    rng = RngFactory(SEED)
    out = apply_action(
        state, CreateUnit(FOUNDER, "team", "Ops"), rng, data.balance, data.game_data, {}, seq=1
    )
    state = out.new_state
    unit = max(u.id for u in state.units)
    role = data.game_data.role("devops_engineer")
    for i in range(people):
        pid, ids = state.next_ids.take("person")
        eid, ids = ids.take("employment")
        state = replace(state, next_ids=ids)
        gen: np.random.Generator = rng.stream(0, "misc", i)
        person = generate_person(
            gen,
            data.game_data,
            data.balance,
            state.turn,
            role,
            "senior",
            "north_america",
            person_id=pid,
        )
        state = with_person(state, person)
        state = with_employment(
            state,
            Employment(
                id=eid,
                person_id=pid,
                company_id=1,
                role="devops_engineer",
                level="senior",
                salary_cents=14_000_000,
                equity_bp=0,
                start_turn=state.turn,
                end_turn=None,
                status="active",
                unit_id=unit,
            ),
        )
        state = with_person_state(state, PersonState(person_id=pid, morale=65.0))
    facility = state.facilities[-1]
    return with_facility(state, replace(facility, unit_id=unit))


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
    _edit(path, _product)
    return path


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    if mode == "product":
        path = _create(save_dir, name, data)
    elif mode == "cloud":
        path = _create(save_dir, name, data)
        _edit(path, lambda s: _staff(_facility(s, data, 2000), data, 10))
    elif mode == "outage":
        path = _create(save_dir, name, data)
        _edit(path, lambda s: _facility(s, data, 500))

        def outage(s: GameState) -> GameState:
            out, _ = apply_outages(s, [s.facilities[-1].id], data.balance, data.game_data)
            return out

        _edit(path, outage)
        run_turn(path, data)  # the event director shows the queued outage event
    else:
        path = existing_save_path(save_dir, name)
        if mode == "ripen":

            def ripen(s: GameState) -> GameState:
                for f in s.facilities:
                    if f.status == "building":
                        k = data.balance.facility.kinds[f.kind]
                        moved = replace(
                            f,
                            ordered_turn=s.turn - k.build_months + 1,
                            ready_turn=s.turn + 1,
                            late_turn=s.turn + 1 + (f.late_turn - f.ready_turn),
                            capex_paid_cents=f.capex_cents * (k.build_months - 1) // k.build_months,
                        )
                        s = with_facility(s, moved)
                return s

            _edit(path, ripen)
        elif mode == "brand":

            def brand(s: GameState) -> GameState:
                cloud = compute.capacity_product(s, 1, data.game_data)
                assert cloud is not None
                return with_product(s, replace(cloud, brand=60.0))

            _edit(path, brand)
        else:
            print(__doc__)
            return 2
    fixtures.finish(path, data)  # M23c: a knowledge record of every hand-built employee
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
