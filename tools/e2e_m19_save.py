"""Create saves for the M19 Playwright flows and tests (an e2e fixture tool). Never used by the
game.

- `holder <save dir> <name>`: a new game's company at stage 3 with $2B more cash and a
  permitted copper project (a definitive study and a permit): ready to found a mining
  subsidiary and move the project into it.
- `building <save dir> <name>`: `holder`, with a mine ordered on the project and a full crew of
  mining engineers; construction ends next month, so it ramps up and sells from then.
- `crash <save dir> <name>`: `building`, producing, with a price-crash event open (a critical
  event), unanswered.
- `accident <save dir> <name>`: `building`, producing, with an accident event open (a critical
  event), unanswered.

The project, the mine and its months are made by the engine's own functions (tst.balance.m19,
tst.sim.mining); only the months between are skipped.

Usage: uv run --project backend python tools/e2e_m19_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from tst.balance import fixtures, m18, m19
from tst.config import Settings
from tst.db.mappers import entry_to_row
from tst.db.repository import create_save, ledger_balances, load_state, open_session, run_turn
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.events.models import QueuedEvent
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.mining import formulas as mf
from tst.sim.mining.actions import BuildMine, StaffMine
from tst.sim.state import reach_stage, with_company, with_mine, with_queued

SEED = 19
TOP_UP = 200_000_000_000  # $2B
COMMODITY = "copper"


def holder(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = create_save(
        name, SEED, "ex_big_tech_founders", company_name="Ironbark", data=data, save_dir=save_dir
    )
    with open_session(path) as session, session.begin():
        before = load_state(session)
        state = with_company(before, reach_stage(before.player, 3, before.turn))
        state = m18.add_geologists(state, data, 12.0, 2)
        session.add(
            entry_to_row(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=1,
                    memo="E2E funding for mining",
                    debit=CASH,
                    credit=COMMON_EQUITY,
                    amount=TOP_UP,
                )
            )
        )
        sync_state(session, before, state)
    _write(path, data, lambda run: m19.permitted_project(run, COMMODITY))
    return path


def _write(path: Path, data: LoadedData, step: Callable[[m19.Miner], object]) -> None:
    """Run `step(run)` on the save's state in memory and write the result."""
    with open_session(path) as session, session.begin():
        before = load_state(session)
        run = m19.Miner(data, before, dict(ledger_balances(session)))
        step(run)
        state = replace(run.state, turn=before.turn)
        sync_state(session, before, state)
        for entry in run.posted:
            session.add(entry_to_row(replace(entry, turn=before.turn)))


def building(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = holder(save_dir, name, data)

    def step(run: m19.Miner) -> None:
        project = run.state.projects[-1]
        assert run.act(BuildMine(run.founder, project.id)) is not None, run.log
        mine = run.state.mines[-1]
        need = mf.staff_needed(mine.capacity_t, data.balance.mining.staff_per_kt)
        uid = m19.add_engineers(run, need, 12.0)
        assert run.act(StaffMine(run.founder, mine.id, uid)) is not None, run.log
        mine = run.state.mines[-1]
        t = run.state.turn
        # construction is skipped: paid at the revised cost, ready next month
        total = mine.hidden_total_cents
        run.state = with_mine(
            run.state,
            replace(
                mine,
                ordered_turn=t - 24,
                ready_turn=t + 1,
                revised_cents=total,
                capex_paid_cents=total,
            ),
        )
        run.posted.append(
            LedgerEntry.transfer(
                turn=t,
                company_id=mine.company_id,
                memo="Capex: construction (e2e fixture)",
                debit="1520_mineral_properties",
                credit=CASH,
                amount=total,
            )
        )

    _write(path, data, step)
    return path


def _producing(save_dir: Path, name: str, data: LoadedData, template: str, field: str) -> Path:
    path = building(save_dir, name, data)
    run_turn(path, data)  # construction ends: the mine produces
    run_turn(path, data)

    def step(run: m19.Miner) -> None:
        mine = run.state.mines[-1]
        t = run.state.turn
        run.state = with_mine(run.state, replace(mine, **{field: t + 1}))
        qid, ids = run.state.next_ids.take("queued")
        run.state = with_queued(
            replace(run.state, next_ids=ids),
            QueuedEvent(
                id=qid, company_id=1, template_id=template, due_turn=t + 1, source_event_id=None
            ),
        )

    _write(path, data, step)
    run_turn(path, data)  # the event is shown next month
    return path


def crash(save_dir: Path, name: str, data: LoadedData) -> Path:
    return _producing(save_dir, name, data, "mine_price_crash", "crash_turn")


def accident(save_dir: Path, name: str, data: LoadedData) -> Path:
    return _producing(save_dir, name, data, "mine_tailings_failure", "accident_turn")


MODES = {"holder": holder, "building": building, "crash": crash, "accident": accident}


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
        specialists=(("mining_engineer", 2, "Mining"), ("operations_manager", 1, "Mining")),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
