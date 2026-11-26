"""Create and edit saves for the M54 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

- `bank <save dir> <name>` (the practice save `pt-bank`): Fin, a stage-4 fintech group in January
  2019 (2010-2018 played by the engine, the player's company doing nothing, so the world and its
  banks are the engine's): a live fintech line and a live banking line priced at its reference
  fees but with no accounts yet (no charter or partner bank), $20B of extra funding (cash for a
  charter) and a team.
- `rates <save dir> <name>`: the same group with a chartered North American bank at a deposit beta
  of 0.9 and 300,000 consumer and 20,000 business accounts, its bank built from January 2020 and
  played to January 2022, just before the policy rate's rise.
- `currency <save dir> <name>`: the same group in January 2024 with a software line selling in
  North America and Europe (half its revenue in Europe), one month played so its foreign revenue
  is recorded.
- `advance <save dir> <name> <months>`: plays the save's next months with the engine, answering
  open critical events with their first choice.

Usage: uv run --project backend python tools/e2e_m54_save.py <mode> <save dir> <name> [months]
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

import e2e_m38_save as m38
from tst.balance import fixtures
from tst.balance.game import Game
from tst.config import Settings
from tst.db.repository import create_save, ledger_balances, open_session
from tst.loader import LoadedData, load_all
from tst.sim.finserv.models import Bank
from tst.sim.geo.models import RegionalSegment
from tst.sim.products.models import ProductSegment

SEED: Final = 54
COMPANY: Final = "Fin"
STAGE: Final = 4
YEARS: Final = {"bank": 2019, "rates": 2020, "currency": 2024}
REGION: Final = "north_america"
RESERVES: Final = "1060_bank_reserves"
CASH: Final = "1000_cash"
BANK_CAPITAL: Final = 60_000_000_000  # $600M: about 9% of the bank's first year's deposits


def _segments(
    game: Game, pid: int, home: dict[str, tuple[int, float]], away: dict[str, tuple[int, float]]
) -> None:
    s = game.state
    rows = tuple(x for x in s.product_segments if x.product_id != pid)
    new = tuple(ProductSegment(pid, seg, price, n) for seg, (price, n) in home.items())
    regional = tuple(x for x in s.regional_segments if x.product_id != pid)
    abroad = tuple(
        RegionalSegment(pid, "europe", seg, price, n) for seg, (price, n) in away.items()
    )
    game.state = replace(
        s,
        product_segments=tuple(sorted((*rows, *new), key=lambda x: (x.product_id, x.segment))),
        regional_segments=tuple(
            sorted((*regional, *abroad), key=lambda x: (x.product_id, x.region, x.segment))
        ),
    )


def _state(mode: str, data: LoadedData) -> Game:
    m38.SEED, m38.COMPANY, m38.STAGE = SEED, COMPANY, STAGE  # m38's helpers read these
    game = m38._played(data, YEARS[mode])
    fintech = m38._product(game, "Fin Pay", "fintech", 6_000)
    _segments(game, fintech, {"smb": (6_000, 0.0)}, {})
    m38._launch(game, fintech)
    if mode == "currency":
        cloud = m38._product(game, "Fin Cloud", "b2b_saas", 5_000)
        _segments(game, cloud, {"smb": (5_000, 4_000.0)}, {"smb": (5_000, 4_000.0)})
        m38._launch(game, cloud)
        game.turn()
        return game
    bank_line = m38._product(game, "Fin Bank", data.balance.finserv.banking_category, 800)
    accounts = (300_000.0, 20_000.0) if mode == "rates" else (0.0, 0.0)
    _segments(
        game,
        bank_line,
        {"bank_consumer": (800, accounts[0]), "bank_business": (6_000, accounts[1])},
        {},
    )
    m38._launch(game, bank_line)
    if mode == "bank":
        return game
    player = game.state.player.id
    bank = Bank(
        id=1,
        company_id=player,
        region=REGION,
        status="chartered",
        applied_turn=game.state.turn,
        charter_turn=game.state.turn,
        beta=0.9,
        reserves_cents=BANK_CAPITAL,
        capital_in_cents=BANK_CAPITAL,
    )
    game.state = replace(game.state, finserv=replace(game.state.finserv, banks=(bank,)))
    game.balances = {
        **game.balances,
        (player, RESERVES): game.balances.get((player, RESERVES), 0) + BANK_CAPITAL,
        (player, CASH): game.balances[(player, CASH)] - BANK_CAPITAL,
    }
    for _ in range(24):
        game.turn()
    return game


def make(save_dir: Path, name: str, data: LoadedData, mode: str) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = _state(mode, data)
    m38._write(path, game.state, game.balances, start)
    fixtures.finish(path, data, team=True, stage=STAGE)
    return path


def main(argv: list[str]) -> int:
    modes = ("bank", "rates", "currency", "advance")
    if len(argv) < 4 or argv[1] not in modes or (argv[1] == "advance") != (len(argv) == 5):
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    if argv[1] == "advance":
        m38.advance(Path(argv[2]), argv[3], data, int(argv[4]))
        return 0
    print(make(Path(argv[2]), argv[3], data, argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
