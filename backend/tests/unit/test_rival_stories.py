"""Rival CEO storylines (M15b addendum 12): an interview after a launch, a reply when the feud
crosses 25 and 50, a profile on entering the Top 50; template text from engine facts."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.modes.models import Ranking
from tst.sim.press.models import Feud
from tst.sim.press.names import rival_ceo_name
from tst.sim.rivals.models import RivalMove
from tst.sim.rivals.stories import STORY, candidates, month_stories
from tst.sim.state import GameState, with_feud
from tst.sim.turn import text_requests


def _rival(state: GameState) -> int:
    return next(r.id for r in state.rivals() if rival_ceo_name(state, r.id) is not None)


def test_feud_crossing_brings_a_reply_once(loaded: LoadedData) -> None:
    start = fresh_game(loaded)
    rival = _rival(start)
    player = start.player.id
    start = with_feud(start, Feud(player, rival, score=20.0))
    now = with_feud(start, Feud(player, rival, score=27.0))
    found = candidates(start, now, loaded.balance)
    assert [(k, r) for k, r, _ in found] == [("reply", rival)]
    assert found[0][2]["mark"] == "25"
    later = with_feud(now, Feud(player, rival, score=30.0))
    assert candidates(now, later, loaded.balance) == []  # already past 25, not yet 50
    big = with_feud(now, Feud(player, rival, score=55.0))
    assert candidates(now, big, loaded.balance)[0][2]["mark"] == "50"


def test_interview_after_a_launch_and_text(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    rival = _rival(state)
    product = state.company_products(rival)[0]
    assert month_stories(state, state, loaded.balance) == []  # seeded products: no interview
    move = RivalMove(1, rival, state.turn, "launched", product.id)
    now = replace(state, rival_moves=(*state.rival_moves, move))
    items = month_stories(state, now, loaded.balance)
    assert len(items) == 1
    item = items[0]
    params = dict(item.params)
    assert item.template == STORY and item.link_id == rival and params["story"] == "interview"
    assert product.name in str(params["text"]) and product.name in str(params["title"])
    assert "{" not in str(params["text"])
    reqs = text_requests((item,), now.player.id, now.turn)
    assert any(r.kind == "rival_story" and r.ref_id == rival for r in reqs)


def test_profile_on_entering_the_top_50(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    state = replace(state, turn=11)  # December: January's lists are turn 12
    rival = _rival(state)
    ranked = replace(state, rankings=(Ranking(12, "revenue", 7, rival, 1.0),))
    found = candidates(state, ranked, loaded.balance)
    assert [(k, r) for k, r, _ in found] == [("profile", rival)]
    assert found[0][2]["place"] == "7"
    # already in last year's list: no new profile
    both = replace(ranked, rankings=(*ranked.rankings, Ranking(0, "revenue", 9, rival, 1.0)))
    assert candidates(state, both, loaded.balance) == []


def test_at_most_max_per_month_one_per_rival(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    now = state
    for r in state.rivals():
        for p in state.company_products(r.id):
            move = RivalMove(p.id, r.id, state.turn, "launched", p.id)
            now = replace(now, rival_moves=(*now.rival_moves, move))
        now = with_feud(now, Feud(state.player.id, r.id, score=30.0))
    found = candidates(state, now, loaded.balance)
    assert len(found) == loaded.balance.story.max_per_month
    assert len({r for _, r, _ in found}) == len(found)
    assert all(k == "reply" for k, _, _ in found)  # a reply comes first
