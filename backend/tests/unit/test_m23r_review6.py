"""M23r (Codex review 6; docs/tasks/M23r-review-6-fixes.md): each finding's regression test, written
first and seen failing on m23a-done."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tst.balance import m19
from tst.loader import LoadedData
from tst.sim.ledger import EXPLORATION
from tst.sim.mining.actions import BuildMine, CloseMine
from tst.sim.state import GameState, with_mine


def reload(state: GameState, data: LoadedData, tmp_path: Path, name: str = "reload") -> GameState:
    """`state` written into a fresh save and read back cold (a new session)."""
    from tst.db.repository import create_save, load_state, open_session
    from tst.db.state_io import sync_state

    path = create_save(
        name, 1, "funded_spinout", company_name="Reload", data=data, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        sync_state(session, load_state(session), state)
    with open_session(path) as session:
        return load_state(session)


# --- Finding 1: depletion across mine lifetimes ------------------------------------------------


def test_repeated_rebuilds_deplete_the_deposit_once(loaded: LoadedData, tmp_path: Path) -> None:
    """Codex's reproduction carried to four lifetimes, with a cold reload before each rebuild: the
    deposit's ore extracted plus the ore left always equals its original tonnage, and the
    project's exploration spend is capitalized once, with the first mine."""
    run = m19.miner(loaded, 7)
    mine = m19.build(run, "copper")
    original = mine.hidden_ore_mt
    project_spend = mine.moved_cents
    assert project_spend > 0
    exploration = run.balances.get((m19.PLAYER, EXPLORATION), 0)
    for lifetime, share in enumerate((0.1, 0.25, 0.45), start=2):
        now = m19.mine_of(run, mine.id)
        extracted = original * share  # the deposit's cumulative extraction so far
        run.state = with_mine(run.state, replace(now, ore_mined_mt=extracted))
        assert run.act(CloseMine(run.founder, mine.id)) is not None, run.log
        run.state = reload(run.state, loaded, tmp_path, f"life{lifetime}")
        assert run.act(BuildMine(run.founder, now.project_id)) is not None, run.log
        mine = run.state.mines[-1]
        assert mine.ore_mined_mt == pytest.approx(extracted), lifetime
        assert mine.ore_mined_mt + mine.hidden_ore_left_mt == pytest.approx(original), lifetime
        lifetimes = [m for m in run.state.mines if m.project_id == now.project_id]
        assert len(lifetimes) == lifetime
        assert sum(m.moved_cents for m in lifetimes) == project_spend
        assert run.balances.get((m19.PLAYER, EXPLORATION), 0) == exploration
