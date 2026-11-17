"""Create and edit saves for the M39 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

- `robotics <save dir> <name>` (the practice save `pt-robotics`): Kestrel, a stage-4 EV maker in
  January 2027 (2010-2026 played by the engine, the player's company doing nothing, so the world,
  its robot makers and robotaxi services are the engine's): a live AI model (quality 70), an
  autonomy lead of 30, a car line (Kestrel One) live at L3 on CATL cells, made in a staffed
  2,000-car-a-month vehicle plant in North America (a high-wage region), $20B of extra funding
  and a team. No robots yet.
- `taxi <save dir> <name>`: the same with L4 (an autonomy lead of 50 and an AI model of quality
  85), a robotaxi service (Kestrel Ride) live and a live 100-car depot in Phoenix.
- `permit <save dir> <name>`: every zone under review approved now (as if its review had ended).
- `incident <save dir> <name>`: a serious incident in the first active zone (its permit
  suspended, the critical event queued), as the engine's own incident does.
- `advance <save dir> <name> <months>`: plays the save's next months with the engine, answering
  open critical events with their first choice.

Usage: uv run --project backend python tools/e2e_m39_save.py <mode> <save dir> <name> [months]
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

import e2e_m38_save as m38

from tst.balance import fixtures
from tst.balance.game import Game, start_game
from tst.config import Settings
from tst.db.repository import create_save, existing_save_path, ledger_balances, load_state
from tst.db.repository import open_session
from tst.loader import LoadedData, load_all
from tst.sim.actions.facilities import BuildFacility
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import CASH
from tst.sim.research.models import ResearchLead
from tst.sim.robotics import robotaxi as rt
from tst.sim.robotics.actions import BuildDepot
from tst.sim.state import with_company, with_product, with_research_lead
from tst.sim.vehicles.models import VehicleSpec

SEED: Final = 39
COMPANY: Final = "Kestrel"
EXTRA_CASH: Final = 20_000_000_000_00
STAGE: Final = 4
YEAR: Final = 2027
CAR: Final = "Kestrel One"
CAR_PRICE: Final = 3_150_000
PLANT_CARS: Final = 2_000
REGION: Final = "north_america"


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


def _lead(game: Game, lead: float) -> None:
    domain = game.loaded.balance.vehicles.domain
    game.state = with_research_lead(game.state, ResearchLead(game.state.player.id, domain, lead))


def _quality(game: Game, pid: int, quality: float) -> None:
    p = game.state.product(pid)
    assert p is not None
    game.state = with_product(game.state, replace(p, quality=quality))


def _plant(game: Game) -> int:
    m38._energise(game)
    before = {f.id for f in game.state.facilities}
    kind = game.loaded.balance.vehicles.plant.kind
    assert game.act(BuildFacility(game.founder_id, kind, REGION, PLANT_CARS)), game.refused
    (fid,) = {f.id for f in game.state.facilities} - before
    m38._live(game, fid)
    staff = game.loaded.balance.facility.kinds[kind].staff_per
    m38._staff(game, fid, "manufacturing_engineer", -(-PLANT_CARS // int(staff)), 1)
    return fid


def _state(mode: str, data: LoadedData) -> Game:
    game = _played(data)
    ai = m38._product(game, "Kestrel Mind", "ai_models", 2_000_000)
    m38._launch(game, ai)
    _quality(game, ai, 70.0)
    _lead(game, 30.0)
    _plant(game)
    car = m38._product(game, CAR, "vehicles", CAR_PRICE)
    spec = VehicleSpec(car, 70.0, "lfp", 150.0, "l3", "licensed", "catl")
    game.state = replace(game.state, vehicle_specs=(*game.state.vehicle_specs, spec))
    m38._launch(game, car)
    game.state = with_company(game.state, replace(game.state.player, root_product_id=car))
    if mode == "robotics":
        return game
    _quality(game, ai, 85.0)
    _lead(game, 50.0)
    ride = m38._product(game, "Kestrel Ride", "mobility", 1)
    game.state = replace(
        game.state,
        product_segments=tuple(s for s in game.state.product_segments if s.product_id != ride),
    )
    m38._launch(game, ride)
    m38._energise(game)
    assert game.act(BuildDepot(game.founder_id, "phoenix", 100)), game.refused
    depot = game.state.depots[-1]
    m38._live(game, depot.facility_id)
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


def _edit(save_dir: Path, name: str, data: LoadedData, mode: str) -> int:
    path = existing_save_path(save_dir, name)
    with open_session(path) as session:
        state = load_state(session)
        balances = dict(ledger_balances(session))
    game = Game(data, state, dict(balances))
    n = 0
    if mode == "permit":
        zones = []
        for z in game.state.zones:
            if z.status == "applied":
                z = replace(z, status="active", approved_turn=game.state.turn)
                n += 1
            zones.append(z)
        game.state = replace(game.state, zones=tuple(zones))
    else:
        zone = next(z for z in game.state.zones if z.status == "active")
        name_ = f"{COMPANY} Ride in {rt.city(data.game_data, zone.city).label}"
        state, zone, entries, _ = rt._incident(game.state, zone, True, name_, data.balance)
        game.state = replace(
            state, zones=tuple(zone if z.id == zone.id else z for z in state.zones)
        )
        for e in entries:
            for line in e.lines:
                key = (e.company_id, line.account)
                game.balances[key] = game.balances.get(key, 0) + line.amount
        n = 1
    m38._write(path, game.state, game.balances, balances)
    return n


def main(argv: list[str]) -> int:
    modes = ("robotics", "taxi", "permit", "incident", "advance")
    if len(argv) < 4 or argv[1] not in modes or (argv[1] == "advance") != (len(argv) == 5):
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    if argv[1] == "advance":
        m38.advance(Path(argv[2]), argv[3], data, int(argv[4]))
        return 0
    if argv[1] in ("permit", "incident"):
        print(_edit(Path(argv[2]), argv[3], data, argv[1]))
        return 0
    print(make(Path(argv[2]), argv[3], data, argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
