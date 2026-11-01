"""Create a save for the M9 Playwright flows (an e2e fixture tool). Never used by the game.

`geo <save dir> <name>`: a funded spinout with four senior engineers in a "Platform" team
and a live B2B SaaS product ("Pipeline", SMB at $40) built by the company root.

Usage: uv run --project backend python tools/e2e_m9_save.py geo <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.balance.game import Game
from tst.balance.m8 import add_staff
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, load_state, open_session, run_action
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import AssignUnit, CreateProduct, CreateUnit, LaunchProduct, MovePerson
from tst.sim.actions import SetPrice
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.state import with_person_state, with_product

SEED = 23
FOUNDER = 1
ENGINEERS = 4
FUNDING_CENTS = 2_000_000_000  # $20M: the flows are not about solvency


def geo(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name="Geo Co", data=data, save_dir=save_dir
    )
    entry = LedgerEntry.transfer(
        turn=0,
        company_id=FOUNDER,
        memo="Fixture funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=FUNDING_CENTS,
    )
    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))
        before = load_state(session)
        game = Game(data, before, {})
        engineers = add_staff(game, "software_engineer", "senior", ENGINEERS)
        sync_state(session, before, game.state)
    run_action(path, data, CreateUnit(FOUNDER, "team", "Platform"))
    for pid in engineers:
        run_action(path, data, MovePerson(FOUNDER, pid, 1))
    with open_session(path) as session:
        product = load_state(session).next_ids.product
    run_action(path, data, CreateProduct(FOUNDER, "Pipeline", "b2b_saas", ("smb",)))
    run_action(path, data, SetPrice(FOUNDER, product, "smb", 4000))
    run_action(path, data, AssignUnit(FOUNDER, product, None))
    with open_session(path) as session, session.begin():
        before = load_state(session)
        pipeline = before.product(product)
        assert pipeline is not None
        ready = with_product(before, replace(pipeline, quality=50.0, feature_points=200.0))
        founder = ready.person_state(FOUNDER)
        ready = with_person_state(ready, replace(founder, energy=60))  # a fresh month's energy
        sync_state(session, before, ready)
    run_action(path, data, LaunchProduct(FOUNDER, product))
    with open_session(path) as session, session.begin():
        before = load_state(session)
        founder = before.person_state(FOUNDER)
        sync_state(session, before, with_person_state(before, replace(founder, energy=60)))
    return path


def main(argv: list[str]) -> int:
    data = load_all(Settings().data_dir)
    if len(argv) == 3 and argv[0] == "geo":
        print(geo(Path(argv[1]), argv[2], data))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
