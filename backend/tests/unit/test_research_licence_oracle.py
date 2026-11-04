"""M12r finding 1 (Codex review 3): licence errors must not reveal a rival's true lead.

The licence-in and licence-out actions offer at most the ceiling the Research screen shows,
taken from the displayed range (21.7, 21.10), in whole points; their errors depend only on
public values. Two rivals whose true leads differ but whose displayed ranges are the same
give the same answer to every request.
"""

from __future__ import annotations

import math
from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game
from tests.unit.test_hiring_phases import Game
from tests.unit.test_research import FOUNDER, _lab_game
from tst.loader import LoadedData
from tst.sim.actions.research import LicenseIn, LicenseOut
from tst.sim.errors import SimError
from tst.sim.ledger import CASH
from tst.sim.research import estimates, licensing
from tst.sim.research.models import License, ResearchLead
from tst.sim.research.projects import add_lead
from tst.sim.state import GameState

IBM = 17
PLANTED = 23.4567


def _game(loaded: LoadedData, lead: float, cash: int = 0) -> Game:
    game = _lab_game(loaded, staff=1)
    game.state = add_lead(game.state, IBM, "devices", lead)
    game.balances = {**game.balances, (1, CASH): cash}
    return game


def _answer(game: Game, action: LicenseIn | LicenseOut) -> str:
    """What the player learns from a request: the error class and its words, or 'ok'."""
    state, balances = game.state, dict(game.balances)
    try:
        game.act(action)
    except SimError as exc:
        return f"{type(exc).__name__}: {exc}"
    finally:
        game.state, game.balances = state, balances
    return "ok"


def _range(loaded: LoadedData, state: GameState, lead: float) -> tuple[int, int]:
    planted = add_lead(state, IBM, "devices", lead - state.research_lead(IBM, "devices"))
    return estimates.lead_range(planted, 1, IBM, "devices", loaded.balance, loaded.game_data)


def _sibling(loaded: LoadedData, state: GameState, lead: float) -> float:
    """The lead furthest from `lead` (within a point) with the same displayed range."""
    shown = _range(loaded, state, lead)
    same = [
        lead + k / 1000
        for k in range(-1000, 1001)
        if lead + k / 1000 > 0 and _range(loaded, state, lead + k / 1000) == shown
    ]
    return max(same, key=lambda x: abs(x - lead))


def _bisect(game: Game) -> list[str]:
    """Codex's oracle: 32 failed calls halving the interval the licence limit lies in."""
    lo, hi = 0.0, 40.0
    transcript = []
    for _ in range(32):
        mid = (lo + hi) / 2
        answer = _answer(game, LicenseIn(FOUNDER, IBM, "devices", mid))
        transcript.append(f"{mid!r} -> {answer}")
        if "fewer points" in answer:
            hi = mid
        else:
            lo = mid
    return transcript


def test_bisection_learns_nothing_below_the_displayed_range(loaded: LoadedData) -> None:
    """IBM's planted 23.4567 and a lead with the same displayed range give the same 32
    answers, so the bisection cannot narrow the lead below the range."""
    game = _game(loaded, PLANTED)
    other = _sibling(loaded, game.state, PLANTED)
    assert abs(other - PLANTED) > 0.3
    assert _bisect(game) == _bisect(_game(loaded, other))


def test_requests_answer_from_public_values_only(loaded: LoadedData) -> None:
    """Failed, unaffordable and fractional requests, in and out, answer identically for
    two true leads with the same displayed range."""
    a = _game(loaded, PLANTED)
    b = _game(loaded, _sibling(loaded, a.state, PLANTED))
    a.state = add_lead(a.state, 1, "software_platform", 30.0)
    b.state = add_lead(b.state, 1, "software_platform", 30.0)
    requests: list[LicenseIn | LicenseOut] = [
        LicenseIn(FOUNDER, IBM, "devices", p / 4) for p in range(1, 4 * 30)
    ]
    requests += [LicenseOut(FOUNDER, IBM, "devices", p / 4) for p in range(1, 4 * 30)]
    assert [_answer(a, r) for r in requests] == [_answer(b, r) for r in requests]


def test_the_action_offers_the_screens_ceiling_in_whole_points(loaded: LoadedData) -> None:
    game = _game(loaded, PLANTED, cash=500_000_000)
    low, _ = _range(loaded, game.state, PLANTED)
    ceiling = licensing.public_license_in_limit(
        game.state, loaded.balance, loaded.game_data, 1, IBM, "devices"
    )
    assert ceiling == max(0, math.floor(low - loaded.balance.rnd.license.margin))
    assert "whole points" in _answer(game, LicenseIn(FOUNDER, IBM, "devices", 1.5))
    assert "fewer points" in _answer(game, LicenseIn(FOUNDER, IBM, "devices", ceiling + 1))
    game.act(LicenseIn(FOUNDER, IBM, "devices", ceiling))
    assert game.state.research_lead(1, "devices") == ceiling


@settings(max_examples=200, deadline=None)
@given(
    theirs=st.floats(min_value=0, max_value=120, allow_nan=False),
    mine=st.floats(min_value=0, max_value=120, allow_nan=False),
    licensed=st.booleans(),
)
def test_the_public_ceiling_never_exceeds_the_true_limit(
    loaded: LoadedData, theirs: float, mine: float, licensed: bool
) -> None:
    """The ceiling is the range's low end (high end, licensing out) minus the margin, so a
    request the screen allows is always one the true lead allows."""
    licences = (License(1, IBM, 1, "ai", 1.0, 0, 0),) if licensed else ()
    state = replace(
        fresh_game(loaded),
        research_leads=(ResearchLead(IBM, "devices", theirs), ResearchLead(1, "devices", mine)),
        licenses=licences,
    )
    b, g = loaded.balance, loaded.game_data
    assert licensing.public_license_in_limit(state, b, g, 1, IBM, "devices") <= max(
        0.0, licensing.license_in_limit(state, b, 1, IBM, "devices")
    )
    assert licensing.public_license_out_limit(state, b, g, 1, IBM, "devices") <= max(
        0.0, licensing.license_in_limit(state, b, IBM, 1, "devices")
    )
