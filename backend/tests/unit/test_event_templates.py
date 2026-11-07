"""Event templates load and are checked (docs/formulas.md 16.4, M6 sub-task 4): about 60,
every trigger covered by a minor template and the critical trigger by a critical one,
placeholders and targets resolvable, effects within caps; and broken templates are refused."""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest
from pydantic import ValidationError

from tst.loader import LoadedData
from tst.sim.events.data import (
    CRITICAL_TRIGGERS,
    TRIGGERS,
    EventTemplate,
    template_problems,
)


def test_the_library(loaded: LoadedData) -> None:
    templates = loaded.game_data.event_templates
    assert Counter(t.category for t in templates) == {
        "personnel": 25,  # M6: 20; M7a: +4; M10b: key exit (23.3)
        "market": 16,  # M6: 12; M7a: +2; M10b: the press storyline (23.3)
        "operations": 15,  # M6: 10; M7a: +2; M10b: breach and outage (23.3); M12a: 22.5
        "finance": 8,
        "board": 6,
        "rivals": 4,
        "founder": 14,  # M7a: early days (trigger early_days)
        "lender": 2,  # M10: queued by the debt phase (20.3)
        "public": 11,  # M13: IPO chain and public life (25); M14: takeover_offer
        "press": 10,  # M14b: press moments, queued by the engine (29.1)
        "executive": 5,  # M10c: executives ask and clash (24.3)
        "research": 4,  # M11: breakthroughs and dead ends (21.3)
    }
    for trigger in TRIGGERS:
        assert any(t.trigger == trigger and "minor" in t.severities for t in templates), trigger
    for trigger in CRITICAL_TRIGGERS:
        assert any(t.trigger == trigger and t.is_critical for t in templates)
    stories = {t.storyline.key for t in templates if t.storyline}
    assert stories == {
        "cofounder_tension",
        "burnout",
        "key_customer",
        "investor_say",
        "poaching_war",
        "press_scrutiny",  # M10b: its second step is a press crisis (23.3)
    }
    for key in stories:
        steps = sorted(
            t.storyline.step for t in templates if t.storyline and t.storyline.key == key
        )  # type: ignore[union-attr]
        assert 2 <= len(steps) <= 4 and steps == list(range(1, len(steps) + 1))
    assert template_problems(templates) == []


def _template(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "t",
        "category": "personnel",
        "trigger": "low_morale",
        "severities": ["minor"],
        "weight": 1.0,
        "title": "{person}",
        "body": "Body",
        "choices": [
            {
                "key": "A",
                "label": "A",
                "effects": [{"type": "morale_delta", "target": "person", "share": 0.5}],
            },
            {"key": "B", "label": "B", "do_nothing": True},  # 23.2: said as such
        ],
    }
    base.update(changes)
    return base


@pytest.mark.parametrize(
    "changes",
    [
        {"category": "weather"},
        {"trigger": "full_moon"},
        {"title": "{nobody}"},
        {"choices": [{"key": "A", "label": "only one"}]},
        {"choices": [{"key": "B", "label": "x"}, {"key": "A", "label": "y"}]},
        {
            "choices": [
                {
                    "key": "A",
                    "label": "x",
                    "effects": [{"type": "teleport", "target": "person", "share": 1}],
                },
                {"key": "B", "label": "y"},
            ]
        },
        {
            "choices": [
                {
                    "key": "A",
                    "label": "x",
                    "effects": [{"type": "morale_delta", "target": "person", "share": 1.5}],
                },
                {"key": "B", "label": "y"},
            ]
        },
        {
            "choices": [
                {
                    "key": "A",
                    "label": "x",
                    "effects": [{"type": "cash_delta", "target": "person", "share": -0.5}],
                },
                {"key": "B", "label": "y"},
            ]
        },
        {
            "choices": [
                {
                    "key": "A",
                    "label": "x",
                    "effects": [{"type": "salary_change", "target": "person", "share": -0.5}],
                },
                {"key": "B", "label": "y"},
            ]
        },
        {
            "choices": [
                {"key": "A", "label": "x", "effects": [{"type": "resign", "target": "person"}]},
                {"key": "B", "label": "y"},
            ]
        },
        {
            "choices": [
                {"key": "A", "label": "x", "effects": [{"type": "follow_up"}]},
                {"key": "B", "label": "y"},
            ]
        },
    ],
)
def test_a_broken_template_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        EventTemplate.model_validate(_template(**changes))


def test_cross_template_problems(loaded: LoadedData) -> None:
    templates = loaded.game_data.event_templates
    unresolvable = EventTemplate.model_validate(
        _template(id="needs_rival", trigger="low_morale", title="{rival} calls {person}")
    )
    problems = template_problems((*templates, unresolvable))
    assert any("needs_rival" in p and "rival" in p for p in problems)
    only_major = tuple(
        t if t.trigger != "anniversary" else t.model_copy(update={"severities": ("major",)})
        for t in templates
    )
    assert any("anniversary" in p for p in template_problems(only_major))
    no_critical = tuple(t for t in templates if not t.is_critical)
    assert any("runway_short" in p for p in template_problems(no_critical))
    assert any("duplicate" in p for p in template_problems((*templates, templates[0])))
