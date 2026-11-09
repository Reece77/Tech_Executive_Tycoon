"""Create saves for the M21 Playwright flows and tests (an e2e fixture tool). Never used by the
game.

- `nodes <save dir> <name>`: a funded spinout in January 2021: the node timeline shows TSMC's
  N5 from April 2020.
- `mature <save dir> <name>`: January 2016, $60B more cash, a process lead (as if researched)
  and a team of fab engineers, with a 28 nm fab of 10,000 starts in East Asia built and staffed:
  the next Continue starts its production; later ones raise its yield. Ready to build another.
- `euv <save dir> <name>`: January 2021 with the same cash, lead and team: ready to build a
  leading-edge fab, whose EUV tools arrive after its construction ends.
- `slots <save dir> <name>`: the `mature` save without chips of its own: every start its fab
  runs is sold as a foundry slot to rival designers.

Fabs are ordered through `build_fab` (the engine's own action); only construction is skipped:
a fab is made ready and its capex posted to PPE at once.

Usage: uv run --project backend python tools/e2e_m21_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from tst.balance import m21
from tst.balance.game import Game
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, ledger_balances, load_state, open_session
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import CASH, COMMON_EQUITY, PPE, LedgerEntry
from tst.sim.research.models import ResearchLead
from tst.sim.state import with_research_lead

SEED = 21
EXTRA_CASH = 6_000_000_000_000  # $60B
LEAD = 30.0  # process lead points, as if researched


def _create(save_dir: Path, name: str, data: LoadedData, turn: int) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name="Lithos", data=data, save_dir=save_dir
    )
    entry = LedgerEntry.transfer(
        turn=0,
        company_id=1,
        memo="E2E funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=EXTRA_CASH,
    )
    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))
        before = load_state(session)
        sync_state(session, before, replace(before, turn=turn))
        read_meta(session).current_turn = turn
    return path


def _edit(path: Path, data: LoadedData, step: Callable[[Game], None]) -> None:
    """Run `step(game)` on the save's state in memory and write the result: the state, and the
    capex of fabs made ready at once as an entry (cash to PPE)."""
    with open_session(path) as session, session.begin():
        before = load_state(session)
        game = Game(data, before, dict(ledger_balances(session)))
        ppe = game.balances.get((1, PPE), 0)
        step(game)
        built = game.balances.get((1, PPE), 0) - ppe
        sync_state(session, before, replace(game.state, turn=before.turn))
        if built > 0:
            session.add(
                entry_to_row(
                    LedgerEntry.transfer(
                        turn=before.turn,
                        company_id=1,
                        memo="E2E: fabs built",
                        debit=PPE,
                        credit=CASH,
                        amount=built,
                    )
                )
            )


def _ready(game: Game) -> None:
    """A process lead and a team of fab engineers (enough for a 10,000-start fab, and more)."""
    domain = game.loaded.balance.refining.domain
    game.state = with_research_lead(game.state, ResearchLead(1, domain, LEAD))
    m21.hire_unit(game, "Fab team", 4)


def nodes(save_dir: Path, name: str, data: LoadedData) -> Path:
    return _create(save_dir, name, data, ym_to_turn(2021, 1))


def mature(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data, ym_to_turn(2016, 1))

    def step(game: Game) -> None:
        _ready(game)
        m21.build(game, "n28", "east_asia", 10_000)

    _edit(path, data, step)
    return path


def euv(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data, ym_to_turn(2021, 1))
    _edit(path, data, _ready)
    return path


MODES = {"nodes": nodes, "mature": mature, "euv": euv, "slots": mature}


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in MODES:
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    MODES[argv[1]](Path(argv[2]), argv[3], data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
