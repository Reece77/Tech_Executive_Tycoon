"""M10b event modifiers (docs/formulas.md 23.2): a chosen modifier starts at once, changes its
stat every month for its months, then expires; values and months are held to the severity's
caps; the validator takes only the template's own stats; effects read as numbers."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game, make_person, with_employee, with_product
from tests.unit.test_event_effects import A, _open
from tst.events.validator import ValidatedEvent, validate_event
from tst.loader import LoadedData, load_all
from tst.sim.actions import ChooseEvent, apply_action
from tst.sim.events import modifiers as mf
from tst.sim.events.describe import choice_texts, month_choices
from tst.sim.events.models import Effect, EventChoice
from tst.sim.hiring.phases import reset_energy
from tst.sim.org.morale import morale_terms
from tst.sim.org.rules import org_view
from tst.sim.products.phases import team_of
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_event

LOADED = load_all(DATA_DIR)
FOUNDER = 1


def _state(loaded: LoadedData) -> GameState:
    state = fresh_game(loaded)
    state = with_employee(loaded, state, make_person(loaded, A), 9_000_000)
    return with_product(state, customers={"smb": 100.0}, quality=40.0, brand=10.0)


def _choose(loaded: LoadedData, state: GameState, effects: tuple[Effect, ...], **kw: object):  # type: ignore[no-untyped-def]
    event = _open(state, (EventChoice("A", "Take it", effects), EventChoice("B", "No")), **kw)
    state = with_event(state, event)
    return apply_action(
        state,
        ChooseEvent(FOUNDER, event.id, "A"),
        RngFactory(1),
        loaded.balance,
        loaded.game_data,
        {(1, "1000_cash"): 10**10},
        seq=1,
    ).new_state


def test_a_brand_target_modifier_runs_then_expires(loaded: LoadedData) -> None:
    state = _state(loaded)
    product = state.company_products(1)[0]
    target = f"product:{product.id}"
    before = team_of(state, org_view(state, 1), product, loaded.balance, loaded.game_data)
    after = _choose(loaded, state, (Effect("modifier", target, 10.0, "brand_target", 3),))
    (m,) = after.modifiers
    assert (m.stat, m.value_pct, m.start_turn, m.end_turn) == ("brand_target", 10.0, 0, 3)
    team = team_of(after, org_view(after, 1), product, loaded.balance, loaded.game_data)
    assert team.brand_mult == before.brand_mult * 1.10
    for turn in range(3):
        current = replace(after, turn=turn)
        assert mf.product_factor(current, 1, product.id, "brand_target") == 1.10
        current, gone = mf.expire(current)
        assert bool(gone) == (turn == 2)  # its last month is the third
    late = replace(after, turn=3)
    assert mf.product_factor(late, 1, product.id, "brand_target") == 1.0


def test_major_caps_value_and_months(loaded: LoadedData) -> None:
    state = _state(loaded)
    product = state.company_products(1)[0]
    after = _choose(
        loaded, state, (Effect("modifier", f"product:{product.id}", 50.0, "churn", 40),)
    )
    (m,) = after.modifiers
    assert (m.value_pct, m.end_turn - m.start_turn) == (10.0, 12)  # major: 10%, 12 months


def test_morale_target_and_founder_energy(loaded: LoadedData) -> None:
    state = _state(loaded)
    b, data = loaded.balance, loaded.game_data
    employment = state.employment_of(A)
    assert employment is not None
    view = org_view(state, 1)
    plain = morale_terms(state, view, employment, b, data, 10**9, 10**9).target
    after = _choose(
        loaded,
        state,
        (
            Effect("modifier", f"person:{A}", 10.0, "morale_target", 6),
            Effect("modifier", f"founder:{FOUNDER}", -10.0, "founder_energy", 6),
        ),
    )
    boosted = morale_terms(after, view, employment, b, data, 10**9, 10**9).target
    assert boosted == plain * 1.10
    energy = reset_energy(after, b, data).person_state(FOUNDER).energy
    assert energy == round(b.founder.energy_per_month * 0.9)


def test_effects_read_as_numbers(loaded: LoadedData) -> None:
    state = _state(loaded)
    product = state.company_products(1)[0]
    event = _open(state, ())
    texts = choice_texts(
        state,
        event,
        EventChoice(
            "A",
            "x",
            (
                Effect("cash_delta", "company:1", -800_000.0),
                Effect("brand_delta", f"product:{product.id}", 3.0),
                Effect("modifier", f"product:{product.id}", 5.0, "brand_target", 12),
            ),
        ),
        loaded.balance,
    )
    assert texts == [
        "costs $8,000",
        f"+3 brand for {product.name}",
        f"+5% brand target for {product.name} for 12 months",
    ]
    assert choice_texts(state, event, EventChoice("B", "No", (), True), loaded.balance) == [
        "Do nothing: no effect"
    ]
    energy = choice_texts(
        state,
        event,
        EventChoice("C", "x", (Effect("energy_delta", "founder:1", -10.0),)),
        loaded.balance,
    )
    assert energy == [chr(0x2212) + "10 founder energy next month"]  # a minus sign


def test_the_month_end_line_lists_choices_and_modifiers(loaded: LoadedData) -> None:
    state = _state(loaded)
    product = state.company_products(1)[0]
    after = _choose(
        loaded,
        state,
        (
            Effect("brand_delta", f"product:{product.id}", 3.0),
            Effect("modifier", f"product:{product.id}", 5.0, "awareness", 1),
        ),
    )
    expiring = tuple(m for m in after.modifiers if m.end_turn <= after.turn + 1)
    line = month_choices(after, expiring, 1, loaded.balance)
    assert line is not None
    assert line.startswith(f"Take it: +3 brand for {product.name}")
    assert f"Started: +5% awareness for {product.name} for 1 month" in line
    assert "Expired: +5% awareness" in line


def test_the_validator_takes_only_the_templates_stats(loaded: LoadedData) -> None:
    template = loaded.game_data.event_template("launch_press")  # awareness modifiers
    targets = ("product:24", "founder:1")
    draft = {
        "title": "T",
        "body": "B",
        "storyline_summary": "",
        "choices": [
            {
                "label": "Yes",
                "effects": [
                    {
                        "type": "modifier",
                        "target": "product:24",
                        "value": 30,
                        "stat": "awareness",
                        "months": 40,
                    },
                    {
                        "type": "modifier",
                        "target": "product:24",
                        "value": 5,
                        "stat": "churn",
                        "months": 3,
                    },
                ],
            },
            {"label": "No", "effects": [], "do_nothing": True},
        ],
    }
    out = validate_event(
        draft,
        template=template,
        severity="minor",
        targets=targets,
        cash_base_cents=10**8,
        events=loaded.balance.events,
    )
    assert isinstance(out, ValidatedEvent)
    (effect,) = out.choices[0].effects  # churn is not in launch_press's list
    assert (effect.stat, effect.value, effect.months) == ("awareness", 5.0, 6)  # minor caps
    assert out.choices[1].do_nothing and out.dropped == 2


@settings(max_examples=200, deadline=None)
@given(
    st.sampled_from(["minor", "major", "critical"]),
    st.floats(-1000, 1000, allow_nan=False),
    st.integers(-5, 60),
    st.sampled_from(sorted(mf.MODIFIER_STATS)),
    st.integers(0, 30),
)
def test_modifiers_never_exceed_caps_and_always_expire(
    severity: str, value: float, months: int, stat: str, turn: int
) -> None:
    events = LOADED.balance.events
    state = replace(_state(LOADED), turn=turn)
    product = state.company_products(1)[0]
    word = mf.MODIFIER_STATS[stat][0]
    target = {
        "product": f"product:{product.id}",
        "person": f"person:{A}",
        "founder": f"founder:{FOUNDER}",
    }[word]
    effect = Effect("modifier", target, value, stat, months)
    started = mf.start(state, 1, None, effect, severity, events)  # type: ignore[arg-type]
    cap, longest = events.cap("modifier", severity), events.max_months(severity)
    for m in started.modifiers:
        assert -cap <= m.value_pct <= cap
        assert 1 <= m.end_turn - m.start_turn <= longest
    # Month ends roll on: within the longest duration every modifier has left the state.
    current = started
    for _ in range(longest):
        current, _ = mf.expire(current)
        current = replace(current, turn=current.turn + 1)
    assert current.modifiers == ()


# 23.7 target 2: templates whose story implies a benefit carry a matching modifier (the
# review list in docs/tasks/M10b-feel-fixes.md, Decisions made).
BENEFIT_TEMPLATES = (
    "early_domain_name",
    "early_mentor_offer",
    "early_customer_interviews",
    "early_meetup_talk",
    "early_coworking_desk",
    "early_accelerator_invite",
    "early_open_source",
    "early_advisor",
    "launch_press",
    "launch_hacker_news",
    "milestone_case_study",
    "milestone_customers",
    "milestone_user_group",
    "quiet_analyst_call",
    "quiet_award",
    "quiet_meetup",
    "rival_move_trade_show",
    "quiet_tooling",
    "star_conference_talk",
    "support_backlog",
    "slipping_tech_debt",
    "unhappy_unit_retro",
    "launch_night_outage",
    "rival_price_war",
    "price_war_customers_ask",
    "key_customer_2",
    "poaching_war_2",
    "funding_party",
)


def test_every_choice_has_an_effect_or_says_do_nothing(loaded: LoadedData) -> None:
    for t in loaded.game_data.event_templates:
        assert any(c.effects for c in t.choices), t.id
        for c in t.choices:
            assert bool(c.effects) != c.do_nothing, (t.id, c.key)


def test_benefit_templates_carry_a_modifier(loaded: LoadedData) -> None:
    for tid in BENEFIT_TEMPLATES:
        template = loaded.game_data.event_template(tid)
        assert template.modifier_stats(), tid
