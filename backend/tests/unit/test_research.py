"""Research projects, decay, breakthroughs and dead ends (formulas.md 21.1, 21.3; M11
sub-task 3)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, with_employee, with_product
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.actions import AssignUnit, CreateUnit, MovePerson, UnassignUnit
from tst.sim.actions.research import SetProjectBudget, StartProject, StopProject
from tst.sim.data_models import Balance
from tst.sim.errors import ProductRuleError, ResearchRuleError
from tst.sim.ledger import RESEARCH
from tst.sim.org.rules import org_view
from tst.sim.research import projects as rp
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

FOUNDER = 1


def _lab_game(loaded: LoadedData, staff: int = 6, role: str = "data_scientist") -> Game:
    state = fresh_game(loaded)
    for pid in range(2, 2 + staff):
        state = with_employee(loaded, state, make_person(loaded, pid, role), 9_000_000, morale=50)
    game = Game(loaded, state, cash=500_000_000)
    game.act(CreateUnit(FOUNDER, "team", "Lab"))
    unit = game.state.active_units(1)[0]
    for pid in range(2, 2 + staff):
        game.act(MovePerson(FOUNDER, pid, unit.id))
    return game


def _rnd(balance: Balance, **changes: object) -> Balance:
    return balance.model_copy(update={"rnd": balance.rnd.model_copy(update=changes)})


def _unit(game: Game) -> int:
    return game.state.active_units(1)[0].id


def test_start_costs_energy_and_a_unit_does_one_thing(loaded: LoadedData) -> None:
    game = _lab_game(loaded)
    unit = _unit(game)
    energy = game.state.person_state(FOUNDER).energy or 0
    game.act(StartProject(FOUNDER, unit, "ai"))
    assert game.state.person_state(FOUNDER).energy == energy - loaded.balance.rnd.start_energy
    project = game.state.unit_project(unit)
    assert project is not None and project.domain == "ai" and project.is_active
    state = with_product(game.state, product_id=900, category="ai_models", root=False)
    game.state = state
    with pytest.raises(ProductRuleError, match="research project"):
        game.act(AssignUnit(FOUNDER, 900, unit))
    with pytest.raises(ResearchRuleError, match="already"):
        game.act(StartProject(FOUNDER, unit, "infrastructure"))
    game.act(StopProject(FOUNDER, project.id))
    game.act(AssignUnit(FOUNDER, 900, unit))
    with pytest.raises(ResearchRuleError, match="works on"):
        game.act(StartProject(FOUNDER, unit, "ai"))
    game.act(UnassignUnit(FOUNDER, unit))
    with pytest.raises(ResearchRuleError, match="unknown research domain"):
        game.act(StartProject(FOUNDER, unit, "alchemy"))


def test_progress_and_budget(loaded: LoadedData) -> None:
    """A month of a 6-person AI lab: lead = 0.25 x o x funded share, then decay; the budget
    posts n x $6,000 x the AI compute index to 6500."""
    game = _lab_game(loaded)
    unit = _unit(game)
    game.act(StartProject(FOUNDER, unit, "ai"))
    state = game.state
    project = state.unit_project(unit)
    assert project is not None
    work = rp.lab(state, org_view(state, 1), project, loaded.balance, loaded.game_data)
    assert len(work.researchers) == 6
    assert work.funded == 1.0
    quiet = _rnd(loaded.balance, breakthrough_chance=0.0, dead_end_chance=0.0)
    after, entries = rp.run_projects(state, RngFactory(1), quiet, loaded.game_data)
    gained = rp.progress(work.output, 0.0, quiet)
    assert after.research_lead(1, "ai") == pytest.approx(gained)
    spend = sum(line.amount for e in entries for line in e.lines if line.account == RESEARCH)
    assert (
        spend
        == work.needed_cents
        == 6
        * rp.researcher_cost_cents(
            state, loaded.game_data, rp.levels.domain_def(loaded.game_data, "ai")
        )
    )
    decayed = rp.decay_leads(after, loaded.game_data, quiet)
    assert decayed.research_lead(1, "ai") == pytest.approx(gained * (1 - quiet.rnd.decay))


def test_underfunding_scales_output(loaded: LoadedData) -> None:
    game = _lab_game(loaded)
    unit = _unit(game)
    game.act(StartProject(FOUNDER, unit, "ai"))
    project = game.state.unit_project(unit)
    assert project is not None
    full = rp.lab(game.state, org_view(game.state, 1), project, loaded.balance, loaded.game_data)
    game.act(SetProjectBudget(FOUNDER, project.id, full.needed_cents // 2))
    quiet = _rnd(loaded.balance, breakthrough_chance=0.0, dead_end_chance=0.0)
    after, entries = rp.run_projects(game.state, RngFactory(1), quiet, loaded.game_data)
    assert after.research_lead(1, "ai") == pytest.approx(
        rp.progress(full.output * (full.needed_cents // 2) / full.needed_cents, 0, quiet)
    )
    assert sum(e.lines[0].amount for e in entries) == full.needed_cents // 2
    game.act(SetProjectBudget(FOUNDER, project.id, 0))
    after, entries = rp.run_projects(game.state, RngFactory(1), quiet, loaded.game_data)
    assert after.research_lead(1, "ai") == 0 and entries == ()


def _seeded_lab(loaded: LoadedData) -> GameState:
    game = _lab_game(loaded)
    game.act(StartProject(FOUNDER, _unit(game), "ai"))
    return game.state


def test_breakthroughs_are_seeded(loaded: LoadedData) -> None:
    """Stream `research`, key (project_id,): the same seed gives the same month; a draw below
    0.02 q is a breakthrough worth +5 lead and recorded as this month's event (21.3)."""
    state = _seeded_lab(loaded)
    runs = [
        rp.run_projects(state, RngFactory(s), loaded.balance, loaded.game_data)[0] for s in (7, 7)
    ]
    assert runs[0] == runs[1]
    sure = _rnd(loaded.balance, breakthrough_chance=1.0)
    after, _ = rp.run_projects(state, RngFactory(7), sure, loaded.game_data)
    project = after.research_projects[0]
    assert project.last_event == "breakthrough" and project.last_event_turn == state.turn
    quiet = _rnd(loaded.balance, breakthrough_chance=0.0, dead_end_chance=0.0)
    base, _ = rp.run_projects(state, RngFactory(7), quiet, loaded.game_data)
    assert after.research_lead(1, "ai") == pytest.approx(base.research_lead(1, "ai") + 5)
    # Over many seeds the breakthrough rate is near 0.02 x q.
    work = rp.lab(
        state, org_view(state, 1), state.research_projects[0], loaded.balance, loaded.game_data
    )
    q = rp.quality(work.mean_skill, loaded.balance)
    hits = sum(
        rp.run_projects(state, RngFactory(s), loaded.balance, loaded.game_data)[0]
        .research_projects[0]
        .last_event
        == "breakthrough"
        for s in range(2000)
    )
    assert hits / 2000 == pytest.approx(0.02 * q, abs=0.01)


