"""Create and edit saves for the M24 Playwright flows (an e2e fixture tool). Never used by
the game.

- `fresh <save dir> <name>`: Kestrel, a funded spinout with $50M of extra cash, at turn 0.
- `drain <save dir> <name>`: the founder's energy this month is spent (as a month of
  interviews and searches would leave it).
- `december <save dir> <name>`: M13's listed Kestrel (tools/e2e_m13_save.py `listed`) played
  on, every event answered with its first choice, to a December, so this month's end makes
  the foundation's first grants.
- `scandal <save dir> <name>`: a lobbying scandal breaks in North America this month, as the
  engine's draw would make it (formulas.md 32.5): Continue shows its critical event.
- `over <save dir> <name>`: `fresh`, played a month, then the game ended (bankrupt), so the
  Game over screen shows the legacy score.

Usage: uv run --project backend python tools/e2e_m24_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, existing_save_path, load_state, open_session, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.founder import influence
from tst.sim.founder.models import Influence
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.state import GameState, influence_of, with_influence, with_person_state

SEED = 5
EXTRA_CASH = 50_000_000_00
DECEMBER = 11


def _edit(path: Path, change) -> GameState:  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        after = change(before)
        sync_state(session, before, after)
    return after


def fresh(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name="Kestrel", data=data, save_dir=save_dir
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
    return path


def drain(path: Path) -> None:
    def change(state: GameState) -> GameState:
        founder = state.founder_of(state.player.id)
        assert founder is not None
        return with_person_state(state, replace(state.person_state(founder.id), energy=0))

    _edit(path, change)


def december(save_dir: Path, name: str, data: LoadedData) -> Path:
    from e2e_m13_save import answer_open, eligible, play_chain

    path = eligible(save_dir, name, data)
    state = play_chain(path, data)
    while state.turn % 12 != DECEMBER:
        run_turn(path, data)
        answer_open(path, data)
        with open_session(path) as session:
            state = load_state(session)
    return path


def scandal(path: Path, data: LoadedData) -> None:
    entries: list[LedgerEntry] = []

    def change(state: GameState) -> GameState:
        record = influence_of(state, 1, "north_america") or Influence(1, "north_america")
        state = with_influence(state, replace(record, value=max(record.value, 30.0)))
        state, posted, _ = influence.break_scandal(
            state, 1, "north_america", False, data.balance, data.game_data
        )
        entries.extend(posted)
        return state

    _edit(path, change)
    with open_session(path) as session, session.begin():
        session.add_all(entry_to_row(e) for e in entries)


def over(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = fresh(save_dir, name, data)
    run_turn(path, data)
    _edit(
        path,
        lambda s: replace(
            s, save_meta=replace(s.save_meta, game_state="bankrupt", ended_turn=s.turn - 1)
        ),
    )
    return path


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    if mode == "fresh":
        path = fresh(save_dir, name, data)
    elif mode == "december":
        path = december(save_dir, name, data)
    elif mode == "over":
        path = over(save_dir, name, data)
    elif mode in ("drain", "scandal"):
        path = existing_save_path(save_dir, name)
        drain(path) if mode == "drain" else scandal(path, data)
    else:
        print(__doc__)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
