"""Create and edit saves for the M38 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

- `ev <save dir> <name>` (the practice save `pt-ev`): Volta, a stage-4 integrator in January 2022
  (2010-2021 played by the engine, the player's company doing nothing, so the world, its EV
  markets and car makers are the engine's): a live 25,000 t/yr lithium converter in North America
  fed at spot, a phone line live on a Foxconn contract, $20B of extra funding and a team. No car
  yet: it is ready to enter cars.
- `car <save dir> <name>`: the same company in January 2024 with a car line, Volta One, in
  development (quality 60, its features in reach of launch, priced at $31,500 in North America),
  a 2,000-car-a-month contract with Foxconn in San Francisco, and the default design.
- `selling <save dir> <name>`: `car` with the line launched on CATL cells (LFP), selling.
- `ripen <save dir> <name>`: every cell plant of the save built, paid, staffed and four years
  into its learning (as if built earlier).
- `advance <save dir> <name> <months>`: plays the save's next months with the engine (each a turn
  of its own), answering open critical events with their first choice.

The months in memory are written as one ledger entry per company netting what they posted.

Usage: uv run --project backend python tools/e2e_m38_save.py <mode> <save dir> <name> [months]
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final

from tst.balance import fixtures
from tst.balance.game import Game, start_game
from tst.config import Settings
from tst.db import repository
from tst.db.mappers import entry_to_row
from tst.db.repository import (
    create_save,
    existing_save_path,
    ledger_balances,
    load_state,
    open_session,
)
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import ChooseEvent
from tst.sim.actions.facilities import StaffFacility
from tst.sim.calendar import ym_to_turn
from tst.sim.hardware.models import ProductionContract
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, LedgerLine
from tst.sim.money import to_millicents
from tst.sim.products.models import Product, ProductSegment
from tst.sim.refining.actions import BuildRefinery
from tst.sim.state import (
    GameState,
    with_company,
    with_facility,
    with_person_state,
    with_product,
    with_product_segment,
    with_production_contract,
)
from tst.sim.vehicles.models import VehicleSpec

SEED: Final = 38
COMPANY: Final = "Volta"
EXTRA_CASH: Final = 20_000_000_000_00  # $20B of funding (equity)
STAGE: Final = 4
LI_TONNES: Final = 25_000
CAR: Final = "Volta One"
CAR_PRICE: Final = 3_150_000  # $31,500 a car (2010 dollars)
CAR_UNITS: Final = 2_000  # cars a month under contract
CONTRACT_MONTHS: Final = 36
CITY: Final = "san_francisco"
PHONE_PRICE: Final = 40_000
PHONE_UNITS: Final = 20_000
LEARNED_MONTHS: Final = 48


def _played(data: LoadedData, year: int) -> Game:
    """2010 to December of the year before played by the engine, the company doing nothing."""
    game = start_game(data, SEED, "funded_spinout")
    game.state = replace(game.state, companies=tuple(
        replace(c, name=COMPANY) if c.is_player else c for c in game.state.companies
    ))  # fmt: skip
    while game.state.turn < ym_to_turn(year, 1):
        game.turn()
    cash = (game.state.player.id, CASH)
    game.balances = {**game.balances, cash: game.balances.get(cash, 0) + EXTRA_CASH}
    game.state = with_company(game.state, replace(game.state.player, stage=STAGE))
    return game


def _energise(game: Game) -> None:
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def _live(game: Game, fid: int) -> None:
    """Built and paid for now (as if ordered earlier)."""
    f = game.state.facility(fid)
    assert f is not None
    turn = game.state.turn
    game.state = with_facility(
        game.state,
        replace(
            f,
            ordered_turn=turn - 24,
            ready_turn=turn,
            late_turn=turn,
            status="live",
            capex_paid_cents=f.capex_cents,
        ),
    )
    game.balances[(game.state.player.id, CASH)] -= f.capex_cents - f.capex_paid_cents


def _staff(game: Game, fid: int, role: str, n: int, sub: int) -> None:
    state, _ = fixtures.hire(
        game.state, game.loaded, role, "senior", n, f"plant {fid}", 12_000_000, sub
    )
    game.state = state
    unit = next(u.id for u in game.state.units if u.name == f"plant {fid}")
    _energise(game)
    assert game.act(StaffFacility(game.founder_id, fid, unit)), game.refused


def _converter(game: Game) -> int:
    _energise(game)
    before = {f.id for f in game.state.facilities}
    ok = game.act(BuildRefinery(game.founder_id, "li_converter", "north_america", LI_TONNES))
    assert ok, game.refused
    (fid,) = {f.id for f in game.state.facilities} - before
    _live(game, fid)
    _staff(game, fid, "process_engineer", 10, 1)
    return fid


def _product(game: Game, name: str, category: str, price: int) -> int:
    state = game.state
    pid, ids = state.next_ids.take("product")
    cat = game.loaded.game_data.category(category)
    expected = cat.features_at_start + cat.features_per_month * state.turn
    p = Product(
        id=pid,
        company_id=state.player.id,
        category=category,
        name=name,
        status="in_development",
        quality=60.0,
        feature_points=expected * 0.9,
        brand=40.0,
        marketing_budget_cents=5_000_000,
        created_turn=state.turn,
    )
    state = replace(with_product(state, p), next_ids=ids)
    state = with_product_segment(state, ProductSegment(pid, "consumer", price, 0.0))
    game.state = state
    return pid


def _contract(game: Game, pid: int, units: int, fee: int, city: str) -> None:
    state = game.state
    cid, ids = state.next_ids.take("production_contract")
    c = ProductionContract(
        id=cid,
        company_id=state.player.id,
        product_id=pid,
        kind="assembly",
        supplier="foxconn",
        units=units,
        price_millicents=to_millicents(fee),
        signed_turn=state.turn,
        end_turn=state.turn + CONTRACT_MONTHS - 1,
        city=city,
    )
    game.state = with_production_contract(replace(state, next_ids=ids), c)


def _launch(game: Game, pid: int) -> None:
    p = game.state.product(pid)
    assert p is not None
    game.state = with_product(
        game.state, replace(p, status="live", launched_turn=game.state.turn)
    )


def _state(mode: str, data: LoadedData) -> Game:
    year = 2022 if mode == "ev" else 2024
    game = _played(data, year)
    _converter(game)
    phone = _product(game, "Volta Phone", "devices", PHONE_PRICE)
    fee = data.balance.hardware.bom["devices"].contract_fee_cents
    _contract(game, phone, PHONE_UNITS, fee, "shenzhen")
    _launch(game, phone)
    game.state = with_company(game.state, replace(game.state.player, root_product_id=phone))
    if mode == "ev":
        return game
    car = _product(game, CAR, "vehicles", CAR_PRICE)
    fee = data.balance.hardware.bom["vehicles"].contract_fee_cents
    _contract(game, car, CAR_UNITS, fee, CITY)
    spec = VehicleSpec(car, 60.0, "lfp", 150.0, "l2", "licensed", "catl")
    game.state = replace(game.state, vehicle_specs=(*game.state.vehicle_specs, spec))
    if mode == "selling":
        _launch(game, car)
        game.state = with_company(game.state, replace(game.state.player, root_product_id=car))
    return game


def _write(
    path: Path,
    state: GameState,
    balances: Mapping[tuple[int, str], int],
    start: Mapping[tuple[int, str], int],
) -> None:
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, state)
        read_meta(session).current_turn = state.turn
        by_company: dict[int, list[LedgerLine]] = {}
        for key in sorted(set(balances) | set(start)):
            diff = balances.get(key, 0) - start.get(key, 0)
            if diff:
                by_company.setdefault(key[0], []).append(LedgerLine(key[1], diff))
        for cid, lines in sorted(by_company.items()):
            gap = sum(x.amount for x in lines)
            if gap:
                lines.append(LedgerLine(COMMON_EQUITY, -gap))
            if len(lines) >= 2:
                entry = LedgerEntry(state.turn - 1, cid, "E2E: the fixture's months", tuple(lines))
                session.add(entry_to_row(entry))


def make(save_dir: Path, name: str, data: LoadedData, mode: str) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = _state(mode, data)
    _write(path, game.state, game.balances, start)
    fixtures.finish(path, data, team=True, stage=STAGE)
    return path


def ripen(save_dir: Path, name: str, data: LoadedData) -> int:
    """Every cell plant live, paid, staffed and LEARNED_MONTHS into its learning."""
    path = existing_save_path(save_dir, name)
    with open_session(path) as session:
        state = load_state(session)
        balances = dict(ledger_balances(session))
    game = Game(data, state, dict(balances))
    n = 0
    for cp in list(game.state.cell_plants):
        f = game.state.facility(cp.facility_id)
        assert f is not None
        _live(game, f.id)
        kind = data.balance.facility.kinds[f.kind]
        _staff(game, f.id, "process_engineer", -(-f.capacity // int(kind.staff_per)), 10 + n)
        plants = tuple(
            replace(c, months_run=LEARNED_MONTHS) if c.facility_id == f.id else c
            for c in game.state.cell_plants
        )
        game.state = replace(game.state, cell_plants=plants)
        n += 1
    _write(path, game.state, game.balances, balances)
    return n


def advance(save_dir: Path, name: str, data: LoadedData, months: int) -> int:
    """Each month: open critical events answered with their first choice, then the month."""
    path = existing_save_path(save_dir, name)
    for _ in range(months):
        with open_session(path) as session:
            state = load_state(session)
        founder = state.founder_of(state.player.id)
        for event in state.open_events(state.player.id):
            if event.severity == "critical" and event.status == "open" and founder is not None:
                choice = ChooseEvent(founder.id, event.id, event.choices[0].key)
                repository.run_action(path, data, choice)
        repository.run_turn(path, data, block_major=False)
    return months


def main(argv: list[str]) -> int:
    modes = ("ev", "car", "selling", "ripen", "advance")
    if len(argv) < 4 or argv[1] not in modes or (argv[1] == "advance") != (len(argv) == 5):
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    if argv[1] == "advance":
        advance(Path(argv[2]), argv[3], data, int(argv[4]))
        return 0
    if argv[1] == "ripen":
        print(ripen(Path(argv[2]), argv[3], data))
        return 0
    print(make(Path(argv[2]), argv[3], data, argv[1]))
    return 0


if __name__ == "__main__":
    import e2e_cache  # M59: CI keeps the saves it builds (tools/e2e_cache.py)

    sys.exit(e2e_cache.run(__file__, sys.argv[1:], lambda: main(sys.argv)))
