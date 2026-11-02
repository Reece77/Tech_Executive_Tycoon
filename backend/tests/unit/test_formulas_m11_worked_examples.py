"""docs/formulas.md 21.9 worked examples and 21.8 target 4 (M11 sub-task 1)."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.products import formulas as pf
from tst.sim.research import levels
from tst.sim.research.formulas import license_price_cents
from tst.sim.research.models import EraArrival, ResearchLead
from tst.sim.research.projects import decay_leads, progress
from tst.sim.state import CompanyState, GameState, SaveMeta


def _state(turn: int = 0, leads: tuple[ResearchLead, ...] = (), arrivals=()) -> GameState:
    company = CompanyState(id=1, name="Kestrel", is_player=True, stage=1, founded_turn=0)
    return GameState(
        save_meta=SaveMeta("t", 1, "garage_bootstrap", "standard"),
        turn=turn,
        companies=(company,),
        research_leads=leads,
        era_arrivals=tuple(arrivals),
    )


def test_progress(loaded: LoadedData) -> None:
    """6 researchers with research skill 12, morale 50, no tax: o = 0.98 x 6 x 1.2 = 7.06;
    Delta R = 0.25 x 7.06 = 1.76 a month at R = 0 and 0.88 at R = 30."""
    pb = loaded.balance.products
    each = 12 / 10 * pf.morale_factor(50, pb) * pf.tag_multiplier((), pb)
    output = pf.coord_factor(6, pb) * 6 * each
    assert output == pytest.approx(7.056)
    assert progress(output, 0, loaded.balance) == pytest.approx(1.764)
    assert progress(output, 30, loaded.balance) == pytest.approx(0.882)


def test_quality_cap(loaded: LoadedData) -> None:
    """B2B SaaS, Q_cap 60, software platform lead 20 and infrastructure 10: R_cat = 17, so
    Q_cap = 60 x 1.068 = 64.1."""
    leads = (ResearchLead(1, "software_platform", 20.0), ResearchLead(1, "infrastructure", 10.0))
    state = _state(leads=leads)
    data, balance = loaded.game_data, loaded.balance
    assert levels.category_lead(state, data, 1, "b2b_saas") == pytest.approx(17.0)
    factor = levels.tech_factor(state, 1, "b2b_saas", balance, data)
    assert factor.cap(60.0) == pytest.approx(64.08)
    assert factor.feature_mult == pytest.approx(1.034)


def test_era_threshold(loaded: LoadedData) -> None:
    """Transformers: D_AI(2017.5) = 10 + 1.5 x 6 + 3 x 1.5 = 23.5, + 5 for Deep learning,
    + 15 = 43.5. In January 2016 the AI baseline is 10 + 9 + 5 = 24: a lead of 19.5."""
    data, balance = loaded.game_data, loaded.balance
    transformers = next(e for e in data.eras.eras if e.key == "transformers")
    assert levels.threshold(data, balance, transformers) == pytest.approx(43.5)
    jan_2016 = 72
    state = _state(jan_2016, arrivals=(EraArrival("deep_learning", 33),))
    assert levels.baseline(state, data, balance, "ai") == pytest.approx(24.0)
    assert levels.threshold(data, balance, transformers) - 24.0 == pytest.approx(19.5)


def test_license_price(loaded: LoadedData) -> None:
    """12 points with ARR $10M: $150,000 x 12 x 1.5 = $2.7M."""
    assert license_price_cents(12, 1_000_000_000, loaded.balance) == 270_000_000


def test_decay_target(loaded: LoadedData) -> None:
    """21.8 target 4: a lead of 30 with no research is 14-16 after 46 months (about 14.95)."""
    state = _state(leads=(ResearchLead(1, "ai", 30.0),))
    for _ in range(46):
        state = decay_leads(state, loaded.game_data, loaded.balance)
    lead = state.research_lead(1, "ai")
    print(f"21.8 target 4: lead 30 after 46 months = {lead:.2f}")
    assert 14 <= lead <= 16


def test_no_research_is_identity(loaded: LoadedData) -> None:
    """A company with no lead and no first-mover window has a factor of exactly 1 (21.2)."""
    state = _state(arrivals=(EraArrival("mobile_first", 12),))
    factor = levels.tech_factor(state, 1, "consumer_apps", loaded.balance, loaded.game_data)
    assert factor.is_identity
    assert factor.cap(57.3) == 57.3
    assert factor.feature_mult == 1.0
