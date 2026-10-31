"""Quick-start saves for Reece's playtests (M7c sub-task 5; a tool, not a game feature).

Plays the balance runner's strategies headless on seed 1 through the normal save path (every
action and month goes through `repository`, so the saves are ordinary games) and leaves two
saves in the save folder, shown in the Saves screen:

- `quick-stage2`: the steady strategy at turn 36 (January 2013);
- `quick-stage3`: blitzscale with its second product, at the first month of stage 3, so M8's
  divisions and executive seats can be tried at once.

An existing save of the same name is replaced.

    make quickstart-saves
    uv run --project backend python tools/quickstart_saves.py [--save-dir saves]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
SEED = 1
STAGE2_TURN = 36
STAGE3_BY = 120  # turns of blitzscale allowed to reach stage 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--save-dir", type=Path, default=None)
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "template")
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)

    from tst.balance.game import PLAYER, Game
    from tst.balance.strategies import blitzscale, steady
    from tst.config import Settings
    from tst.db import repository
    from tst.llm.offline import TemplateAdapter
    from tst.loader import load_all
    from tst.sim.actions import Action, ChooseEvent
    from tst.sim.errors import SimError

    settings = Settings()
    data = load_all(settings.data_dir)
    save_dir = (args.save_dir or settings.resolved_save_dir()).resolve()
    save_dir.mkdir(parents=True, exist_ok=True)

    class SaveGame(Game):
        """A balance Game whose actions and months go through a save file."""

        path: Path

        def act(self, action: Action) -> bool:
            try:
                repository.run_action(self.path, data, action)
            except SimError:
                self.refused[action.kind] += 1
                return False
            self._reload()
            return True

        def turn(self) -> None:
            for event in self.state.open_events(PLAYER):
                if event.severity == "critical" and event.status == "open":
                    self.act(ChooseEvent(self.founder_id, event.id, event.choices[0].key))
            result = repository.run_turn(self.path, data, adapter=TemplateAdapter())
            self.snapshots.append(result.snapshot.for_company(PLAYER))
            self._reload()

        def _reload(self) -> None:
            with repository.open_session(self.path) as session:
                self.state = repository.load_state(session)
                self.balances = dict(repository.current_balances(session, self.state.turn))

    def start(name: str) -> SaveGame:
        old = repository.save_path(save_dir, name)
        for suffix in ("", "-wal", "-shm"):
            Path(f"{old}{suffix}").unlink(missing_ok=True)
        path = repository.create_save(
            name,
            SEED,
            "ex_big_tech_founders",
            company_name="Quick Co" if name.endswith("2") else "Scale Co",
            data=data,
            save_dir=save_dir,
        )
        with repository.open_session(path) as session:
            state = repository.load_state(session)
            balances = dict(repository.current_balances(session, state.turn))
        game = SaveGame.__new__(SaveGame)
        Game.__init__(game, data, state, balances)
        game.path = path
        return game

    stage2 = start("quick-stage2")
    while stage2.state.turn < STAGE2_TURN and not stage2.state.ended:
        steady(stage2)
        stage2.turn()
    print(
        f"quick-stage2: {stage2.path} at turn {stage2.state.turn}, stage {stage2.state.player.stage}"
    )

    stage3 = start("quick-stage3")
    while stage3.state.player.stage < 3 and stage3.state.turn < STAGE3_BY:
        if stage3.state.ended:
            print("quick-stage3: the game ended before stage 3", file=sys.stderr)
            return 1
        blitzscale(stage3)
        stage3.turn()
    products = [p.name for p in stage3.state.company_products(PLAYER)]
    print(
        f"quick-stage3: {stage3.path} at turn {stage3.state.turn}, stage "
        f"{stage3.state.player.stage}, products {products}"
    )
    return 0 if stage3.state.player.stage >= 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
