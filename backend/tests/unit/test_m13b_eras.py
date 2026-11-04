"""M13b sub-tasks 5-6 (formulas.md 27.3-27.4): the first mover's appeal bonus, the arrival
item listing its products, the era report at the window's end, era marks, and market size."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, with_product
from tests.unit.test_research_eras import _months, _with_ai_lead
from tst.api.product_views import categories_out, era_marks, market_out, size_cents_year
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.research import eras, levels
from tst.sim.rng import RngFactory
from tst.sim.state import GameState


def _caused(loaded: LoadedData) -> tuple[GameState, list]:  # type: ignore[type-arg]
    """The player's AI product, then Transformers pulled forward 17 months (21.9)."""
    data, balance = loaded.game_data, loaded.balance
    jan_2016 = ym_to_turn(2016, 1)
    state = _months(loaded, fresh_game(loaded), jan_2016)
    state = with_product(state, category="ai_models", customers={"smb": 200.0}, name="Oracle")
    state, logs = eras.arrive_eras(
        _with_ai_lead(state, 19.5, jan_2016), data, balance, RngFactory(1)
    )
    return state, list(logs)


def test_the_first_mover_gets_the_appeal_bonus_for_the_window(loaded: LoadedData) -> None:
    data, balance = loaded.game_data, loaded.balance
    state, _ = _caused(loaded)
    assert levels.first_mover_appeal(state, data, balance, 1, "ai_models") == pytest.approx(1.15)
    assert levels.first_mover_appeal(state, data, balance, 1, "b2b_saas") == 1.0
    assert levels.first_mover_appeal(state, data, balance, 2, "ai_models") == 1.0  # not a rival
    late = replace(state, turn=state.turn + balance.rnd.first_mover_months)
    assert levels.first_mover_appeal(late, data, balance, 1, "ai_models") == 1.0


def test_the_appeal_bonus_reaches_the_market(loaded: LoadedData) -> None:
    """The Market screen's appeal for the first mover's product is x1.15 (the engine's own
    appeal hook)."""
    state, _ = _caused(loaded)
    out = market_out(state, "ai_models", loaded)
    row = next(p for s in out.segments for p in s.products if p.name == "Oracle")
    no_bonus = replace(
        state, era_arrivals=tuple(replace(a, company_id=None) for a in state.era_arrivals)
    )
    plain = next(
        p
        for s in market_out(no_bonus, "ai_models", loaded).segments
        for p in s.products
        if p.name == "Oracle"
    )
    assert row.appeal == pytest.approx(plain.appeal * 1.15)


def test_the_arrival_item_lists_the_affected_products(loaded: LoadedData) -> None:
    state, logs = _caused(loaded)
    news = next(
        i for i in logs if i.template == "era_arrived" and dict(i.params)["era"] == "Transformers"
    )
    note = str(dict(news.params)["note"])
    assert "17 months early" in str(dict(news.params)["when"])
    assert "Oracle (quality" in note and "cap +8" in note and "target +15" in note
    assert "x1.15 appeal" in note
    (window,) = state.era_windows
    assert window.era_key == "transformers" and window.company_id == 1
    assert [p[0] for p in window.products] == [state.company_products(1)[0].id]


def test_the_era_report_comes_at_the_windows_end(loaded: LoadedData) -> None:
    data, balance = loaded.game_data, loaded.balance
    state, _ = _caused(loaded)
    months = balance.rnd.first_mover_months
    _, logs = eras.era_reports(replace(state, turn=state.turn + months - 1), data, balance)
    assert not logs
    after, logs = eras.era_reports(replace(state, turn=state.turn + months), data, balance)
    (report,) = logs
    params = dict(report.params)
    assert report.template == "era_report" and params["era"] == "Transformers"
    assert "Oracle:" in str(params["lines"]) and "pre-era path" in str(params["lines"])
    assert after.era_windows[0].reported
    _, logs = eras.era_reports(after, data, balance)
    assert not logs  # once


def test_era_marks_and_market_size(loaded: LoadedData) -> None:
    state, _ = _caused(loaded)
    marks = era_marks(state, "ai_models", loaded, since=0)
    assert [m.label for m in marks][-1] == "Transformers" and marks[-1].caused_by == "You"
    assert era_marks(state, "fintech", loaded) == [] or all(
        "fintech" in next(e for e in loaded.game_data.eras.eras if e.label == m.label).categories
        for m in era_marks(state, "fintech", loaded)
    )
    assert size_cents_year(1000.0, 5000) == 1000 * 5000 * 12
    assert size_cents_year(0.5, 3, 1.0) == 18
    cats = {c.key: c for c in categories_out(state, loaded)}
    ai = cats["ai_models"]
    assert ai.size_cents_year == sum(s.size_cents_year for s in ai.segments) > 0
    m = market_out(state, "ai_models", loaded, history=[(state.turn - 1, 10.0), (state.turn, 12.0)])
    assert m.size_cents_year == ai.size_cents_year
    assert [h.customers for h in m.history] == [10.0, 12.0]
