"""Create saves for the M8 Playwright flows (an e2e fixture tool). Never used by the game.

- `stage3 <save dir> <name>`: a funded spinout at stage 3 with 20 senior engineers, a finance
  manager and an "Eng" department, plus a Fintech product ("Ledger") developed far enough to
  launch. Reaching $20M ARR on screen takes years; the flows are not about that.
- `advance <save dir> <name> <turns>`: a new funded spinout played headless for <turns>
  months (Stripe is founded in September 2011, turn 20).

Usage: uv run --project backend python tools/e2e_m8_save.py stage3 <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.balance.game import Game
from tst.balance.m8 import add_staff
from tst.config import Settings
from tst.db.repository import create_save, load_state, open_session, run_action, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import AssignUnit, ChooseEvent, CreateProduct, CreateUnit, SetPrice
from tst.sim.state import reach_stage, with_company, with_product

SEED = 21
FOUNDER = 1
ENGINEERS = 20
FUNDING_CENTS = 5_000_000_000  # $50M: the flows are not about solvency


def _create(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = create_save(
        name,
        SEED,
        "funded_spinout",
        company_name="Scale Co",
        data=data,
        save_dir=save_dir,
        mission=("ai", "enterprise"),
    )
    from tst.db.mappers import entry_to_row
    from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry

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
    return path


def stage3(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        game = Game(data, before, {})
        add_staff(game, "software_engineer", "senior", ENGINEERS)
        add_staff(game, "finance_manager", "senior", 1)
        state = with_company(game.state, reach_stage(game.state.player, 3, 0))
        sync_state(session, before, state)
    run_action(path, data, CreateUnit(FOUNDER, "department", "Eng"))
    with open_session(path) as session:
        product = load_state(session).next_ids.product
    run_action(path, data, CreateProduct(FOUNDER, "Ledger", "fintech", ("smb",)))
    run_action(path, data, SetPrice(FOUNDER, product, "smb", 6000))
    run_action(path, data, AssignUnit(FOUNDER, product, None))
    with open_session(path) as session, session.begin():
        before = load_state(session)
        ledger = before.product(product)
        assert ledger is not None
        ready = replace(ledger, quality=40.0, feature_points=200.0)
        sync_state(session, before, with_product(before, ready))
    return path


def advance(save_dir: Path, name: str, turns: int, data: LoadedData) -> Path:
    path = _create(save_dir, name, data)
    for _ in range(turns):
        with open_session(path) as session:
            state = load_state(session)
        for event in state.open_events(FOUNDER):
            if event.severity == "critical" and event.status == "open":
                run_action(path, data, ChooseEvent(FOUNDER, event.id, event.choices[0].key))
        run_turn(path, data)
    return path


def main(argv: list[str]) -> int:
    data = load_all(Settings().data_dir)
    if len(argv) == 3 and argv[0] == "stage3":
        print(stage3(Path(argv[1]), argv[2], data))
        return 0
    if len(argv) == 4 and argv[0] == "advance":
        print(advance(Path(argv[1]), argv[2], int(argv[3]), data))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
