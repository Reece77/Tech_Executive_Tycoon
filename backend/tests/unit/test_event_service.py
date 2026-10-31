"""The event service, validator and context builder (docs/formulas.md 16.3, 16.5; ADR-0005;
M6 sub-task 5): no draft can apply an effect outside the catalog, a target outside the
eligible list or a value beyond its cap; a draft rejected twice becomes the template; the
budget and the template mode never call an adapter; no prompt carries a hidden value."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game, make_person, with_employee, with_product
from tst.events.context import Kpis, build_prompt
from tst.events.coo import KpiMonth, coo_prompt
from tst.events.drafts import template_draft
from tst.events.service import Writer, write_event
from tst.events.validator import Rejection, ValidatedEvent, allowed_effects, validate_event
from tst.llm.offline import MockLLMAdapter, TemplateAdapter
from tst.llm.settings import LLMSettings, ModelPrice
from tst.loader import LoadedData
from tst.sim.coo import briefing
from tst.sim.events.data import EFFECT_TYPES, VALUELESS
from tst.sim.events.director import eligible_targets
from tst.sim.events.formulas import effect_cap
from tst.sim.events.models import GameEvent
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_event, with_person_state, with_reveal

KPIS = Kpis(cash_cents=50_000_000, runway_months=14, mrr_cents=10_000_000, headcount=3, stage=1)
PRIYA = 2


_STATES: dict[int, GameState] = {}


def _state(loaded: LoadedData) -> GameState:
    """The test company (built once: states are immutable and the property test asks 400
    times)."""
    if id(loaded) not in _STATES:
        _STATES[id(loaded)] = _build(loaded)
    return _STATES[id(loaded)]


def _build(loaded: LoadedData) -> GameState:
    state = fresh_game(loaded)
    for pid in (PRIYA, 3):
        state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000)
    state = with_product(state, customers={"smb": 30.0})
    return with_person_state(state, replace(state.person_state(PRIYA), morale=31.0))


def _event(state: GameState, template: str, severity: str = "major", **kw: Any) -> GameEvent:
    product = state.company_products(1)[0].id
    event = GameEvent(
        id=1,
        company_id=1,
        turn=state.turn,
        template_id=template,
        category="personnel",
        severity=severity,  # type: ignore[arg-type]
        trigger="low_morale",
        strength=0.5,
        person_ids=(PRIYA,),
        product_id=product,
        cash_base_cents=50_000_000,
        **kw,
    )
    return event


def _writer(adapter: Any, budget: float = 1000.0, price: float = 0.0) -> Writer:
    prices = {"mock": ModelPrice(input=price, output=price)}
    return Writer(adapter, LLMSettings(price_per_mtok_cents=prices), lambda: budget)


# --- Validator ---------------------------------------------------------------------------------

effect_st = st.fixed_dictionaries(
    {
        "type": st.sampled_from([*EFFECT_TYPES, "teleport", "fire_everyone"]),
        "target": st.sampled_from(
            [
                "person:2",
                "person:3",
                "person:99",
                "pair:1-2",
                "company:1",
                "company:7",
                "unit:4",
                "product:1",
                "product:9",
                "founder:1",
                "board",
                "",
                "rival:5",
            ]
        ),
        "value": st.one_of(st.floats(-1e9, 1e9, allow_nan=False), st.integers(-(10**9), 10**9)),
    }
)
draft_st = st.fixed_dictionaries(
    {
        "title": st.text(min_size=0, max_size=30),
        "body": st.text(min_size=0, max_size=60),
        "choices": st.lists(
            st.fixed_dictionaries(
                {
                    "key": st.sampled_from(["A", "B", "C", "Z"]),
                    "label": st.text(min_size=0, max_size=20),
                    "effects": st.lists(effect_st, max_size=6),
                }
            ),
            max_size=5,
        ),
        "storyline_summary": st.text(max_size=40),
    }
)


@settings(max_examples=400, deadline=None)
@given(draft=draft_st, severity=st.sampled_from(["minor", "major", "critical"]))
def test_no_draft_escapes_the_catalog_targets_or_caps(
    loaded: LoadedData, draft: dict[str, Any], severity: str
) -> None:
    state = _state(loaded)
    event = _event(
        state,
        "runway_payroll_crunch" if severity == "critical" else "low_morale_job_search",
        severity,
    )
    template = loaded.game_data.event_template(event.template_id)
    targets = eligible_targets(state, event)
    result = validate_event(
        draft,
        template=template,
        severity=event.severity,
        targets=targets,
        cash_base_cents=event.cash_base_cents,
        events=loaded.balance.events,
    )
    if isinstance(result, Rejection):
        return
    allowed = set(allowed_effects(template, event.severity, targets))
    assert 2 <= len(result.choices) <= 3
    assert [c.key for c in result.choices] == ["A", "B", "C"][: len(result.choices)]
    for choice in result.choices:
        assert len(choice.effects) <= 3
        for e in choice.effects:
            assert e.type in allowed
            assert e.target in targets or (e.type == "follow_up" and e.target == "")
            if e.type in VALUELESS:
                assert e.value == 0
                continue
            cap = effect_cap(
                e.type,
                event.severity,
                loaded.balance.events,
                event.cash_base_cents,
                gain=e.value > 0,
            )
            assert abs(e.value) <= cap + 1e-9
    assert len(result.body.split()) <= loaded.balance.events.body_words


def test_the_validator_clamps_and_drops(loaded: LoadedData) -> None:
    """16.11: morale +15 on a major event becomes +10; a $40,000 cost with $500,000 cash
    becomes $15,000; unknown effects and targets are dropped; resign is not allowed on a
    template that does not carry it."""
    state = _state(loaded)
    event = _event(state, "low_morale_checkin")
    template = loaded.game_data.event_template(event.template_id)
    draft = {
        "title": "Priya",
        "body": "word " * 300,
        "choices": [
            {
                "key": "A",
                "label": "Lift",
                "effects": [
                    {"type": "morale_delta", "target": "person:2", "value": 15},
                    {"type": "cash_delta", "target": "company:1", "value": -40_000},
                    {"type": "teleport", "target": "person:2", "value": 1},
                ],
            },
            {
                "key": "B",
                "label": "Push",
                "effects": [
                    {"type": "resign", "target": "person:2", "value": 0},
                    {"type": "morale_delta", "target": "person:42", "value": 3},
                ],
            },
        ],
        "storyline_summary": "",
    }
    result = validate_event(
        draft,
        template=template,
        severity="major",
        targets=eligible_targets(state, event),
        cash_base_cents=50_000_000,
        events=loaded.balance.events,
    )
    assert isinstance(result, ValidatedEvent)
    a, b = result.choices
    assert [(e.type, e.value) for e in a.effects] == [
        ("morale_delta", 10),
        ("cash_delta", -1_500_000),
    ]
    assert b.effects == ()
    assert len(result.body.split()) == 180
    assert result.dropped >= 4


# --- Service -----------------------------------------------------------------------------------


def test_a_twice_rejected_draft_becomes_the_template(loaded: LoadedData) -> None:
    state = _state(loaded)
    event = _event(state, "low_morale_checkin")
    state = with_event(state, event)
    bad = {"title": "x", "body": "y", "choices": []}
    adapter = MockLLMAdapter([bad, None])
    writer = _writer(adapter)
    out = write_event(state, event, KPIS, writer, loaded.balance, loaded.game_data)
    written = out.event(event.id)
    assert written is not None and written.status == "open" and written.source == "template"
    assert len([c for c in adapter.calls]) == 2  # one retry
    assert adapter.calls[1].retry_note is not None  # type: ignore[union-attr]
    assert writer.rejected == 1 and [r.outcome for r in writer.records] == ["rejected", "rejected"]
    template = loaded.game_data.event_template(event.template_id)
    assert (
        written.title
        == template_draft(state, event, template, loaded.balance, loaded.game_data)["title"]
    )


def test_a_good_draft_is_used_and_counted(loaded: LoadedData) -> None:
    state = _state(loaded)
    event = _event(state, "low_morale_checkin")
    state = with_event(state, event)
    writer = _writer(MockLLMAdapter(), price=100.0)
    out = write_event(state, event, KPIS, writer, loaded.balance, loaded.game_data)
    written = out.event(event.id)
    assert written is not None and written.source == "mock" and written.title.startswith("[mock]")
    assert writer.spent_cents > 0 and writer.records[0].input_tokens > 0


def test_templates_and_an_empty_budget_call_no_adapter(loaded: LoadedData) -> None:
    for writer in (_writer(TemplateAdapter()), _writer(MockLLMAdapter(), budget=0.0)):
        state = _state(loaded)
        event = _event(state, "low_morale_checkin")
        state = with_event(state, event)
        out = write_event(state, event, KPIS, writer, loaded.balance, loaded.game_data)
        assert out.event(event.id).source == "template"  # type: ignore[union-attr]
        if isinstance(writer.adapter, MockLLMAdapter):
            assert writer.adapter.calls == []
            assert [r.outcome for r in writer.records] == ["budget"]


def test_the_budget_stops_calls_at_the_limit(loaded: LoadedData) -> None:
    """With a price per call and a budget for about two calls, the third event is a
    template and the spend stops at the limit."""
    adapter = MockLLMAdapter()
    writer = _writer(adapter, budget=0.05, price=10_000.0)
    state = _state(loaded)
    sources = []
    for i in range(1, 6):
        event = replace(_event(state, "low_morale_checkin"), id=i)
        state = with_event(state, event)
        state = write_event(state, event, KPIS, writer, loaded.balance, loaded.game_data)
        sources.append(state.event(i).source)  # type: ignore[union-attr]
    assert "mock" in sources and sources[-1] == "template"
    calls = len([c for c in adapter.calls])
    assert calls < 5
    assert (
        writer.spent_cents >= 0.05 > writer.spent_cents - max(r.cost_cents for r in writer.records)
    )


# --- Context hygiene (ADR-0005 section 4) ---------------------------------------------------------


def test_no_prompt_contains_a_hidden_value(loaded: LoadedData) -> None:
    """Plant unmistakable hidden values (potential, hidden traits, true skills, an unnoticed
    tag, a rival's cash) and build every kind of prompt: none of them may appear."""
    state = fresh_game(loaded)
    priya = make_person(loaded, PRIYA)
    planted_skill = 17.3456
    priya = replace(
        priya,
        potential_ability=187.6543,
        tags=("toxic_high_performer",),
        skills=priya.skills.updated({k: planted_skill for k, _ in priya.skills.items}),
        hidden=priya.hidden.updated({k: 19.8765 for k, _ in priya.hidden.items}),
        personality=priya.personality.updated({"loyalty": 3.1415, "ambition": 18.2718}),
    )
    state = with_employee(loaded, state, priya, 9_123_456)
    state = with_reveal(
        state,
        new_reveal_state(
            observer_company_id=1,
            person=priya,
            turn=state.turn,
            rng=RngFactory(1),
            data=loaded.game_data,
            balance=loaded.balance,
        ),
    )
    state = with_product(state, customers={"smb": 12.0})
    rival = next(c for c in state.companies if not c.is_player)
    texts = []
    for template in loaded.game_data.event_templates:
        event = replace(
            _event(state, template.id, "critical" if template.is_critical else "major"),
            rival_id=rival.id,
            months=2,
            person_ids=(PRIYA,),
        )
        system, user = build_prompt(
            state,
            event,
            template,
            eligible_targets(state, event),
            KPIS,
            loaded.balance,
            loaded.game_data,
        )
        texts.append(system + user)
    # Ask my COO (M7b, 17.3): the briefing, the allowlist and the KPIs, as Priya answers.
    issues = briefing(state, 1_000_000, loaded.balance, loaded.game_data)
    kpis = [KpiMonth("Jan 2010", 40_000_000, 1_000_000, 0, 2, 65.0, None)]
    for who in (PRIYA, None):
        system, user = coo_prompt(state, who, issues, kpis, "Who is best?", 200, loaded.game_data)
        texts.append(system + user)
    blob = "\n".join(texts)
    for planted in (
        "187.6",
        "187",
        "19.87",
        "17.34",
        "3.14",
        "18.27",
        "toxic",
        "Toxic",
        "potential",
    ):
        assert planted not in blob, planted
    assert priya.first_name in blob  # people are named
