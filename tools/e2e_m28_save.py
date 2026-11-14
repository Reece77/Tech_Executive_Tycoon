"""Create saves for the M28 Playwright flows and the practice save (an e2e fixture tool). Never
used by the game.

- `world <save dir> <name>` (the practice save `pt-world`): Cathode, a listed integrator in
  January 2027: M13's listed scale-up moved to 2026 and played through 2026 in the living
  world, then given a lithium converter in Latin America (built, staffed, past its ramp), a
  5-year lithium carbonate offtake with Albemarle, and a share price at about 55% of its value
  (trading cheaply). Its Commodities tab links the offtake to Albemarle's company page; World
  news has a year of the world's moves.
- `bid <save dir> <name>`: `world`, moved to the first month in which a rival's own valuation
  makes it bid for the cheap listed group (41.4): the next Continue brings the takeover bid as a
  critical event.

The year in memory is played with the engine (tst.balance.game); the ledger is written as one
entry per company netting what that year posted (every entry balances, so each net does too).

Usage: uv run --project backend python tools/e2e_m28_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final

from tst.balance import fixtures, m13, m20
from tst.balance.game import Game, start_game
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, ledger_balances, load_state, open_session
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import HireBanks, SignOfftake
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import COMMON_EQUITY, LedgerEntry, LedgerLine, apply_entries
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, listed_id, public_of, with_public
from tst.sim.world import bids
from tst.sim.world.setup import materialise

SEED: Final = 28
COMPANY: Final = "Cathode"
WORLD_FROM: Final = ym_to_turn(2026, 1)
CONVERTER_T: Final = 25_000  # tonnes of lithium carbonate a year (a recipe size)
EXTRA_CASH: Final = 200_000_000_000  # $2B of funding for the plant (equity)
OFFTAKE_T: Final = 8_000.0
CHEAP: Final = 0.55  # share price / value a share
BID_SEARCH: Final = 48  # months searched for a bid


def _listed_game(data: LoadedData) -> Game:
    """M13's listed scale-up (Kestrel's numbers), in memory, listed by the engine."""
    game = start_game(data, SEED, "funded_spinout")
    game.state = replace(game.state, companies=tuple(
        replace(c, name=COMPANY) if c.is_player else c for c in game.state.companies
    ))  # fmt: skip
    m13.scaleup(game)
    game.act(HireBanks(game.founder_id, m13.BANK))
    for _ in range(12):
        game.turn()
        if public_of(game.state, 1) is not None:
            break
    if public_of(game.state, 1) is None:
        raise RuntimeError("the IPO did not list")
    return game


def _into_the_world(game: Game) -> None:
    """Move the listed company to January 2026 and play 2026 in the living world."""
    b, d = game.loaded.balance, game.loaded.game_data
    game.state = replace(game.state, turn=WORLD_FROM)
    state, opening = materialise(game.state, RngFactory(SEED), b, d)
    game.state = state
    game.balances = dict(apply_entries(game.balances, opening))
    for _ in range(12):
        game.turn()


def _integrator(game: Game) -> None:
    """A lithium converter in Latin America (past its ramp) and an offtake with Albemarle."""
    from tst.sim.state import with_person_state

    cash = (1, "1000_cash")
    game.balances = {**game.balances, cash: game.balances.get(cash, 0) + EXTRA_CASH}
    fid = m20.build(game, "li_converter", "latin_america", CONVERTER_T)
    plant = game.state.facility(fid)
    assert plant is not None
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))
    if not game.act(SignOfftake(game.founder_id, "lithium_carbonate", "albemarle", 5, OFFTAKE_T)):
        raise RuntimeError(f"the offtake was refused: {dict(game.refused)}")


def _cheap(state: GameState) -> GameState:
    lid = listed_id(state)
    public = public_of(state, lid)
    assert public is not None
    return with_public(state, replace(public, sentiment=CHEAP, price_cents=round(
        public.price_cents * CHEAP / max(public.sentiment, 1e-9)
    )))  # fmt: skip


def _bid_month(game: Game) -> int:
    """The first month from now in which a rival bids (41.4): the draws are the world's."""
    b = game.loaded.balance
    rng = RngFactory(SEED)
    for t in range(game.state.turn, game.state.turn + BID_SEARCH):
        state = replace(game.state, turn=t)
        probe, _ = bids.bids_month(state, rng, b, game.loaded.game_data, game.balances)
        if probe.world_bids != state.world_bids:
            return t
    raise RuntimeError("no rival bids within the search")


def build(data: LoadedData, *, bid: bool) -> Game:
    game = _listed_game(data)
    _into_the_world(game)
    _integrator(game)
    game.state = _cheap(game.state)
    if bid:
        game.state = replace(game.state, turn=_bid_month(game))
    return game


def _write(path: Path, game: Game, start: Mapping[tuple[int, str], int]) -> None:
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, game.state)
        read_meta(session).current_turn = game.state.turn
        by_company: dict[int, list[LedgerLine]] = {}
        for (cid, account), amount in game.balances.items():
            diff = amount - start.get((cid, account), 0)
            if diff:
                by_company.setdefault(cid, []).append(LedgerLine(account, diff))
        for (cid, account), amount in start.items():
            if (cid, account) not in game.balances and amount:
                by_company.setdefault(cid, []).append(LedgerLine(account, -amount))
        for cid, lines in sorted(by_company.items()):
            gap = sum(x.amount for x in lines)  # the scale-up's cash set directly (M13's helper)
            if gap:
                lines.append(LedgerLine(COMMON_EQUITY, -gap))
            if len(lines) >= 2:
                entry = LedgerEntry(
                    game.state.turn - 1, cid, "E2E: the fixture's months", tuple(lines)
                )
                session.add(entry_to_row(entry))


def make(save_dir: Path, name: str, data: LoadedData, *, bid: bool) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = build(data, bid=bid)
    _write(path, game, start)
    return path


MODES = {"world": False, "bid": True}


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in MODES:
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    path = make(Path(argv[2]), argv[3], data, bid=MODES[argv[1]])
    # M23c: a believable stage-3 team and a knowledge record of every employee (playtest 5)
    fixtures.finish(
        path,
        data,
        team=True,
        stage=3,
        specialists=(("process_engineer", 2, "Plants"), ("operations_manager", 1, "Supply")),
    )
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
