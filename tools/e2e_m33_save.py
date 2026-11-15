"""Create saves for the M33 Playwright flows and the practice save (an e2e fixture tool). Never
used by the game.

- `litho <save dir> <name>` (the practice save `pt-litho`): Lithos, a stage-5 chip group in
  January 2030. 2010-2029 are played by the engine (a do-nothing company, so ASML's queue, the
  world and the markets are the game's own), then it is given $300B of funding, a process lead
  (as if researched), a live mobile SoC of its own, two leading-edge fabs in Taiwan (3 nm and
  5 nm, 25,000 starts each, built and staffed) and a lithography lab of 45 hardware engineers
  researching the `lithography` domain with a lead of 12 points: enough to start the
  programme's first stage (a DUV-class scanner). Its Equipment screen orders high-NA tools.
- `advance <save dir> <name> <months>`: plays the save's next months with the engine.

The months in memory are written as one ledger entry per company netting what they posted.

Usage: uv run --project backend python tools/e2e_m33_save.py <mode> <save dir> <name> [months]
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final

from tst.balance import fixtures, m12b, m21
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
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, LedgerLine
from tst.sim.research.models import ResearchLead, ResearchProject
from tst.sim.state import with_research_lead, with_research_project

SEED: Final = 33
COMPANY: Final = "Lithos"
START: Final = ym_to_turn(2030, 1)
EXTRA_CASH: Final = 30_000_000_000_000  # $300B
PROCESS_LEAD: Final = 40.0  # process lead points, as if researched (every node's need met)
LITHO_LEAD: Final = 12.0  # lithography lead: litho_1 needs 10
LAB: Final = 45  # hardware engineers on the lithography project (litho_1 needs 40)
FABS: Final = (("n3", 25_000), ("n5", 25_000))
SUB: Final = 33  # fixtures.hire's draw offset for the lab


def _played(data: LoadedData) -> Game:
    """2010 to December 2029 played by the engine, the player's company doing nothing."""
    game = start_game(data, SEED, "funded_spinout")
    game.state = replace(game.state, companies=tuple(
        replace(c, name=COMPANY) if c.is_player else c for c in game.state.companies
    ))  # fmt: skip
    while game.state.turn < START:
        game.turn()
    cash = (game.state.player.id, CASH)
    game.balances = {**game.balances, cash: game.balances.get(cash, 0) + EXTRA_CASH}
    return game


def _equip(game: Game, data: LoadedData) -> None:
    b, d = data.balance, data.game_data
    pid = game.state.player.id
    game.state = with_research_lead(game.state, ResearchLead(pid, b.refining.domain, PROCESS_LEAD))
    ref = d.category("chips_mobile_soc").market("device_oems").reference_price_cents
    game.state, _ = m12b.product(
        game.state, "chips_mobile_soc", "device_oems", ref, "Lithos SoC", root=True
    )
    for node, size in FABS:
        m21.build(game, node, "east_asia", size)  # in Taiwan, made ready (tools waived)
    domain = b.equipment.programme.domain
    game.state = with_research_lead(game.state, ResearchLead(pid, domain, LITHO_LEAD))
    game.state, _ = fixtures.hire(
        game.state, data, "hardware_engineer", "senior", LAB, "Lithography lab", 18_000_000, SUB
    )
    uid = next(u.id for u in game.state.units if u.name == "Lithography lab")
    project_id, ids = game.state.next_ids.take("research_project")
    game.state = with_research_project(
        replace(game.state, next_ids=ids),
        ResearchProject(project_id, pid, domain, uid, game.state.turn),
    )


def _write(
    path: Path,
    game: Game,
    start: Mapping[tuple[int, str], int],
) -> None:
    state, balances = game.state, game.balances
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


def make(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = _played(data)
    _equip(game, data)
    _write(path, game, start)
    fixtures.finish(path, data, team=True, stage=5)
    return path


def advance(save_dir: Path, name: str, data: LoadedData, months: int) -> None:
    path = existing_save_path(save_dir, name)
    for _ in range(months):
        repository.run_turn(path, data, block_major=False)


def main(argv: list[str]) -> int:
    modes = ("litho", "advance")
    if len(argv) < 4 or argv[1] not in modes or (argv[1] == "advance") != (len(argv) == 5):
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    if argv[1] == "advance":
        advance(Path(argv[2]), argv[3], data, int(argv[4]))
        return 0
    print(make(Path(argv[2]), argv[3], data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
