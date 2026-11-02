"""Create saves for the M10c Playwright flows (an e2e fixture tool). Never used by the game.

- `cro <save dir> <name>`: a funded spinout at stage 3 with 20 senior engineers and a senior
  account executive appointed CRO; a live B2B SaaS product ("Pipeline") selling to the
  mid-market, whose sales capacity limited new customers last month.
- `cfo <save dir> <name>`: a garage start with the same staff at stage 3 and no round raised
  yet, a senior finance manager appointed CFO, and cash for about three months: a CFO
  with authority proposes the seed.

Usage: uv run --project backend python tools/e2e_m10c_save.py cro <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from e2e_m8_save import FOUNDER, SEED, _create

from tst.balance.game import Game
from tst.balance.m8 import add_staff
from tst.config import Settings
from tst.db.repository import create_save, load_state, open_session, run_action
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import (
    AppointExecutive,
    AssignUnit,
    CreateProduct,
    LaunchProduct,
    SetPrice,
)
from tst.sim.state import reach_stage, with_company, with_product, with_product_segment

ENGINEERS = 20
PRICE_CENTS = 80_000  # $800 a month, mid-market
CUSTOMERS = 40.0
CFO_CASH_CENTS = 100_000_000  # $1M: about three months at this payroll, under the CFO's nine


def _staffed(path: Path, data: LoadedData, role: str) -> int:
    """Stage 3 with 20 senior engineers and one senior `role` (returned) to appoint."""
    with open_session(path) as session, session.begin():
        before = load_state(session)
        game = Game(data, before, {})
        add_staff(game, "software_engineer", "senior", ENGINEERS)
        (holder,) = add_staff(game, role, "senior", 1)
        state = with_company(game.state, reach_stage(game.state.player, 3, 0))
        sync_state(session, before, state)
    return holder


def cro(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data)
    holder = _staffed(path, data, "account_executive")
    run_action(path, data, AppointExecutive(FOUNDER, "cro", holder))
    with open_session(path) as session:
        product = load_state(session).next_ids.product
    run_action(path, data, CreateProduct(FOUNDER, "Pipeline", "b2b_saas", ("mid_market",)))
    run_action(path, data, SetPrice(FOUNDER, product, "mid_market", PRICE_CENTS))
    run_action(path, data, AssignUnit(FOUNDER, product, None))
    with open_session(path) as session, session.begin():
        before = load_state(session)
        ready = before.product(product)
        assert ready is not None
        sync_state(
            session, before, with_product(before, replace(ready, quality=60.0, feature_points=300))
        )
    run_action(path, data, LaunchProduct(FOUNDER, product))
    with open_session(path) as session, session.begin():
        before = load_state(session)
        (segment,) = before.segments_of(product)
        limited = replace(segment, customers=CUSTOMERS, capacity_limited=True)
        sync_state(session, before, with_product_segment(before, limited))
    return path


def cfo(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = create_save(
        name,
        SEED,
        "garage_bootstrap",
        company_name="Runway Co",
        data=data,
        save_dir=save_dir,
        mission=("ai", "enterprise"),
    )
    from tst.db.mappers import entry_to_row
    from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry

    with open_session(path) as session, session.begin():
        session.add(
            entry_to_row(
                LedgerEntry.transfer(
                    turn=0,
                    company_id=FOUNDER,
                    memo="Fixture funding",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=CFO_CASH_CENTS,
                )
            )
        )
    holder = _staffed(path, data, "finance_manager")
    run_action(path, data, AppointExecutive(FOUNDER, "cfo", holder))
    return path


def main(argv: list[str]) -> int:
    data = load_all(Settings().data_dir)
    if len(argv) == 3 and argv[0] in ("cro", "cfo"):
        make = cro if argv[0] == "cro" else cfo
        print(make(Path(argv[1]), argv[2], data))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
