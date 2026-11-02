"""Era milestones (formulas.md 21.4) and 21.8 target 1's demand check (M11 sub-task 4)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import MONTHS_PER_YEAR, turn_to_ym, ym_to_turn
from tst.sim.products.formulas import monthly_growth
from tst.sim.research import eras, levels
from tst.sim.research.models import ResearchLead
from tst.sim.research.projects import decay_leads
from tst.sim.state import GameState


def _months(loaded: LoadedData, state: GameState, months: int) -> GameState:
    """Phase 3's era check and phase 9's demand growth, month by month (no other phases)."""
    data, balance = loaded.game_data, loaded.balance
    for _ in range(months):
        state, _ = eras.arrive_eras(state, data, balance)
        markets = tuple(
            replace(
                m,
                addressable=m.addressable
                * (1 + eras.annual_growth(state, data, m.category, m.segment))
                ** (1 / MONTHS_PER_YEAR),
            )
            for m in state.markets
        )
        state = replace(state, markets=markets, turn=state.turn + 1)
    return state


def _before_m11(loaded: LoadedData, category: str, segment: str, months: int) -> float:
    cat = loaded.game_data.category(category)
    value = cat.market(segment).addressable
    for t in range(months):
        value *= monthly_growth(cat, turn_to_ym(t)[0])
    return value


def test_eras_arrive_on_their_dates_without_research(loaded: LoadedData) -> None:
    state = _months(loaded, fresh_game(loaded), 200)
    for era in loaded.game_data.eras.eras:
        arrival = state.era_arrival(era.key)
        hist = ym_to_turn(*era.arrival)
        if hist < 200:
            assert arrival is not None and arrival.turn == hist, era.key
            assert arrival.company_id is None and arrival.months_early == 0
        else:
            assert arrival is None


def test_target_1_demand_is_unchanged(loaded: LoadedData) -> None:
    """21.8 target 1: with eras on their historical dates, AI demand in January 2024 is
    within 10% of M8's (359x January 2010), and every other category's January 2020 demand
    within 10% of before M11."""
    data = loaded.game_data
    state = fresh_game(loaded)
    jan_2020, jan_2024 = ym_to_turn(2020, 1), ym_to_turn(2024, 1)
    at_2020 = _months(loaded, state, jan_2020)
    at_2024 = _months(loaded, at_2020, jan_2024 - jan_2020)
    ai = at_2024.market("ai_models", "smb")
    assert ai is not None
    ratio = ai.addressable / data.category("ai_models").market("smb").addressable
    print(f"21.8 target 1: AI demand Jan 2024 = {ratio:.0f}x Jan 2010 (M8 359x)")
    assert ratio == pytest.approx(359, rel=0.10)
    for cat in data.categories:
        if cat.key == "ai_models":
            continue
        for m in cat.markets:
            now = at_2020.market(cat.key, m.segment)
            assert now is not None
            before = _before_m11(loaded, cat.key, m.segment, jan_2020)
            print(f"  {cat.key}/{m.segment} Jan 2020: {now.addressable / before:.3f} of before")
            assert now.addressable == pytest.approx(before, rel=0.10), (cat.key, m.segment)


def _with_ai_lead(state: GameState, lead: float, turn: int) -> GameState:
    return replace(state, turn=turn, research_leads=(ResearchLead(1, "ai", lead),))


def test_a_lead_past_the_threshold_brings_an_era_early(loaded: LoadedData) -> None:
    """Transformers' threshold is 43.5; in January 2016 (Deep learning arrived) the baseline
    is 24, so a lead of 19.5 causes it 17 months early (21.4, 21.9)."""
    data, balance = loaded.game_data, loaded.balance
    jan_2016 = ym_to_turn(2016, 1)
    state = _months(loaded, fresh_game(loaded), jan_2016)
    assert state.era_arrival("deep_learning") is not None
    short, _ = eras.arrive_eras(_with_ai_lead(state, 19.4, jan_2016), data, balance)
    assert short.era_arrival("transformers") is None
    after, logs = eras.arrive_eras(_with_ai_lead(state, 19.5, jan_2016), data, balance)
    arrival = after.era_arrival("transformers")
    assert arrival is not None
    assert (arrival.turn, arrival.company_id, arrival.months_early) == (jan_2016, 1, 17)
    assert levels.baseline(after, data, balance, "ai") == pytest.approx(29.0)
    news = next(i for i in logs if dict(i.params)["era"] == "Transformers")
    assert "17 months early" in str(dict(news.params)["when"])
    assert "First-mover head start" in str(dict(news.params)["note"])


def test_the_first_mover_window(loaded: LoadedData) -> None:
    """For 12 months the causer's AI products get +5 on the quality cap and +10 on the brand
    target, and its AI lead does not decay; then it ends (21.4)."""
    data, balance = loaded.game_data, loaded.balance
    jan_2016 = ym_to_turn(2016, 1)
    state = _months(loaded, fresh_game(loaded), jan_2016)
    state, _ = eras.arrive_eras(_with_ai_lead(state, 20.0, jan_2016), data, balance)
    factor = levels.tech_factor(state, 1, "ai_models", balance, data)
    assert (factor.cap_points, factor.brand_points) == (5.0, 10.0)
    assert factor.cap(50.0) == pytest.approx(50.0 * (1 + balance.rnd.cap_per_point * 16.0) + 5.0)
    other = levels.tech_factor(state, 1, "b2b_saas", balance, data)
    assert other.cap_points == 0 and other.brand_points == 0
    assert decay_leads(state, data, balance).research_lead(1, "ai") == 20.0
    late = replace(state, turn=jan_2016 + 12)
    assert levels.tech_factor(late, 1, "ai_models", balance, data).cap_points == 0
    assert decay_leads(late, data, balance).research_lead(1, "ai") == pytest.approx(19.7)


def test_boosts_follow_the_arrival(loaded: LoadedData) -> None:
    """An early Mobile-first pulls its +15 points and consumer adoption x1.2 forward."""
    data, balance = loaded.game_data, loaded.balance
    state = replace(
        fresh_game(loaded),
        turn=3,
        research_leads=(ResearchLead(1, "software_platform", 60.0),),
    )
    state, _ = eras.arrive_eras(state, data, balance)
    assert state.era_arrival("mobile_first") is not None
    base = eras.base_growth(data, "consumer_apps", 2010)
    assert eras.annual_growth(state, data, "consumer_apps", "consumer") == pytest.approx(
        base + 0.15
    )
    assert eras.adoption_factor(state, data, "consumer_apps", "consumer") == pytest.approx(1.2)
    assert eras.adoption_factor(state, data, "consumer_apps", "smb") == 1.0
    ended = replace(state, turn=3 + 36)
    assert eras.growth_boost(ended, data, "consumer_apps", "consumer") == 0
