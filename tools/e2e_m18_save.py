"""Create saves for the M18 Playwright flows and tests (an e2e fixture tool). Never used by the
game.

- `explorer <save dir> <name>`: a new game's company at stage 3 with three geologists (geology
  and data 12) and $200M more cash: ready for a desk study, a licence and a survey.
- `sampled <save dir> <name>`: `explorer`, with a licence on a block holding copper in Latin
  America, surveyed and sampled for copper: ready to drill.
- `protest <save dir> <name>`: `explorer`, with a project whose definitive study is done and
  whose permit is pending, and a community protest (a critical event) open, unanswered.
- `permitted <save dir> <name>`: `explorer`, with a permitted project: ready to sell.

The project's stages are run by the engine's own functions (tst.sim.exploration); only the
months between them are skipped.

Usage: uv run --project backend python tools/e2e_m18_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.balance import fixtures, m18
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, ledger_balances, load_state, open_session, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.events.models import QueuedEvent
from tst.sim.exploration import pipeline as xp
from tst.sim.exploration.pipeline import TakeLicence
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, reach_stage, with_company, with_queued

SEED = 18
TOP_UP = 20_000_000_000  # $200M
SKILL = 12.0
REGION, COMMODITY = "latin_america", "copper"


def explorer(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = create_save(
        name, SEED, "ex_big_tech_founders", company_name="Lodestar", data=data, save_dir=save_dir
    )
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = with_company(before, reach_stage(before.player, 3, before.turn))
        state = m18.add_geologists(state, data, SKILL, 3)
        session.add(
            entry_to_row(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=1,
                    memo="E2E funding for exploration",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=TOP_UP,
                )
            )
        )
        sync_state(session, before, state)
    return path


def _block(state: GameState) -> int:
    for b in state.geo_blocks:
        if (
            b.region == REGION
            and b.true_commodity == COMMODITY
            and xp.holder_of(state, b.region, b.index) is None
        ):
            return b.index
    raise RuntimeError("no free copper block")


def _write(path: Path, data: LoadedData, step: object) -> None:
    """Run `step(run)` on the save's state in memory and write the result."""
    with open_session(path) as session, session.begin():
        before = load_state(session)
        run = m18.Run(data, before, dict(ledger_balances(session)))
        step(run)  # type: ignore[operator]
        state = replace(run.state, turn=before.turn)
        sync_state(session, before, state)
        for entry in run.posted:
            session.add(entry_to_row(replace(entry, turn=before.turn)))


def _project(run: m18.Run) -> xp.Project:
    block = _block(run.state)
    out = run.act(TakeLicence(run.founder, REGION, block))
    assert out is not None
    return run.state.projects[-1]


def sampled(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = explorer(save_dir, name, data)

    def step(run: m18.Run) -> None:
        p = _project(run)
        rng = RngFactory(run.state.save_meta.master_seed)
        p = xp.survey_result(
            run.state, replace(p, commodity=COMMODITY), rng, data.balance, data.game_data
        )
        p = replace(p, commodity=COMMODITY, reading=p.reading if p.reading != "none" else "weak")
        p = xp.sample_result(run.state, p, rng, data.balance, data.game_data)
        run.state = xp.with_project(run.state, p)

    _write(path, data, step)
    return path


def _studied(run: m18.Run, data: LoadedData) -> xp.Project:
    p = _project(run)
    rng = RngFactory(run.state.save_meta.master_seed)
    b, d = data.balance, data.game_data
    p = replace(p, commodity=COMMODITY, reading="strong", kind="hard_rock")
    p = xp.sample_result(run.state, p, rng, b, d)
    run.state = xp.with_project(run.state, p)
    holes = tuple(xp.drill_hole(run.state, p, n, rng, b, d) for n in range(1, 41))
    run.state = replace(run.state, holes=(*run.state.holes, *holes))
    p = xp.estimate_result(run.state, p, rng, b, d)
    p = xp.study_result(run.state, p, "definitive", rng, b, d)
    run.state = xp.with_project(run.state, p)
    return p


def protest(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = explorer(save_dir, name, data)

    def step(run: m18.Run) -> None:
        p = _studied(run, data)
        t = run.state.turn
        p = replace(
            p,
            stage="permitting",
            permit_start=t,
            hidden_due_turn=t + 36,
            protest_turn=t + 1,
            protests=1,
        )
        run.state = xp.with_project(run.state, p)
        qid, ids = run.state.next_ids.take("queued")
        run.state = with_queued(
            replace(run.state, next_ids=ids),
            QueuedEvent(
                id=qid,
                company_id=1,
                template_id="community_blockade",
                due_turn=t + 1,
                source_event_id=None,
            ),
        )

    _write(path, data, step)
    run_turn(path, data)  # the protest is shown next month
    return path


def permitted(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = explorer(save_dir, name, data)

    def step(run: m18.Run) -> None:
        p = _studied(run, data)
        t = run.state.turn
        p = replace(p, status="permitted", permit_start=t, hidden_due_turn=t, permit_turn=t)
        run.state = xp.with_project(run.state, p)

    _write(path, data, step)
    return path


MODES = {"explorer": explorer, "sampled": sampled, "protest": protest, "permitted": permitted}


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in MODES:
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    path = MODES[argv[1]](Path(argv[2]), argv[3], data)
    # M23c: a believable stage-3 team and a knowledge record of every employee (playtest 5)
    fixtures.finish(path, data, team=True, specialists=(("data_scientist", 1, "Exploration"),))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
