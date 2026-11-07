"""M15b sub-tasks 2-3: a Sandbox save starts in its year, keeps its mode through a reload, and
replays to the same state (ADR-0014)."""

from __future__ import annotations

from pathlib import Path

from tst.db.repository import (
    create_save,
    open_session,
    read_session,
    read_state,
    replay_save,
    run_turn,
)
from tst.db.state_io import load_state
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.modes.world import ModeSpec


def test_a_sandbox_save_starts_in_its_year_and_replays(tmp_path: Path, loaded: LoadedData) -> None:
    spec = ModeSpec(kind="sandbox", start_year=2012, cash_cents=2_000_000_00, rivals="half")
    path = create_save(
        "sb", 5, "funded_spinout", company_name="Kestrel", data=loaded, save_dir=tmp_path, mode=spec
    )
    with open_session(path) as session:
        state = load_state(session)
    assert state.turn == ym_to_turn(2012, 1)
    assert state.mode is not None and state.mode.kind == "sandbox" and state.mode.rivals == "half"
    run_turn(path, loaded)
    run_turn(path, loaded)
    copy = replay_save(path, tmp_path / "b", "copy", loaded)
    with read_session(path) as a, read_session(copy) as b:
        assert read_state(a).companies == read_state(b).companies
