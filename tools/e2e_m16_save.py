"""Create saves for the M16 Playwright flows and tests (an e2e fixture tool). Never used by the
game.

- `eligible <save dir> <name>`: M13's listed Kestrel (tools/e2e_m13_save.py) that has kept two
  rival startups as brands through the real closing path (settle, then the brand closing):
  eligible to form a holding company (formulas.md 31.2).
- `formed <save dir> <name>`: the same with the holding company formed and a month played.

Usage: uv run --project backend python tools/e2e_m16_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import ledger_balances, load_state, open_session, run_action, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.group.holding import FormHolding
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, apply_entries
from tst.sim.mna import deals as mna_deals
from tst.sim.mna import integration
from tst.sim.mna.closing import settle
from tst.sim.mna.models import Deal
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_acquisition

FOUNDER = 1  # the founder's person id in every new save
BRANDS = 2
PREMIUM = 1.2  # a brand's price: its book equity x this (goodwill the rest)


def _state(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def _candidates(state: GameState, data: LoadedData) -> list[int]:
    """Rival startups still in business with no parent, smallest first by staff, then id."""
    alive = [
        c
        for c in state.rivals()
        if c.is_startup and c.parent_id is None and state.company_products(c.id)
    ]
    return [c.id for c in sorted(alive, key=lambda c: (len(state.staff(c.id)), c.id))]


def keep_brand(path: Path, data: LoadedData, target: int) -> None:
    """Buy `target` for cash at its book equity x PREMIUM and keep it as a brand, through
    the closing path (28.3, 28.5): the player's books post the price, 1810 and goodwill."""
    with open_session(path) as session, session.begin():
        before = load_state(session)
        balances = ledger_balances(session)
        book = sum(v for _, v in mna_deals.net_assets(balances, target, data.game_data))
        price = max(round(max(book, 0) * PREMIUM), 1_000_000_00)
        top_up = LedgerEntry.transfer(
            turn=before.turn,
            company_id=1,
            memo="E2E funding for an acquisition",
            debit=CASH,
            credit=COMMON_EQUITY,
            amount=price,
        )
        balances = apply_entries(balances, [top_up])
        deal_id, ids = before.next_ids.take("deal")
        deal = Deal(
            id=deal_id,
            acquirer_id=1,
            target_id=target,
            price_cents=price,
            cash_share=1.0,
            made_turn=before.turn,
            status="closed",
            resolved_turn=before.turn,
            mode="brand",
        )
        state, posted, acquisition = settle(
            replace(before, next_ids=ids), deal, (), balances, data.balance, data.game_data
        )
        state, acquisition, more, _ = integration.after_closing(
            state,
            acquisition,
            RngFactory(before.save_meta.master_seed),
            apply_entries(balances, posted),
            data.balance,
            data.game_data,
        )
        state = with_acquisition(state, acquisition)
        for entry in (top_up, *posted, *more):
            session.add(entry_to_row(entry))
        sync_state(session, before, state)


def eligible(save_dir: Path, name: str, data: LoadedData) -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from e2e_m13_save import eligible as listed_eligible
    from e2e_m13_save import play_chain

    path = listed_eligible(save_dir, name, data)
    play_chain(path, data)
    state = _state(path)
    for target in _candidates(state, data)[:BRANDS]:
        keep_brand(path, data, target)
    return path


def formed(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = eligible(save_dir, name, data)
    run_action(path, data, FormHolding(FOUNDER))
    run_turn(path, data)
    return path


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    modes = {"eligible": eligible, "formed": formed}
    if mode not in modes:
        print(__doc__)
        return 2
    path = modes[mode](save_dir, name, data)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
