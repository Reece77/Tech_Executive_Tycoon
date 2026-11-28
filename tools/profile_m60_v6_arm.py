"""Give a late save the player's own v6 industries, for profiling (M60 sub-task 1; a measuring
tool, never part of the game): copies `<save>` to `<out>` and adds to the player's company, as the
M53-M55 e2e fixtures do, a mobile line with low- and mid-band licences, 2,500 towers and a 4G
radio network in North America (tools/e2e_m53_save.py's "huawei" mode), a chartered North
American bank with 300,000 consumer and 20,000 business accounts and its banking line
(tools/e2e_m54_save.py's "rates" mode), a streaming line (tools/e2e_m55_save.py's "stream"
mode) and a software line selling half in Europe (the "currency" mode). The rival world is the
save's own. Then `tools/profile_m60.py <out>` times the months.

    uv run --project backend python tools/profile_m60_v6_arm.py <save.tst.sqlite> <out.tst.sqlite>
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import replace
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
BACKEND = TOOLS.parent / "backend"
sys.path[:0] = [str(BACKEND), str(TOOLS)]

REGION = "north_america"
SITES = 2_500
BANK_CAPITAL = 60_000_000_000  # $600M, as e2e_m54_save
MOBILE_PRICE = 4_000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("save", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()

    import e2e_m38_save as m38
    import e2e_m53_save as m53
    import e2e_m54_save as m54
    from tst.balance.game import Game
    from tst.db import migrate
    from tst.db.repository import current_balances, load_state, open_session
    from tst.loader import load_all
    from tst.sim.facilities.models import Facility
    from tst.sim.finserv.models import Bank
    from tst.sim.products.models import ProductSegment
    from tst.sim.state import with_facility
    from tst.sim.telecom.models import RadioNetwork

    shutil.copy(args.save, args.out)
    migrate.ensure_current(args.out)
    data = load_all(BACKEND / "data")
    with open_session(args.out) as session:
        state = load_state(session)
        balances = dict(current_balances(session, state.turn))
    start = dict(balances)
    game = Game.__new__(Game)
    Game.__init__(game, data, state, balances)
    b = data.balance
    player = game.state.player.id

    # telecom (e2e_m53_save "huawei")
    mobile = m38._product(game, "Arm Mobile", b.telecom.mobile, MOBILE_PRICE)
    m53._segments(game, mobile, {"telecom_consumer": MOBILE_PRICE, "telecom_business": 6_000})
    m38._launch(game, mobile)
    t = game.state.telecom
    first = max((x.id for x in t.licences), default=0) + 1
    licences = (
        m53._licence(game, first, "low", 20.0, 300_000_000_00),
        m53._licence(game, first + 1, "mid", 100.0, 2_000_000_000_00),
    )
    paid = sum(x.paid_cents for x in licences)
    game.balances[(player, "1540_spectrum_licences")] = (
        game.balances.get((player, "1540_spectrum_licences"), 0) + paid
    )
    game.balances[(player, "1000_cash")] -= paid
    game.state = replace(game.state, telecom=replace(t, licences=(*t.licences, *licences)))
    fid, ids = game.state.next_ids.take("facility")
    turn = game.state.turn
    capex = SITES * 20_000_000
    tower = Facility(
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
    game.state = replace(with_facility(game.state, tower), next_ids=ids)
    game.balances[(player, "1500_ppe")] = game.balances.get((player, "1500_ppe"), 0) + capex
    game.balances[(player, "1000_cash")] -= capex
    t = game.state.telecom
    radio = RadioNetwork(fid, player, REGION, "g4", "huawei")
    game.state = replace(game.state, telecom=replace(t, radios=(*t.radios, radio)))

    # a bank (e2e_m54_save "rates") and a line selling in Europe ("currency")
    bank_line = m38._product(game, "Arm Bank", b.finserv.banking_category, 800)
    m54._segments(
        game,
        bank_line,
        {"bank_consumer": (800, 300_000.0), "bank_business": (6_000, 20_000.0)},
        {},
    )
    m38._launch(game, bank_line)
    fs = game.state.finserv
    bank = Bank(
        id=max((x.id for x in fs.banks), default=0) + 1,
        company_id=player,
        region=REGION,
        status="chartered",
        applied_turn=turn,
        charter_turn=turn,
        beta=0.9,
        reserves_cents=BANK_CAPITAL,
        capital_in_cents=BANK_CAPITAL,
    )
    game.state = replace(game.state, finserv=replace(fs, banks=(*fs.banks, bank)))
    game.balances[(player, "1060_bank_reserves")] = (
        game.balances.get((player, "1060_bank_reserves"), 0) + BANK_CAPITAL
    )
    game.balances[(player, "1000_cash")] -= BANK_CAPITAL
    cloud = m38._product(game, "Arm Cloud", "b2b_saas", 5_000)
    m54._segments(game, cloud, {"smb": (5_000, 4_000.0)}, {"smb": (5_000, 4_000.0)})
    m38._launch(game, cloud)

    # streaming (e2e_m55_save "stream")
    cat = data.game_data.category(b.media.streaming)
    price = cat.markets[0].reference_price_cents
    stream = m38._product(game, "Arm Stream", b.media.streaming, price)
    rows = tuple(s for s in game.state.product_segments if s.product_id != stream)
    seg = ProductSegment(stream, cat.markets[0].segment, price, 0.0)
    game.state = replace(
        game.state,
        product_segments=tuple(sorted((*rows, seg), key=lambda s: (s.product_id, s.segment))),
    )
    m38._launch(game, stream)

    m38._write(args.out, game.state, game.balances, start)
    print(f"wrote {args.out} at turn {game.state.turn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
