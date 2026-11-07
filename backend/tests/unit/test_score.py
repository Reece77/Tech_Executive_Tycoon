"""M15b sub-task 1 (formulas.md 30.1): the company score, its worked example, its parts from
public inputs, and the December snapshots."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game, with_product
from tests.unit.test_hiring_phases import Game
from tst.loader import LoadedData
from tst.sim import score as sc
from tst.sim.modes.models import CompanyScore
from tst.sim.state import with_company


def test_the_30_1_example(loaded: LoadedData) -> None:
    """$40B listed, CAGR 30%, margin 18%, leading 35% of its markets' revenue, brand 70 and
    credibility 62: 306.8 + 120 + 114 + 52.5 + 66 = 659."""
    b = loaded.balance
    points = sc.score_points(
        40e9, sc.growth_part(0.30, b), sc.profit_part(0.18, b), 0.35, (70 + 62) / 200, b
    )
    assert points == pytest.approx(659.3, abs=0.05)
    assert round(points) == 659


@settings(max_examples=200, deadline=None)
@given(
    value=st.floats(0, 1e16),
    cagr=st.floats(-1, 10),
    margin=st.floats(-5, 5),
    lead=st.floats(0, 1),
    rep=st.floats(0, 1),
)
def test_the_score_stays_in_0_to_1000(
    loaded: LoadedData, value: float, cagr: float, margin: float, lead: float, rep: float
) -> None:
    b = loaded.balance
    points = sc.score_points(
        value, sc.growth_part(cagr, b), sc.profit_part(margin, b), lead, rep, b
    )
    assert 0 <= points <= 1000


def test_growth_reads_the_snapshot_three_years_back(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    state = replace(state, turn=47)  # December 2013
    state = with_company(state, replace(state.player, mrr_history=(100,) * 12))
    old = CompanyScore(1, 11, 0, 0, 0, 0, 0, 0, revenue_cents=600)  # December 2010
    state = replace(state, scores=(old,))
    assert sc.cagr(state, 1) == pytest.approx((1200 / 600) ** (1 / 3) - 1)
    assert sc.cagr(replace(state, scores=()), 1) == 0.0  # no history: no growth


def test_leadership_weights_markets_by_revenue(loaded: LoadedData) -> None:
    markets = {
        ("b2b_saas", "smb", "na"): {1: 30.0, 2: 10.0},  # led, size 40
        ("b2b_saas", "mid", "na"): {1: 10.0, 2: 50.0},  # not led, size 60
        ("dev_tools", "smb", "na"): {2: 99.0},  # not sold in: not counted
    }
    assert sc.leadership_part(1, markets) == pytest.approx(40 / 100)


def test_every_december_scores_every_company(loaded: LoadedData) -> None:
    state = with_product(fresh_game(loaded), customers={"smb": 100.0})
    game = Game(loaded, state)
    while game.state.turn < 11:
        game.turn()
    assert not game.state.scores
    game.turn()  # December 2010 closes
    scores = {s.company_id: s for s in game.state.scores}
    alive = {c.id for c in game.state.ledger_companies() if c.alive}
    assert set(scores) == alive and all(s.turn == 11 for s in scores.values())
    assert all(0 <= s.score <= 1000 for s in scores.values())
    listed = next(c for c in game.state.rivals() if c.name == "Microsoft")
    assert scores[listed.id].score > scores[1].score  # a giant outranks a new startup
