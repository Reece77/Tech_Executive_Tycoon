"""Create and edit saves for the M32 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

- `power <save dir> <name>` (the practice save `pt-power`): Volt, a stage-4 integrator in January
  2027 (2010-2026 played by the engine, so the world, its power producers and the grid queues are
  the engine's): a live 50,000-start fab in North America and two 10,000-CU GPU data centres, in
  North America and Europe, all connected; $30B of extra funding.
- `fab <save dir> <name>`: `power` without the data centres.
- `outage <save dir> <name>`: `power`'s company with its fab in Africa (the least reliable grid)
  instead, and no data centres.
- `advance <save dir> <name> <months>`: plays the save's next months with the engine (each a turn
  of its own), answering open critical events with their first choice.
- `until_outage <save dir> <name>`: plays months until the player's fab region has a grid outage
  (at most 24).

The months in memory are written as one ledger entry per company netting what they posted.

Usage: uv run --project backend python tools/e2e_m32_save.py <mode> <save dir> <name> [months]
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final

from tst.balance import fixtures, m21
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
from tst.sim.actions.facilities import BuildFacility
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, LedgerLine
from tst.sim.state import GameState, with_company, with_person_state, with_queue_entry

SEED: Final = 32
COMPANY: Final = "Volt"
START: Final = 204  # January 2027
EXTRA_CASH: Final = 30_000_000_000_00  # $30B of funding (equity): a fab and two data centres
FAB_NODE: Final = "n28"
FAB_STARTS: Final = 50_000
DC_KIND: Final = "data_centre_gpu"
DC_UNITS: Final = 10_000
STAGE: Final = 4
MAX_WAIT: Final = 24


def _played(data: LoadedData) -> Game:
    """2010 to December 2026 played by the engine, the player's company doing nothing."""
    game = start_game(data, SEED, "funded_spinout")
    game.state = replace(game.state, companies=tuple(
        replace(c, name=COMPANY) if c.is_player else c for c in game.state.companies
    ))  # fmt: skip
    while game.state.turn < START:
        game.turn()
    cash = (game.state.player.id, CASH)
    game.balances = {**game.balances, cash: game.balances.get(cash, 0) + EXTRA_CASH}
    game.state = with_company(game.state, replace(game.state.player, stage=STAGE))
    return game


def _connect(game: Game, fid: int) -> None:
    """An established site: its grid connection done (it was built before the fixture)."""
    q = next((x for x in game.state.grid_queue if x.facility_id == fid), None)
    if q is not None and q.connected_turn is None:
        game.state = with_queue_entry(game.state, replace(q, connected_turn=game.state.turn))


def _energise(game: Game) -> None:
    ps = game.state.person_state(game.founder_id)
    game.state = with_person_state(game.state, replace(ps, energy=100))


def _data_centre(game: Game, region: str) -> int:
    _energise(game)
    before = {f.id for f in game.state.facilities}
    assert game.act(BuildFacility(game.founder_id, DC_KIND, region, DC_UNITS)), game.refused
    (fid,) = {f.id for f in game.state.facilities} - before
    f = game.state.facility(fid)
    assert f is not None
    turn = game.state.turn
    from tst.sim.state import with_facility

    game.state = with_facility(
        game.state,
        replace(
            f,
            ordered_turn=turn - 12,
            ready_turn=turn,
            late_turn=turn,
            status="live",
            capex_paid_cents=f.capex_cents,
        ),
    )
    game.balances[(game.state.player.id, CASH)] -= f.capex_cents
    _connect(game, fid)
    return fid


def _state(mode: str, data: LoadedData) -> Game:
    game = _played(data)
    region = "africa" if mode == "outage" else "north_america"
    fid = m21.build(game, FAB_NODE, region, FAB_STARTS, ready_now=True)
    _connect(game, fid)
    if mode == "power":
        _data_centre(game, "north_america")
        _data_centre(game, "europe")
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


def until_outage(save_dir: Path, name: str, data: LoadedData) -> int:
    path = existing_save_path(save_dir, name)
    for n in range(1, MAX_WAIT + 1):
        advance(save_dir, name, data, 1)
        with open_session(path) as session:
            state = load_state(session)
        regions = {f.region for f in state.facilities if f.company_id == state.player.id}
        if any(o.region in regions and o.turn == state.turn - 1 for o in state.grid_outages):
            return n
    raise RuntimeError(f"no grid outage in {MAX_WAIT} months")


def main(argv: list[str]) -> int:
    modes = ("power", "fab", "outage", "advance", "until_outage")
    if len(argv) < 4 or argv[1] not in modes or (argv[1] == "advance") != (len(argv) == 5):
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    if argv[1] == "advance":
        advance(Path(argv[2]), argv[3], data, int(argv[4]))
        return 0
    if argv[1] == "until_outage":
        print(until_outage(Path(argv[2]), argv[3], data))
        return 0
    print(make(Path(argv[2]), argv[3], data, argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
