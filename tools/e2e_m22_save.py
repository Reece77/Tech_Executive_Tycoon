"""Create saves for the M22 Playwright flows and tests (an e2e fixture tool). Never used by the
game.

- `chips <save dir> <name>`: October 2022, an AI-accelerator seller (tst.balance.m22's target-2
  company: 30% of revenue in China): the World screen shows October's chip rules, the product
  is closed in China, and a compliant variant or a licence request reopens it.
- `gallium <save dir> <name>`: November 2024, the same company: after one Continue it is
  December 2024 and China's ban on gallium to the US raises the chips' gallium premium.
- `influence <save dir> <name>`: October 2022, the chip company with influence 100 in North
  America and a seed whose December 2022 licence draw is approved at that influence (it would
  be denied at 0): request a licence for China and Continue twice.

Usage: uv run --project backend python tools/e2e_m22_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.balance import fixtures, m22
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, load_state, open_session
from tst.db.state_io import read_meta, sync_state
from tst.loader import LoadedData, load_all
from tst.sim.calendar import ym_to_turn
from tst.sim.founder.models import Influence
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.rng import RngFactory
from tst.sim.state import with_influence

SEED = 22
EXTRA_CASH = 200_000_000_000  # $2B
APPROVAL = 0.25  # us_oct_2022's base approval (export_controls.yaml)
INFLUENCE = 100.0


def _create(save_dir: Path, name: str, data: LoadedData, turn: int, seed: int = SEED) -> Path:
    path = create_save(
        name, seed, "funded_spinout", company_name="Lattice", data=data, save_dir=save_dir
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
        state, _ = m22.accelerator_state(replace(before, turn=turn), data, seed)
        sync_state(session, before, state)
        read_meta(session).current_turn = turn
    return path


def chips(save_dir: Path, name: str, data: LoadedData) -> Path:
    return _create(save_dir, name, data, ym_to_turn(2022, 10))


def gallium(save_dir: Path, name: str, data: LoadedData) -> Path:
    return _create(save_dir, name, data, ym_to_turn(2024, 11))


def approving_seed() -> int:
    """A seed whose first licence (id 1), decided in December 2022, is approved at influence
    100 and denied at 0 (licence.decision_months after an October request)."""
    lo, hi = APPROVAL, APPROVAL * (1 + 0.3 * INFLUENCE / 100)
    decide = ym_to_turn(2022, 12)
    for seed in range(1, 1000):
        u = float(RngFactory(seed).stream(decide, "geopolitics", 1, 1).random())
        if lo <= u < hi:
            return seed
    raise RuntimeError("no seed")


def influence(save_dir: Path, name: str, data: LoadedData) -> Path:
    seed = approving_seed()
    path = _create(save_dir, name, data, ym_to_turn(2022, 10), seed)
    with open_session(path) as session, session.begin():
        before = load_state(session)
        after = with_influence(before, Influence(1, "north_america", INFLUENCE))
        sync_state(session, before, after)
    return path


MODES = {"chips": chips, "gallium": gallium, "influence": influence}


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in MODES:
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    path = MODES[argv[1]](Path(argv[2]), argv[3], data)
    # M23c: a believable stage-3 team and a knowledge record of every employee (playtest 5)
    fixtures.finish(
        path,
        data,
        team=True,
        stage=3,
        specialists=(("chip_designer", 3, "Chip design"), ("hardware_engineer", 2, "Chip design")),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
