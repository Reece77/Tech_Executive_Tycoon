"""M35a sub-task 2: the two server errors e2e's logs showed on main, each reproduced. The M&A
screen of a group with a subsidiary the player founded (no acquisition record: StopIteration),
and an open event that names someone who has since left (no longer in the state: KeyError)."""

from __future__ import annotations

from tests.unit.test_m23a_group import SUB_CENTS, found
from tst.api.event_links import GONE, event_links
from tst.api.mna_views import mna_out
from tst.balance.game import Game, start_game
from tst.balance.report import SCENARIO
from tst.loader import LoadedData
from tst.sim.events.models import GameEvent
from tst.sim.ledger import CASH


def _game(loaded: LoadedData) -> Game:
    return start_game(loaded, 3, SCENARIO)


def test_a_founded_subsidiary_shows_on_the_mna_screen(loaded: LoadedData) -> None:
    game = _game(loaded)
    game.balances[(game.state.player.id, CASH)] = 2 * SUB_CENTS  # the founding needs the cash
    cid = found(game, "Founded Sub")
    assert not any(a.target_id == cid for a in game.state.acquisitions)
    out = mna_out(game.state, game.balances, loaded)
    (sub,) = [s for s in out.subsidiaries if s.company_id == cid]
    assert sub.name == "Founded Sub" and sub.directive == "grow"  # tst.sim.mna.style's default


def _event(company_id: int, turn: int, people: tuple[int, ...]) -> GameEvent:
    return GameEvent(
        id=1,
        company_id=company_id,
        turn=turn,
        template_id="low_morale_checkin",
        category="people",
        severity="major",
        trigger="test",
        strength=1.0,
        person_ids=people,
    )


def test_an_event_naming_someone_who_left_still_has_links(loaded: LoadedData) -> None:
    state = _game(loaded).state
    person = state.people[0]
    gone = max(p.id for p in state.people) + 1
    event = _event(state.player.id, state.turn, (person.id, gone))
    links = {link.path: link.label for link in event_links(state, event, loaded)}
    assert links[f"people/{gone}"] == GONE  # opens their Former employee profile
    assert links[f"people/{person.id}"] == f"{person.first_name} {person.last_name}"
