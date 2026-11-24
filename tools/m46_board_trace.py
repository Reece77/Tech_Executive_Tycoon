"""M46: why the V6 save's board removes its founder after December 2039 (CI only).

Plays research_heavy (V6's script) on seed 1 in memory to December 2039, continues in dynasty
mode as tests/integration/test_v6_perf.py does, and plays on with no actions, printing the
board's inputs each month from 2038: growth and runway points, every voting seat's confidence
and months below the removal line, cash, MRR and the critical events.

    uv run --project backend python tools/m46_board_trace.py [--turns 390] [key=value ...]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m46_overrides import BACKEND, overridden_data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=390)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--strategy", default="research_heavy")
    parser.add_argument("--from-turn", type=int, default=336)
    parser.add_argument("settings", nargs="*")
    args = parser.parse_args()
    os.environ.setdefault("TST_LLM_ADAPTER", "mock")
    sys.path.insert(0, str(BACKEND))
    with overridden_data(args.settings) as root:
        from tst.balance.game import PLAYER, start_game
        from tst.balance.report import SCENARIO
        from tst.balance.strategies_v2 import STRATEGIES
        from tst.balance.strategies_v3 import V3
        from tst.loader import load_all
        from tst.sim.calendar import turn_to_ym
        from tst.sim.dynasty.mode import ContinueDynasty, at_standard_end
        from tst.sim.finance import board
        from tst.sim.finance import formulas as f
        from tst.sim.finance.captable import mrr_now_and_then
        from tst.sim.markets_public.describe import founder_protected, public_patience
        from tst.sim.org.executives import cfo_confidence

        loaded = load_all(root / "data")
        game = start_game(loaded, args.seed, SCENARIO)
        script = {**STRATEGIES, **V3}[args.strategy]
        bal, data = loaded.balance, loaded.game_data
        for _ in range(args.turns):
            state = game.state
            if state.ended:
                print(f"ENDED at turn {state.turn}: {state.save_meta.game_state}")
                break
            if at_standard_end(state, bal):
                founder = state.founder_of(PLAYER)
                game.act(ContinueDynasty(founder.id if founder is not None else 1))
            if state.turn < 360:
                script(game)
            game.turn()
            s = game.state
            if s.turn - 1 < args.from_turn and s.turn % 12:
                continue
            y, m = turn_to_ym(s.turn - 1)
            now, then = mrr_now_and_then(s, PLAYER, bal)
            runway = board.projected_runway(s, PLAYER, game.cash, bal, data)
            growth = board.growth_term(s, PLAYER, bal)
            seats = [
                f"{x.confidence:.0f}/{x.months_below}"
                for x in s.board(PLAYER)
                if x.votes and x.confidence is not None
            ]
            crit = [e.template_id for e in s.open_events(PLAYER) if e.severity == "critical"]
            print(
                f"{y}-{m:02d} t{s.turn - 1} stage {s.player.stage} cash ${game.cash / 1e8:.1f}M "
                f"MRR ${now / 1e8:.2f}M (6m ago ${then / 1e8:.2f}M) growth {growth:+.1f} "
                f"runway {runway} ({f.runway_points(runway, bal.board):+.1f}) "
                f"cfo {cfo_confidence(s, PLAYER, bal):+.2f} "
                f"patience {public_patience(s, PLAYER, bal):+.1f} "
                f"protected {founder_protected(s, PLAYER)} seats {seats} "
                f"staff {len(s.staff(PLAYER))} critical {crit} state {s.save_meta.game_state}",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
