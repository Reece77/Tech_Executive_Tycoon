"""Create the save for the M43 Playwright flow (an e2e fixture tool). Never used by the game.

- `group <save dir> <name>`: full_integrator's chain group (software, devices, its own chips
  and fab, lithium and wafers: at least four industries) played by the engine from January 2010
  to December 2039. Unlike the other fixture tools' "one entry for the months in memory", the
  group's own ledger entries (its months' and its actions') are written as a played save has
  them, so the conglomerate view reads thirty years of books; every other company's months are
  one entry.
  The January 2039 letter (about 2038) is written through the event service's own path with the
  mock adapter. Takes a few minutes.

Usage: uv run --project backend python tools/e2e_m43_save.py group <save dir> <name>
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from tst.config import Settings
from tst.db.events import write_pending
from tst.db.mappers import entry_to_row
from tst.db.models import LLMTextRow
from tst.db.repository import create_save, ledger_balances, open_session
from tst.db.state_io import insert_entries, load_state, read_meta, sync_state
from tst.llm.offline import MockLLMAdapter
from tst.loader import LoadedData, load_all
from tst.sim.ledger import COMMON_EQUITY, LedgerEntry, LedgerLine, apply_entries
from tst.sim.state import GameState

SEED: Final = 43
DEC_2039: Final = 359  # the save opens in December 2039 (a 2039 save; the campaign runs on)
DEC_2038: Final = 347  # the December whose turn queues the January 2039 letter
LETTER_YEAR: Final = 2038


def _write(
    path: Path,
    state: GameState,
    kept: list[LedgerEntry],
    balances: Mapping[tuple[int, str], int],
    start: Mapping[tuple[int, str], int],
) -> None:
    """The state, the group's own entries, and one entry per company for the rest."""
    rest = dict(balances)
    for key, amount in apply_entries({}, kept).items():
        rest[key] = rest.get(key, 0) - amount
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, state)
        read_meta(session).current_turn = state.turn
        insert_entries(session, kept)
        by_company: dict[int, list[LedgerLine]] = {}
        for key in sorted(set(rest) | set(start)):
            diff = rest.get(key, 0) - start.get(key, 0)
            if diff:
                by_company.setdefault(key[0], []).append(LedgerLine(key[1], diff))
        for cid, lines in sorted(by_company.items()):
            gap = sum(x.amount for x in lines)
            if gap:
                lines.append(LedgerLine(COMMON_EQUITY, -gap))
            if len(lines) >= 2:
                entry = LedgerEntry(state.turn - 1, cid, "E2E: the fixture's months", tuple(lines))
                session.add(entry_to_row(entry))
        session.add(
            LLMTextRow(
                company_id=state.player.id,
                turn=DEC_2038,
                kind="letter",
                ref_id=LETTER_YEAR,
                status="pending",
            )
        )


def group(save_dir: Path, name: str, data: LoadedData) -> Path:
    from tst.balance import fixtures
    from tst.balance.game import Game, group_ids
    from tst.balance.strategies_v3 import V3
    from tst.sim.setup import DEFAULT_FOUNDER, new_game

    path = create_save(
        name, SEED, "ex_big_tech_founders", company_name="Balance Co", data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    state, entries = new_game(
        save_name=name,
        master_seed=SEED,
        scenario=data.game_data.scenario("ex_big_tech_founders"),  # type: ignore[arg-type]
        difficulty="standard",
        company_name="Balance Co",
        founder=DEFAULT_FOUNDER,
        balance=data.balance,
        data=data.game_data,
    )
    kept: list[LedgerEntry] = []

    class Keeping(Game):
        """A balance Game that keeps every group entry, its actions' and its months'."""

        def _keep_group_lines(self, entries: Sequence[LedgerEntry]) -> None:
            mine = group_ids(self.state)
            kept.extend(e for e in entries if e.company_id in mine)
            super()._keep_group_lines(entries)

    game = Keeping(data, state, apply_entries({}, entries))
    script = V3["full_integrator"]
    while game.state.turn < DEC_2039 and not game.state.ended:
        script(game)
        game.turn()
    if game.state.ended:
        raise SystemExit(f"the game ended at {game.state.turn}: try another seed")
    _write(path, game.state, kept, game.balances, start)
    write_pending(path, data, adapter=MockLLMAdapter())
    fixtures.finish(path, data, team=True)
    return path


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    makers = {"group": group}
    if mode not in makers:
        print(__doc__)
        return 2
    print(makers[mode](save_dir, name, data))
    return 0


if __name__ == "__main__":
    import e2e_cache  # M59: CI keeps the saves it builds (tools/e2e_cache.py)

    sys.exit(e2e_cache.run(__file__, sys.argv[1:], lambda: main(sys.argv[1:])))
