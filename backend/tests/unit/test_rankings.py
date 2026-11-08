"""M15b sub-task 5 (formulas.md 30.4): three lists each January, the news item, and the hiring
and brand effects of a top-10 place."""

from __future__ import annotations

from dataclasses import replace

from tests.helpers import fresh_game, with_product
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim.modes import rankings as rk
from tst.sim.modes.models import Ranking


def test_january_brings_three_lists_and_the_news(loaded: LoadedData) -> None:
    game = Game(loaded, with_product(fresh_game(loaded), customers={"smb": 100.0}))
    while game.state.turn < 11:
        game.turn()
    assert not game.state.rankings
    result = game.turn()  # December's month end publishes January's lists
    kinds = {r.kind for r in game.state.rankings}
    assert kinds == {"revenue", "places", "innovative"}
    revenue = [r for r in game.state.rankings if r.kind == "revenue"]
    assert len(revenue) <= loaded.balance.rank.top_revenue and revenue[0].place == 1
    assert [r.value for r in revenue] == sorted((r.value for r in revenue), reverse=True)
    assert all(r.turn == 12 for r in game.state.rankings)
    news = [i for i in result.log_items if i.kind == "rankings_published"]
    assert len(news) == 1 and news[0].company_id == 1


def test_the_news_item_names_each_lists_top_and_links_the_screen(loaded: LoadedData) -> None:
    """Playtest 4 (M15r addendum b): the January item gives the player's place on each list
    (or "not ranked"), the top five names on each, and links to the Rankings screen."""
    from tst.db.inbox import render

    game = Game(loaded, with_product(fresh_game(loaded), customers={"smb": 100.0}))
    while game.state.turn < 11:
        game.turn()
    result = game.turn()
    item = next(i for i in result.log_items if i.kind == "rankings_published")
    assert item.link_kind == "rankings"
    params = dict(item.params)
    names = {c.id: c.name for c in game.state.companies}
    n = loaded.balance.rank.news_top
    assert n == 5
    for kind in ("revenue", "places", "innovative"):
        ranked = sorted((r for r in game.state.rankings if r.kind == kind), key=lambda r: r.place)
        mine = next((r for r in ranked if r.company_id == 1), None)
        assert params[f"{kind}_place"] == (f"#{mine.place}" if mine else "not ranked")
        expected = ", ".join(f"{r.place}. {names[r.company_id]}" for r in ranked[:n])
        assert params[f"{kind}_top"] == (expected or "nobody yet")
    assert len(params["revenue_top"].split(", ")) == n  # the revenue list has five or more
    _, body = render(item, loaded.game_data.inbox_templates)
    assert params["revenue_top"] in body and "Rankings screen" in body
    assert params["revenue_place"] in body and params["innovative_top"] in body


def test_a_top_ten_place_lifts_hiring_and_brand_for_the_year(loaded: LoadedData) -> None:
    b = loaded.balance
    state = replace(fresh_game(loaded), turn=12)
    top = (Ranking(12, "places", 3, 1, 0.9), Ranking(12, "innovative", 11, 1, 0.5))
    state = replace(state, rankings=top)
    assert rk.hiring_bonus(state, 1, b) == b.rank.hiring
    assert rk.brand_bonus(state, 1, b) == 0  # 11th: no effect
    assert rk.hiring_bonus(replace(state, turn=24), 1, b) == 0  # the year is over
    state = replace(state, rankings=(Ranking(12, "innovative", 10, 1, 0.5),))
    assert rk.brand_bonus(state, 1, b) == b.rank.brand


def test_best_places_needs_fifty_staff(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    assert rk.places_measure(state, 1, loaded.balance, loaded.game_data) is None
    big = next(
        c
        for c in state.rivals()
        if len(state.staff(c.id)) + sum(p.headcount for p in state.company_pools(c.id)) >= 50
    )
    value = rk.places_measure(state, big.id, loaded.balance, loaded.game_data)
    assert value is not None and 0 <= value <= 1