def test_dead_end_loses_half_the_recent_progress(loaded: LoadedData) -> None:
    state = _seeded_lab(loaded)
    project = state.research_projects[0]
    state = replace(state, research_projects=(replace(project, recent=(1.0, 1.0)),))
    quiet = _rnd(loaded.balance, breakthrough_chance=0.0, dead_end_chance=0.0)
    gained = rp.run_projects(state, RngFactory(3), quiet, loaded.game_data)[0].research_lead(
        1, "ai"
    )
    doomed = _rnd(loaded.balance, breakthrough_chance=0.0, dead_end_chance=1.0)
    after, _ = rp.run_projects(state, RngFactory(3), doomed, loaded.game_data)
    lost = 0.5 * (1.0 + 1.0 + gained)
    assert after.research_lead(1, "ai") == pytest.approx(max(0.0, gained - lost))
    assert after.research_projects[0].last_event == "dead_end"


def test_a_dissolved_unit_stops_its_project(loaded: LoadedData) -> None:
    state = _seeded_lab(loaded)
    unit = state.active_units(1)[0]
    state = replace(state, units=(replace(unit, status="dissolved"),))
    after, entries = rp.run_projects(state, RngFactory(1), loaded.balance, loaded.game_data)
    assert after.research_projects[0].status == "stopped" and entries == ()


def test_full_turn_grows_the_lead(loaded: LoadedData) -> None:
    game = _lab_game(loaded)
    game.act(StartProject(FOUNDER, _unit(game), "ai"))
    for _ in range(3):
        game.turn()
    assert game.state.research_lead(1, "ai") > 3
