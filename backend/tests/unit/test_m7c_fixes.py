"""M7c sub-task 4: regression tests for the bugs the agent playtest found."""

from __future__ import annotations

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.events.render import placeholder_names, render


def test_an_unhappy_company_root_names_the_company(loaded: LoadedData) -> None:
    """unhappy_unit fires at the root with no unit id and no people: {unit} is the company
    (the playtest saw "{unit} asks for fewer meetings")."""
    state = fresh_game(loaded)
    names = placeholder_names(state, loaded.game_data, 1)
    title = loaded.game_data.event_template("unhappy_unit_process").title
    assert render(title, names) == f"{state.player.name} asks for fewer meetings"
