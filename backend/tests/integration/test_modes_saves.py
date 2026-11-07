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


def test_sandbox_rules(tmp_path: Path, loaded: LoadedData) -> None:
    """30.2: the board cannot remove the founder, eras can be seeded, and the save is kept
    out of the scores on the Saves list."""

    from tst.db import saves
    from tst.sim.modes.models import GameMode
    from tst.sim.research.levels import historical_turn, scheduled_turn
    from tst.sim.rng import RngFactory

    data = loaded.game_data
    spec = ModeSpec(kind="sandbox", start_year=2011, eras="seeded")
    path = create_save(
        "sb2",
        5,
        "funded_spinout",
        company_name="Kestrel",
        data=loaded,
        save_dir=tmp_path,
        mode=spec,
    )
    listed = saves.describe(path)
    assert listed.mode == "sandbox" and listed.score is None
    with open_session(path) as session:
        state = load_state(session)
    # eras: a later historical era moves within its spread; an earlier one does not
    era = next(
        e for e in data.eras.eras if e.window is None and historical_turn(e) > state.turn + 30
    )
    index = data.eras.eras.index(era)
    seeded = scheduled_turn(
        era,
        index,
        RngFactory(5),
        seeded_after=state.turn,
        spread=loaded.balance.sandbox.era_spread_months,
    )
    assert abs(seeded - historical_turn(era)) <= loaded.balance.sandbox.era_spread_months
    assert isinstance(state.mode, GameMode)


def test_a_sandbox_board_never_removes_the_founder(loaded: LoadedData) -> None:
    """The board collapse that removes a founder after a Series B (test_board) does not in a
    Sandbox (spec 17)."""
    from dataclasses import replace as dc_replace

    from tests.helpers import make_person, with_employee
    from tests.unit.test_board import board_after, months
    from tst.sim.modes.models import GameMode

    state = board_after(loaded, "b")
    state = with_employee(loaded, state, make_person(loaded, 2), 20_000_000)
    sandbox = dc_replace(state, mode=GameMode(kind="sandbox"))
    out, templates = months(loaded, sandbox, 24, 0)
    assert not out.ended and "founder_removed" not in templates
    out, _ = months(loaded, state, 24, 0)
    assert out.save_meta.game_state == "founder_removed"  # the same board in a campaign
