"""M23a sub-task 2 (formulas.md 35.2-35.3, 38.6; Codex review 5 findings 2 and 6): depletion and
capitalized exploration are the deposit's, across mine lifetimes; a fab's fixed running cost
follows its lifecycle, not its staffing."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.balance import m19, m21
from tst.loader import LoadedData
from tst.sim.ledger import EXPLORATION
from tst.sim.mining.actions import BuildMine, CloseMine
from tst.sim.state import with_mine


def test_an_exhausted_deposit_rebuilt_keeps_its_depletion_and_capitalizes_nothing_again(
    loaded: LoadedData,
) -> None:
    """Codex's reproduction: the deposit mined to its full tonnage, the mine closed by choice and
    rebuilt on the same project: the new mine has nothing left to mine, and the project's
    exploration spend is not credited to 6600 a second time."""
    run = m19.miner(loaded, 7)
    mine = m19.build(run, "copper")
    m19.run_until(run, mine.ready_turn + 2)
    now = m19.mine_of(run, mine.id)
    run.state = with_mine(run.state, replace(now, ore_mined_mt=now.hidden_ore_mt))
    exploration = run.balances.get((m19.PLAYER, EXPLORATION), 0)
    assert run.act(CloseMine(run.founder, mine.id)) is not None, run.log
    out = run.act(BuildMine(run.founder, now.project_id))
    if out is not None:  # a rebuild after a chosen closure inherits the deposit's depletion
        rebuilt = run.state.mines[-1]
        assert rebuilt.id != mine.id and rebuilt.project_id == now.project_id
        assert rebuilt.hidden_ore_left_mt == 0
        assert rebuilt.moved_cents == 0
    assert run.balances.get((m19.PLAYER, EXPLORATION), 0) == exploration


def test_a_mine_closed_by_choice_rebuilds_on_what_is_left(loaded: LoadedData) -> None:
    run = m19.miner(loaded, 7)
    mine = m19.build(run, "copper")
    m19.run_until(run, mine.ready_turn + 6)
    now = m19.mine_of(run, mine.id)
    assert 0 < now.ore_mined_mt < now.hidden_ore_mt
    assert run.act(CloseMine(run.founder, mine.id)) is not None, run.log
    exploration = run.balances.get((m19.PLAYER, EXPLORATION), 0)
    assert run.act(BuildMine(run.founder, now.project_id)) is not None, run.log
    rebuilt = run.state.mines[-1]
    assert rebuilt.ore_mined_mt == pytest.approx(now.ore_mined_mt)
    assert rebuilt.hidden_ore_left_mt == pytest.approx(now.hidden_ore_left_mt)
    assert rebuilt.moved_cents == 0  # the project's spend was capitalized with the first mine
    assert run.balances.get((m19.PLAYER, EXPLORATION), 0) == exploration


def test_a_depleted_or_sold_project_cannot_be_rebuilt(loaded: LoadedData) -> None:
    from tst.sim.mining.actions import closed

    run = m19.miner(loaded, 7)
    mine = m19.build(run, "copper")
    m19.run_until(run, mine.ready_turn + 2)
    run.state = closed(run.state, m19.mine_of(run, mine.id), "depleted")
    assert run.act(BuildMine(run.founder, mine.project_id)) is None
    assert any("exhausted" in k for k in run.log), run.log


# --- Finding 6: a fab's fixed running cost follows its lifecycle --------------------------------


def test_a_live_unstaffed_fab_still_pays_its_fixed_running_cost() -> None:
    """Codex's reproduction: a completed 28 nm fab with its crew removed is still live; its fixed
    cost is fab.fixed_share of paid capex a year (38.6), while variable costs stop with output."""
    lg = m21.loaded()
    fb = lg.balance.fab
    game = m21.game_at(1, m21.ym_to_turn(2016, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000)
    f = game.state.facility(fid)
    assert f is not None
    game.notes.pop(f"staff:{fid}")
    game.state = m21.with_facility(game.state, replace(f, unit_id=None))
    m21.play(game, 2)
    f = game.state.facility(fid)
    fab = m21.fm.fab_of(game.state, fid)
    assert f is not None and fab is not None and f.status == "live"
    m = fab.month
    assert m is not None and m.available == 0 and m.run == 0
    from fractions import Fraction

    expected = round(Fraction(f.capex_paid_cents) * Fraction(str(fb.fixed_share)) / 12)
    assert m.fixed_cents == expected > 0
    assert m.materials_cents == 0 and m.power_cents == 0


def test_a_fab_under_conversion_pays_its_fixed_cost_on_the_old_capex() -> None:
    """Explicit conversion treatment (M23a decision): offline while converting, a fab keeps paying
    the fixed cost of the capex already live; the conversion's capex joins it when live."""
    from tst.sim.fabs.actions import UpgradeFab

    lg = m21.loaded()
    fb = lg.balance.fab
    game = m21.game_at(1, m21.ym_to_turn(2016, 1))
    fid = m21.build(game, "n28", "east_asia", 10_000)
    m21.play(game, 1)
    ps = game.state.person_state(game.founder_id)
    game.state = m21.with_person_state(game.state, replace(ps, energy=100))
    if not game.act(UpgradeFab(game.founder_id, fid)):
        pytest.skip(f"no conversion from 28 nm here: {dict(game.refused)}")
    m21.play(game, 1)
    fab = m21.fm.fab_of(game.state, fid)
    assert fab is not None and fab.upgrading(game.state.turn - 1)
    live = sum(p.cents for p in fab.parts)
    from fractions import Fraction

    assert fab.month is not None
    assert fab.month.fixed_cents == round(Fraction(live) * Fraction(str(fb.fixed_share)) / 12)
