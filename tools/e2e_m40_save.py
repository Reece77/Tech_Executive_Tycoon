"""Create and edit saves for the M40 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

- `space <save dir> <name>` (the practice save `pt-space`): Halcyon, a stage-4 chip and devices
  group in January 2026 (2010-2025 played by the engine, the player's company doing nothing, so
  the world, its launch providers and constellations are the engine's): a live mobile chip and a
  live phone, $20B of extra funding, a team, and a reusability lead of 25 (a programme begun 36
  months ago, so first-stage recovery is within reach). No space line yet.
- `launcher <save dir> <name>`: the same with a launch line (Halcyon Lift, live, priced, no design
  yet), a staffed two-pad launch site in North America, a broadband line (Halcyon Net, live,
  priced), a 25-a-month satellite plant, and a North American licence granted.
- `shell <save dir> <name>`: the launcher save with a one-shell constellation (Halcyon Ring) on
  bought launches: 100 satellites in orbit (short of the shell's 90%) and 40 waiting, so the next
  month's launch completes the shell and coverage opens North America.
- `failure <save dir> <name>`: a failed launch of the constellation's waiting satellites now, as
  the engine's own failure does (the satellites written off, the critical event queued).
- `advance <save dir> <name> <months>`: plays the save's next months with the engine, answering
  open critical events with their first choice.

Usage: uv run --project backend python tools/e2e_m40_save.py <mode> <save dir> <name> [months]
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
from tst.db.repository import create_save, existing_save_path, ledger_balances, load_state, open_session
from tst.loader import LoadedData, load_all
from tst.sim.actions.facilities import BuildFacility
from tst.sim.ledger import DEPRECIATION, PPE
from tst.sim.products.models import ProductSegment
from tst.sim.research.models import ResearchLead
from tst.sim.space import events
from tst.sim.space.models import Cohort, Constellation, LaunchRecord, Licence
from tst.sim.state import with_company, with_research_lead

SEED: Final = 40
COMPANY: Final = "Halcyon"
STAGE: Final = 4
YEAR: Final = 2026
REGION: Final = "north_america"
LEAD: Final = 25.0
PROGRAMME_MONTHS: Final = 36


def _segments(game: Game, pid: int, prices: dict[str, int]) -> None:
    rows = tuple(s for s in game.state.product_segments if s.product_id != pid)
    new = tuple(ProductSegment(pid, seg, price, 0.0) for seg, price in prices.items())
    game.state = replace(
        game.state,
        product_segments=tuple(sorted((*rows, *new), key=lambda s: (s.product_id, s.segment))),
    )


def _facility(game: Game, kind: str, capacity: int, role: str, staff: int, sub: int) -> int:
    m38._energise(game)
    before = {f.id for f in game.state.facilities}
    assert game.act(BuildFacility(game.founder_id, kind, REGION, capacity)), game.refused
    (fid,) = {f.id for f in game.state.facilities} - before
    m38._live(game, fid)
    m38._staff(game, fid, role, staff, sub)
    return fid


def _state(mode: str, data: LoadedData) -> Game:
    m38.SEED, m38.COMPANY, m38.STAGE = SEED, COMPANY, STAGE  # m38's helpers read these
    game = m38._played(data, YEAR)
    b = data.balance
    chip = m38._product(game, "Halcyon Core", "chips_mobile_soc", 2_500)
    _segments(game, chip, {"device_oems": 2_500})
    m38._launch(game, chip)
    phone = m38._product(game, "Halcyon Phone", "devices", 45_000)
    m38._launch(game, phone)
    game.state = with_company(game.state, replace(game.state.player, root_product_id=phone))
    player = game.state.player.id
    game.state = with_research_lead(game.state, ResearchLead(player, b.space.domain, LEAD))
    started = ((player, game.state.turn - PROGRAMME_MONTHS),)
    game.state = replace(game.state, space=replace(game.state.space, reuse_started=started))
    if mode == "space":
        return game
    lift = m38._product(game, "Halcyon Lift", b.space.launch, 5_000_000_000)
    _segments(game, lift, {"satellite_operators": 5_000_000_000, "government": 8_500_000_000})
    m38._launch(game, lift)
    _facility(game, b.space.site_kind, 2, "operations_manager", 2, 1)
    net = m38._product(game, "Halcyon Net", b.space.broadband, 9_000)
    _segments(game, net, {"consumer": 9_000, "enterprise": 50_000})
    m38._launch(game, net)
    _facility(game, b.space.plant_kind, 25, "manufacturing_engineer", 5, 2)
    lic = Licence(player, REGION, "granted", game.state.turn - 6, None, game.state.turn)
    game.state = replace(game.state, space=replace(game.state.space, licences=(lic,)))
    if mode == "launcher":
        return game
    turn = game.state.turn
    ring = Constellation(
        id=1,
        company_id=player,
        name="Halcyon Ring",
        kind="broadband",
        product_id=net,
        shells=1,
        mass_kg=300.0,
        life_months=60,
        d2d=False,
        insured=True,
        build_per_month=0,
        launches_per_month=1,
        vehicle_product_id=None,
        created_turn=turn - 6,
        ground=40,
        cohorts=(Cohort(0, turn - 3, 100, 10_000_000_000, turn + 57),),
        capex_cents=10_000_000_000 + 40 * 20_000_000,
        cash_cents=-(10_000_000_000 + 40 * 20_000_000),
    )
    game.state = replace(game.state, space=replace(game.state.space, constellations=(ring,)))
    game.balances[(player, PPE)] = game.balances.get((player, PPE), 0) + ring.capex_cents
    game.balances[(player, "1000_cash")] -= ring.capex_cents
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


def fail(save_dir: Path, name: str, data: LoadedData) -> int:
    """The constellation's waiting satellites lost in a launch failure now (module docstring)."""
    path = existing_save_path(save_dir, name)
    with open_session(path) as session:
        state = load_state(session)
        balances = dict(ledger_balances(session))
    game = Game(data, state, dict(balances))
    c = game.state.space.constellations[0]
    sats = c.ground
    value = sats * 20_000_000
    c = replace(c, ground=0, lost=c.lost + sats, capex_cents=c.capex_cents - value)
    record = LaunchRecord(
        game.state.turn, c.company_id, None, "Bought launch", "own", c.id, sats, False
    )
    space = replace(
        game.state.space, constellations=(c,), launches=(*game.state.space.launches, record)
    )
    game.state = events.queue_failure(replace(game.state, space=space), c, sats, value, None)
    player = c.company_id
    game.balances[(player, PPE)] = game.balances.get((player, PPE), 0) - value
    game.balances[(player, DEPRECIATION)] = game.balances.get((player, DEPRECIATION), 0) + value
    m38._write(path, game.state, game.balances, balances)
    return sats


def main(argv: list[str]) -> int:
    modes = ("space", "launcher", "shell", "failure", "advance")
    if len(argv) < 4 or argv[1] not in modes or (argv[1] == "advance") != (len(argv) == 5):
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    if argv[1] == "advance":
        m38.advance(Path(argv[2]), argv[3], data, int(argv[4]))
        return 0
    if argv[1] == "failure":
        print(fail(Path(argv[2]), argv[3], data))
        return 0
    print(make(Path(argv[2]), argv[3], data, argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
