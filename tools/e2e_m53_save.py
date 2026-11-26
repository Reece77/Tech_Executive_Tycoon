"""Create and edit saves for the M53 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

- `telecom <save dir> <name>` (the practice save `pt-telecom`): Nova, a stage-4 devices and chips
  group in January 2018 (2010-2017 played by the engine, the player's company doing nothing, so the
  world and its operators are the engine's): a live mobile chip and a live phone, $20B of extra
  funding (cash for a network) and a team. No telecom line yet; the UK's April 2018 auction (2.3
  and 3.4 GHz, mid band) is announced, as the data announces it that month.
- `network <save dir> <name>`: the same group in January 2020 (5G open) with a mobile line (Nova
  Mobile, live, priced) and 100 MHz of mid-band and 20 MHz of low-band spectrum in the United
  States; no sites yet.
- `huawei <save dir> <name>`: the same group in December 2025 with the network save's line and
  spectrum and 2,500 live North American 4G sites on Huawei radios, so the US ban's June 2026
  deadline owes most of them replaced.
- `advance <save dir> <name> <months>`: plays the save's next months with the engine, answering
  open critical events with their first choice.

Usage: uv run --project backend python tools/e2e_m53_save.py <mode> <save dir> <name> [months]
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
from tst.sim.facilities.models import Facility
from tst.sim.products.models import ProductSegment
from tst.sim.state import with_company, with_facility
from tst.sim.telecom import spectrum
from tst.sim.telecom.models import RadioNetwork, SpectrumLicence

SEED: Final = 53
COMPANY: Final = "Nova"
STAGE: Final = 4
YEARS: Final = {"telecom": 2018, "network": 2020, "huawei": 2025}
REGION: Final = "north_america"
SITES: Final = 2500
MOBILE_PRICE: Final = 4_000  # $40 a month (2010 dollars, north_america's reference)


def _segments(game: Game, pid: int, prices: dict[str, int]) -> None:
    rows = tuple(s for s in game.state.product_segments if s.product_id != pid)
    new = tuple(ProductSegment(pid, seg, price, 0.0) for seg, price in prices.items())
    game.state = replace(
        game.state,
        product_segments=tuple(sorted((*rows, *new), key=lambda s: (s.product_id, s.segment))),
    )


def _licence(game: Game, lid: int, band: str, mhz: float, price: int) -> SpectrumLicence:
    turn = game.state.turn
    return SpectrumLicence(
        id=lid,
        company_id=game.state.player.id,
        region=REGION,
        area="united_states",
        band=band,  # type: ignore[arg-type]
        mhz=mhz,
        auction_id=0,
        paid_cents=price,
        turn=turn - 1,
        expires_turn=turn - 1 + 15 * 12,
    )


def _state(mode: str, data: LoadedData) -> Game:
    m38.SEED, m38.COMPANY, m38.STAGE = SEED, COMPANY, STAGE  # m38's helpers read these
    year = YEARS["telecom" if mode == "telecom" else mode]
    game = m38._played(data, year)
    b = data.balance
    chip = m38._product(game, "Nova Core", "chips_mobile_soc", 2_500)
    _segments(game, chip, {"device_oems": 2_500})
    m38._launch(game, chip)
    phone = m38._product(game, "Nova Phone", "devices", 45_000)
    m38._launch(game, phone)
    game.state = with_company(game.state, replace(game.state.player, root_product_id=phone))
    t = game.state.telecom
    if mode == "telecom":
        d = data.game_data.telecom
        assert d is not None
        uk = d.auction("uk_5g_2018")
        assert uk is not None
        a = spectrum._from_def(uk, t.next_auction_id(), b.telecom.scale)
        game.state = replace(game.state, telecom=replace(t, auctions=(*t.auctions, a)))
        return game
    mobile = m38._product(game, "Nova Mobile", b.telecom.mobile, MOBILE_PRICE)
    _segments(game, mobile, {"telecom_consumer": MOBILE_PRICE, "telecom_business": 6_000})
    m38._launch(game, mobile)
    licences = (
        _licence(game, 1, "low", 20.0, 300_000_000_00),
        _licence(game, 2, "mid", 100.0, 2_000_000_000_00),
    )
    paid = sum(x.paid_cents for x in licences)
    player = game.state.player.id
    game.balances[(player, "1540_spectrum_licences")] = (
        game.balances.get((player, "1540_spectrum_licences"), 0) + paid
    )
    game.balances[(player, "1000_cash")] -= paid
    game.state = replace(game.state, telecom=replace(t, licences=licences))
    if mode == "network":
        return game
    fid, ids = game.state.next_ids.take("facility")
    turn = game.state.turn
    capex = SITES * 20_000_000
    f = Facility(
        id=fid,
        company_id=player,
        kind=b.telecom.tower_kind,
        region=REGION,
        capacity=SITES,
        on_time=SITES,
        ordered_turn=turn - 60,
        ready_turn=turn - 48,
        late_turn=turn - 48,
        capex_cents=capex,
        input_index=1.0,
        capex_paid_cents=capex,
        status="live",
    )
    game.state = replace(with_facility(game.state, f), next_ids=ids)
    game.balances[(player, "1500_ppe")] = game.balances.get((player, "1500_ppe"), 0) + capex
    game.balances[(player, "1000_cash")] -= capex
    rec = RadioNetwork(fid, player, REGION, "g4", "huawei")
    t = game.state.telecom
    game.state = replace(game.state, telecom=replace(t, radios=(rec,)))
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
    modes = ("telecom", "network", "huawei", "advance")
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
