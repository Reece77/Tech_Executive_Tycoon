"""docs/formulas.md 16.11 worked examples, plus the 16.2 trigger table and 16.3 caps as data
(M6 sub-task 1)."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.events.data import EFFECT_TYPES, SEVERITIES, TRIGGERS
from tst.sim.events.formulas import below_strength, candidate_weight, cash_base_cents, clamp_effect
from tst.sim.people.relationships import (
    relationship_label,
    relationship_start,
    relationship_step,
)


def test_director_draw_weights(loaded: LoadedData) -> None:
    """Priya's low_morale (morale 31) with personnel used last month, a price war and a rival
    move: weights 0.20 x 0.5 = 0.10, 0.60 and 0.30 for weight-1 templates."""
    events = loaded.balance.events
    priya = below_strength(31, events.trigger["low_morale"])
    assert priya == pytest.approx(0.20)
    weights = [
        candidate_weight(1.0, priya, category_used_last_month=True, blocked=False, events=events),
        candidate_weight(
            1.0,
            float(events.trigger["price_war"].strength),  # type: ignore[arg-type]
            category_used_last_month=False,
            blocked=False,
            events=events,
        ),
        candidate_weight(
            1.0,
            float(events.trigger["rival_move"].strength),  # type: ignore[arg-type]
            category_used_last_month=False,
            blocked=False,
            events=events,
        ),
    ]
    assert weights == pytest.approx([0.10, 0.60, 0.30])
    assert (
        candidate_weight(1.0, 0.6, category_used_last_month=False, blocked=True, events=events) == 0
    )


def test_validator_clamp(loaded: LoadedData) -> None:
    """A major draft: morale +15 for Priya clamps to +10; a $40,000 cost with cash $500,000
    and revenue $100,000 a month clamps to 300 bp of $500,000 = $15,000."""
    events = loaded.balance.events
    base = cash_base_cents(50_000_000, 10_000_000, events)
    assert base == 50_000_000
    assert clamp_effect("morale_delta", 15, "major", events, base) == 10
    assert clamp_effect("cash_delta", -4_000_000, "major", events, base) == -1_500_000
    assert clamp_effect("cash_delta", 4_000_000, "major", events, base) == 750_000  # gains: half
    assert clamp_effect("salary_change", -5, "major", events, base) == 0  # never a cut
    assert cash_base_cents(1_000_000, 10_000_000, events) == 30_000_000  # 3 x revenue


def test_relationship_start_and_drift(loaded: LoadedData) -> None:
    """Temperaments 14 and 6 start at 3 ("neutral"); with a credit-taker in the unit the pair
    loses 3 a month and drifts 10% back: 0.3, then -2.13, settling at -24 ("strained")."""
    cfg = loaded.balance.relationships
    start = relationship_start(14, 6, cfg)
    assert start == 3 and relationship_label(start, cfg) == "neutral"
    push = cfg.tag_push["credit_taker"]
    value = relationship_step(start, start, push, cfg)
    assert value == pytest.approx(0.3)
    value = relationship_step(value, start, push, cfg)
    assert value == pytest.approx(-2.13)
    for _ in range(300):
        value = relationship_step(value, start, push, cfg)
    assert value == pytest.approx(-24) and relationship_label(value, cfg) == "strained"


def test_labels_and_start_clamp(loaded: LoadedData) -> None:
    cfg = loaded.balance.relationships
    assert [relationship_label(v, cfg) for v in (-50, -49, -20, -19, 19, 20, 59, 60)] == [
        "hostile",
        "strained",
        "strained",
        "neutral",
        "neutral",
        "good",
        "good",
        "close",
    ]
    assert relationship_start(20, 1, cfg) == -14
    assert relationship_start(10, 10, cfg) == 15
    assert relationship_start(1, 20, cfg) >= -20


def test_trigger_table_and_caps_are_data(loaded: LoadedData) -> None:
    """16.2 and 16.3 as data: every trigger and every sized effect, with the spec's values or
    the M6.9 tuning (formulas.md 16.1, 16.2; Reece 2026-10-29)."""
    events = loaded.balance.events
    assert set(events.trigger) == set(TRIGGERS)
    t = events.trigger
    assert (t["low_morale"].below, t["low_morale"].span) == (35, 20)
    assert (t["unhappy_unit"].below, t["unhappy_unit"].span) == (45, 15)
    assert (t["underpaid"].below, t["underpaid"].span) == (0.95, 0.2)  # tuned from 0.9
    assert (t["team_clash"].at_most, t["team_clash"].span) == (-25, 30)  # tuned from -50
    assert (t["board_unhappy"].below, t["board_unhappy"].span) == (50, 15)  # tuned from 40
    assert t["runway_short"].months == [6, 3] and t["runway_short"].strength == [0.6, 1.0]
    assert t["star_performer"].top_fraction == 0.30  # tuned from 0.10
    assert t["star_performer"].tenure_months == 12
    fixed = {
        "team_bond": 0.3,  # at_least tuned from 60 to 30
        "office_politics": 0.6,
        "tag_noticed": 0.5,
        "anniversary": 0.2,
        "product_launched": 0.5,
        "product_slipping": 0.6,
        "price_war": 0.6,
        "rival_move": 0.3,
        "poached": 0.8,
        "customer_milestone": 0.4,
        "funding_closed": 0.5,
        "quiet_month": 0.2,
        "star_performer": 0.4,
    }
    assert {k: t[k].strength for k in fixed} == fixed
    caps = {
        "morale_delta": [3, 10, 20],  # minor tuned from 5
        "relationship_delta": [10, 20, 40],
        "cash_delta": [100, 300, 1000],
        "brand_delta": [2, 5, 10],
        "quality_delta": [1, 3, 6],
        "customers_pct": [1, 3, 8],
        "growth_boost": [0.2, 0.5, 1.0],
        "energy_delta": [5, 10, 15],
        "board_confidence": [3, 6, 12],
        "salary_change": [5, 10, 15],
        "modifier": [5, 10, 20],  # M10b (23.2): percent of a stat while it runs
    }
    assert events.caps == caps
    assert events.modifier_months == [6, 12, 12]
    # M10: loan effects are shares of debt.breach's sizes, not capped in events.caps (20.3).
    loan = {"loan_fee", "loan_rate", "loan_repay"}
    unsized = {"reveal_tag", "resign", "follow_up", "retain", "public_step", "press_step"}
    unsized |= {"founder_step"}  # M24 (32): an engine step
    unsized |= {"group_step"}  # M16 (31.6): an engine step
    unsized |= {"exploration_step"}  # M18 (34.3): an engine step
    unsized |= {"refining_step"}  # M20 (36.4): an engine step
    unsized |= {"mining_step"}  # M19 (35.4): an engine step
    assert set(caps) | unsized | loan == set(EFFECT_TYPES)
    assert SEVERITIES == ("minor", "major", "critical")
    assert events.count_weights == [0.08, 0.40, 0.38, 0.14]  # tuned from [0.15, 0.50, 0.28, 0.07]
    assert sum(n * w for n, w in enumerate(events.count_weights)) == pytest.approx(1.58)
    assert (events.template_cooldown_turns, events.person_cooldown_turns) == (12, 4)
