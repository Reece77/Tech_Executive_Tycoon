"""Build the V6 save (docs/formulas.md 30.7 V6, M15a; a fixture tool, never used by the game):
research_heavy (or, M23b's V6 extended, `--strategy full_integrator`) played through the normal
save path (every action and month goes through
`repository`, as tools/quickstart_saves.py) from January 2010 for `--turns` months (360: to
December 2039) on `--seed`. The scripts' energy top-ups edit the state between actions;
they are written to the save before the next action. An existing save of the name is replaced.

    uv run --project backend python tools/v6_save.py <save dir> <name> [--turns 360] [--seed 1]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
STRATEGY = "research_heavy"


def build(save_dir: Path, name: str, turns: int, seed: int, strategy: str = STRATEGY) -> Path:
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    sys.path.insert(0, str(BACKEND))
    from tst.balance.game import PLAYER, Game
    from tst.balance.report import SCENARIO
    from tst.balance.strategies_v2 import STRATEGIES
    from tst.balance.strategies_v3 import V3
    from tst.db import repository
    from tst.db.state_io import sync_state
    from tst.llm.offline import MockLLMAdapter
    from tst.loader import load_all
    from tst.sim.actions import Action, ChooseEvent
    from tst.sim.errors import SimError

    data = load_all(BACKEND / "data")

    class SaveGame(Game):
        """A balance Game whose actions and months go through a save file."""

        path: Path
        written: object

        def _write_edits(self) -> None:
            if self.state is self.written:
                return
            with repository.open_session(self.path) as session, session.begin():
                sync_state(session, repository.load_state(session), self.state)

        def act(self, action: Action) -> bool:
            self._write_edits()
            try:
                repository.run_action(self.path, data, action)
            except SimError:
                self.refused[action.kind] += 1
                self._reload()
                return False
            self._reload()
            return True

        def turn(self) -> None:
            for event in self.state.open_events(PLAYER):
                if event.severity == "critical" and event.status == "open":
                    self.act(ChooseEvent(self.founder_id, event.id, event.choices[0].key))
            self._write_edits()
            result = repository.run_turn(self.path, data, adapter=MockLLMAdapter())
            self.snapshots.append(result.snapshot.for_company(PLAYER))
            self.last_product_months = result.product_months  # M23b: the v3 scripts read it
            self._reload()

        def _reload(self) -> None:
            with repository.open_session(self.path) as session:
                self.state = repository.load_state(session)
                self.balances = dict(repository.current_balances(session, self.state.turn))
            self.written = self.state

    old = repository.save_path(save_dir, name)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{old}{suffix}").unlink(missing_ok=True)
    path = repository.create_save(
        name, seed, SCENARIO, company_name="Balance Co", data=data, save_dir=save_dir
    )
    game = SaveGame.__new__(SaveGame)
    with repository.open_session(path) as session:
        state = repository.load_state(session)
        balances = dict(repository.current_balances(session, state.turn))
    Game.__init__(game, data, state, balances)
    game.path = path
    game.written = state
    script = {**STRATEGIES, **V3}[strategy]
    started = time.perf_counter()
    for _ in range(turns):
        if game.state.ended:
            raise SystemExit(f"the game ended at turn {game.state.turn}")
        script(game)
        game.turn()
        if game.state.turn % 12 == 0:
            print(
                f"turn {game.state.turn}: stage {game.state.player.stage}, staff "
                f"{len(game.state.staff(PLAYER))}, {time.perf_counter() - started:.0f} s",
                flush=True,
            )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("save_dir", type=Path)
    parser.add_argument("name")
    parser.add_argument("--turns", type=int, default=360)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--strategy", default=STRATEGY, help="M23b: V6 extended")
    args = parser.parse_args()
    args.save_dir.mkdir(parents=True, exist_ok=True)
    print(build(args.save_dir.resolve(), args.name, args.turns, args.seed, args.strategy))
    return 0


if __name__ == "__main__":
    sys.exit(main())
