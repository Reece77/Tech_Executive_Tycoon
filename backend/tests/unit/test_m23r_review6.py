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


# --- Finding 2's check on mines and refineries ------------------------------------------------


def test_a_subsidiarys_mine_counts_the_crew_the_founder_gives_it(loaded: LoadedData) -> None:
    """The matching gap on mines: a player unit put on a subsidiary's mine moves to the mine's
    owner with its people, so the mine counts its crew and the owner pays it."""
    from tst.sim.facilities import lifecycle
    from tst.sim.mining.actions import FoundSubsidiary, StaffMine, TransferAsset

    run = m19.miner(loaded, 7)
    mine = m19.build(run, "copper")
    before = {c.id for c in run.state.companies}
    assert run.act(FoundSubsidiary(run.founder, "Copper Co", mine.region, 50_000_000_000)), run.log
    (sub,) = {c.id for c in run.state.companies} - before
    assert run.act(TransferAsset(run.founder, sub, facility_id=mine.id)), run.log
    assert run.act(StaffMine(run.founder, mine.id, None)), run.log
    need = len(lifecycle.staff_of(run.state, run.state.facility(mine.id), loaded.balance))  # type: ignore[arg-type]
    assert need == 0
    uid = m19.add_engineers(run, 40, 12.0)  # the player's
    assert run.act(StaffMine(run.founder, mine.id, uid)), run.log
    f = run.state.facility(mine.id)
    assert f is not None and f.company_id == sub and f.unit_id == uid
    unit = run.state.unit(uid)
    assert unit is not None and unit.company_id == sub
    crew = lifecycle.staff_of(run.state, f, loaded.balance)
    assert len(crew) == 40 and all(e.company_id == sub for e in crew)


def test_the_founder_staffs_and_sells_a_subsidiarys_refinery() -> None:
    """The matching gap on refineries: a refinery transferred to a subsidiary is staffed and sold
    by the founder; the proceeds are the owner's."""
    from tests.unit.test_m23a_group import _energy, found
    from tst.balance import m20
    from tst.sim.actions.facilities import SellFacility, StaffFacility
    from tst.sim.ledger import CASH

    game = m20.game_at(1, m20.ym_to_turn(2015, 1))
    fid = m20.build(game, "silicon_smelter", "north_america", 25_000)
    m20.play(game, 2)
    sub = found(game, "Smelter Co")
    _energy(game)
    from tst.sim.mining.actions import TransferAsset

    assert game.act(TransferAsset(game.founder_id, sub, facility_id=fid)), dict(game.refused)
    _energy(game)
    assert game.act(StaffFacility(game.founder_id, fid, None)), dict(game.refused)
    sub_cash, player_cash = game.balances.get((sub, CASH), 0), game.cash
    _energy(game)
    assert game.act(SellFacility(game.founder_id, fid)), dict(game.refused)
    f = game.state.facility(fid)
    assert f is not None and f.status == "closed"
    assert game.balances.get((sub, CASH), 0) > sub_cash and game.cash == player_cash
