"""Create saves for the M25 Playwright flows (an e2e fixture tool). Never used by the game.

- `ready <save dir> <name>`: a funded spinout with four senior engineers and a B2B SaaS
  product ("Pipeline", SMB at $40) ready to launch, and a fresh profile (the profile file is
  removed, so the flow's first launch earns its achievement whatever earlier flows did).
- `live <save dir> <name>`: `ready`, launched and played four months with every event
  answered by its first choice, so the product has churn to explain.

Usage: uv run --project backend python tools/e2e_m25_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.balance.game import Game
from tst.balance.m8 import add_staff
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, load_state, open_session, run_action, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.profile.store import profile_path
from tst.sim.actions import AssignUnit, CreateProduct, LaunchProduct, SetPrice
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.state import with_person_state, with_product

SEED = 25
FOUNDER = 1
ENGINEERS = 4
FUNDING_CENTS = 2_000_000_000  # $20M: the flows are not about solvency
MONTHS = 4


def _fresh_energy(path: Path) -> None:
    with open_session(path) as session, session.begin():
        before = load_state(session)
        founder = before.person_state(FOUNDER)
        sync_state(session, before, with_person_state(before, replace(founder, energy=60)))


def ready(save_dir: Path, name: str, data: LoadedData) -> tuple[Path, int]:
    path = create_save(
        name, SEED, "funded_spinout", company_name="Explain Co", data=data, save_dir=save_dir
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
        add_staff(game, "software_engineer", "senior", ENGINEERS)
        sync_state(session, before, game.state)
    with open_session(path) as session:
        product = load_state(session).next_ids.product
    run_action(path, data, CreateProduct(FOUNDER, "Pipeline", "b2b_saas", ("smb",)))
    run_action(path, data, SetPrice(FOUNDER, product, "smb", 4000))
    run_action(path, data, AssignUnit(FOUNDER, product, None))
    with open_session(path) as session, session.begin():
        before = load_state(session)
        pipeline = before.product(product)
        assert pipeline is not None
        sync_state(
            session,
            before,
            with_product(before, replace(pipeline, quality=50.0, feature_points=200.0)),
        )
    _fresh_energy(path)
    profile_path(save_dir).unlink(missing_ok=True)
    return path, product


def live(save_dir: Path, name: str, data: LoadedData) -> Path:
    path, product = ready(save_dir, name, data)
    run_action(path, data, LaunchProduct(FOUNDER, product))
    for _ in range(MONTHS):
        run_turn(path, data)  # open events resolve to their first choice (23.1)
    _fresh_energy(path)
    return path


def main(argv: list[str]) -> int:
    data = load_all(Settings().data_dir)
    if len(argv) == 3 and argv[0] in ("ready", "live"):
        save_dir, name = Path(argv[1]), argv[2]
        print(ready(save_dir, name, data)[0] if argv[0] == "ready" else live(save_dir, name, data))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
