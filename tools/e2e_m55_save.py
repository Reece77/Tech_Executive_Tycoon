"""Create and edit saves for the M55 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

- `media <save dir> <name>` (the practice save `pt-media`): Reel, a stage-3 consumer-apps group in
  January 2016 (2010-2015 played by the engine, the player's company doing nothing, so the world
  and its media rivals are the engine's): a live consumer app, $20B of extra funding (cash for a
  studio) and a team. No media line or title yet; creative leads are on offer.
- `stream <save dir> <name>`: the same group in January 2023 (ad tiers open) with a live video
  service (Reel Stream, priced at the market's reference) and no ad tier yet.
- `advance <save dir> <name> <months>`: plays the save's next months with the engine, answering
  open critical events with their first choice.

Usage: uv run --project backend python tools/e2e_m55_save.py <mode> <save dir> <name> [months]
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
from tst.sim.products.models import ProductSegment

SEED: Final = 55
COMPANY: Final = "Reel"
STAGE: Final = 3
YEARS: Final = {"media": 2016, "stream": 2023}
APP_PRICE: Final = 40  # cents a user a month (consumer apps' reference)


def _state(mode: str, data: LoadedData) -> Game:
    m38.SEED, m38.COMPANY, m38.STAGE = SEED, COMPANY, STAGE  # m38's helpers read these
    game = m38._played(data, YEARS[mode])
    app = m38._product(game, "Reel Moments", "consumer_apps", APP_PRICE)
    m38._launch(game, app)
    if mode == "media":
        return game
    b = data.balance
    cat = data.game_data.category(b.media.streaming)
    price = cat.markets[0].reference_price_cents
    stream = m38._product(game, "Reel Stream", b.media.streaming, price)
    rows = tuple(s for s in game.state.product_segments if s.product_id != stream)
    seg = ProductSegment(stream, cat.markets[0].segment, price, 0.0)
    game.state = replace(
        game.state,
        product_segments=tuple(sorted((*rows, seg), key=lambda s: (s.product_id, s.segment))),
    )
    m38._launch(game, stream)
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
    modes = ("media", "stream", "advance")
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
