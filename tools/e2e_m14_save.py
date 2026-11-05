"""Create saves for the M14 Playwright flows (an e2e fixture tool). Never used by the game.

- `startup <save dir> <name>`: Kestrel, a funded spinout with $50B in cash, played three
  months so Square (a named entrant, a startup) is in business. Prints Square's company id.
- `blocked <save dir> <name>`: the same with a live B2B SaaS product holding most of SMB,
  so a deal for Zoho crosses 50% combined share and is blocked unless a remedy is accepted.
  Prints Zoho's id.
- `exit <save dir> <name>`: M13's `listed` company (tools/e2e_m13_save.py) with a buyer's
  offer for it queued (formulas.md 28.6): answering "Accept and sell" ends the game.

Usage: uv run --project backend python tools/e2e_m14_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, load_state, open_session, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.markets_public import ipo
from tst.sim.markets_public.public import TAKEOVER_OFFER
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import with_product, with_product_segment

FUNDING_CENTS = 50_000_000_000_00  # $50B


def _company(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = create_save(
        name, 7, "funded_spinout", company_name="Kestrel", data=data, save_dir=save_dir
    )
    entry = LedgerEntry.transfer(
        turn=0,
        company_id=1,
        memo="Fixture funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=FUNDING_CENTS,
    )
    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))
    return path


def _id(path: Path, name: str) -> int:
    with open_session(path) as session:
        state = load_state(session)
    return next(c.id for c in state.companies if c.name == name)


def startup(save_dir: Path, name: str, data: LoadedData) -> tuple[Path, int]:
    path = _company(save_dir, name, data)
    for _ in range(3):
        run_turn(path, data)
    return path, _id(path, "Square")


def blocked(save_dir: Path, name: str, data: LoadedData) -> tuple[Path, int]:
    path = _company(save_dir, name, data)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        pid, ids = before.next_ids.take("product")
        product = Product(pid, 1, "b2b_saas", "Pipeline", "live", 55.0, 400.0, 30.0, 0, 0, 0)
        state = with_product(replace(before, next_ids=ids), product)
        state = with_product_segment(state, ProductSegment(pid, "smb", 4000, 10_000_000.0))
        sync_state(session, before, state)
    return path, _id(path, "Zoho")


def exit_offer(save_dir: Path, name: str, data: LoadedData) -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from e2e_m13_save import eligible, play_chain

    path = eligible(save_dir, name, data)
    play_chain(path, data)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = ipo.queue_public(before, 1, TAKEOVER_OFFER, before.turn + 1)
        sync_state(session, before, state)
    run_turn(path, data)  # the offer opens at the next month's start
    return path


def main(argv: list[str]) -> int:
    data = load_all(Settings().data_dir)
    if len(argv) == 3 and argv[0] in ("startup", "blocked"):
        path, target = (startup if argv[0] == "startup" else blocked)(Path(argv[1]), argv[2], data)
        print(f"{path}\ntarget={target}")
        return 0
    if len(argv) == 3 and argv[0] == "exit":
        print(exit_offer(Path(argv[1]), argv[2], data))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
