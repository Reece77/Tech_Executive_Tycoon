"""Create saves for the M47 Playwright flows and the practice save (an e2e fixture tool). Never used
by the game.

- `negotiate <save dir> <name>` (the practice save `pt-negotiate`): Parley, a stage-4 company in
  January 2018 (2010-2017 played by the engine, the player's company doing nothing, so the world
  is the engine's) with $20B of extra funding and a stage-4 team, and three deals on the table:
  an acquisition target (the smallest private company in business), a key hire's counter-offer
  (a senior engineer a rival has just approached at 30% over their salary) and a supplier
  contract renewing (a 12-month lithium carbonate contract with the traders, ending in two
  months). Prints the target's company id, the approached person's id and the contract's good.
- `fresh <save dir> <name>`: the flows' quick save: Parley, a funded spinout in January 2010
  with $50B, and at least four private companies to buy. Prints the private companies' ids,
  smallest first, as JSON.

Usage: uv run --project backend python tools/e2e_m47_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

import e2e_m38_save as m38
from tst.balance import fixtures
from tst.balance.game import Game, start_game
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, ledger_balances, load_state, open_session
from tst.loader import LoadedData, load_all
from tst.sim.actions.commodities import SignCommodityContract
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.mna import valuation
from tst.sim.rivals.models import PoachApproach
from tst.sim.state import GameState, with_company

SEED: Final = 47
COMPANY: Final = "Parley"
EXTRA_CASH: Final = 20_000_000_000_00
FRESH_CASH: Final = 50_000_000_000_00
STAGE: Final = 4
YEAR: Final = 2018
GOOD: Final = "lithium_carbonate"
CONTRACT_MONTHS: Final = 12
CONTRACT_VOLUME: Final = 100.0
ENDS_IN: Final = 2  # months the renewing contract still runs
KEY_SALARY: Final = 18_000_000
POACH_PREMIUM: Final = 1.3


def private_targets(state: GameState, data: LoadedData) -> list[int]:
    """Private companies in business that a player may buy, smallest staff first."""
    out = [
        c
        for c in state.rivals()
        if c.alive
        and c.parent_id is None
        and not valuation.is_listed(state, c.id, data.game_data)
    ]
    return [c.id for c in sorted(out, key=lambda c: (len(state.staff(c.id)), c.id))]


def _played(data: LoadedData) -> Game:
    game = start_game(data, SEED, "funded_spinout")
    game.state = replace(game.state, companies=tuple(
        replace(c, name=COMPANY) if c.is_player else c for c in game.state.companies
    ))  # fmt: skip
    while game.state.turn < ym_to_turn(YEAR, 1):
        game.turn()
    cash = (game.state.player.id, CASH)
    game.balances = {**game.balances, cash: game.balances.get(cash, 0) + EXTRA_CASH}
    game.state = with_company(game.state, replace(game.state.player, stage=STAGE))
    return game


def _deals(game: Game, data: LoadedData) -> tuple[int, int]:
    """The key person and their rival's approach; the supplier contract ending soon."""
    s = game.state
    s, (key,) = fixtures.hire(s, data, "software_engineer", "senior", 1, "Core", KEY_SALARY, 47)
    rival = next(c for c in s.rivals() if c.alive and c.failed_turn is None)
    aid = max((a.id for a in s.approaches), default=0) + 1
    offer = round(KEY_SALARY * POACH_PREMIUM)
    s = replace(s, approaches=(*s.approaches, PoachApproach(aid, rival.id, key, offer, s.turn)))
    game.state = s
    m38._energise(game)
    signed = SignCommodityContract(game.founder_id, GOOD, CONTRACT_MONTHS, CONTRACT_VOLUME)
    assert game.act(signed), game.refused
    deal = game.state.commodity_deals[-1]
    start = game.state.turn - (CONTRACT_MONTHS - ENDS_IN)
    deal = replace(deal, signed_turn=start, end_turn=start + CONTRACT_MONTHS - 1)
    game.state = replace(
        game.state,
        commodity_deals=tuple(
            deal if d.id == deal.id else d for d in game.state.commodity_deals
        ),
    )
    m38._energise(game)
    return key, private_targets(game.state, data)[0]


def negotiate(save_dir: Path, name: str, data: LoadedData) -> str:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = _played(data)
    key, target = _deals(game, data)
    m38._write(path, game.state, game.balances, start)
    fixtures.finish(path, data, team=True, stage=STAGE)
    return json.dumps({"target_id": target, "person_id": key, "good": GOOD})


def fresh(save_dir: Path, name: str, data: LoadedData) -> str:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    entry = LedgerEntry.transfer(
        turn=0,
        company_id=1,
        memo="Fixture funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=FRESH_CASH,
    )
    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))
    with open_session(path) as session:
        state = load_state(session)
    return json.dumps(private_targets(state, data))


def main(argv: list[str]) -> int:
    modes = {"negotiate": negotiate, "fresh": fresh}
    if len(argv) != 4 or argv[1] not in modes:
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    print(modes[argv[1]](Path(argv[2]), argv[3], data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
