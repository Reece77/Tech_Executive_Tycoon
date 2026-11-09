"""A template's own draft for one event (docs/formulas.md 16.4), in the JSON shape the LLM
returns (spec 12): the offline mode, the fallback, and what MockLLMAdapter starts from.
Effect values are in the effect's units, cash in dollars, as the LLM is asked to write them.
"""

from __future__ import annotations

from typing import Any

from tst.sim.data_models import Balance, GameData
from tst.sim.events.data import EventTemplate
from tst.sim.events.formulas import share_value
from tst.sim.events.models import GameEvent
from tst.sim.events.render import loan_names, placeholder_names, render
from tst.sim.markets_public.describe import public_names
from tst.sim.press.names import press_names
from tst.sim.state import GameState

CENTS_PER_DOLLAR = 100  # tunable-exempt: unit conversion


def target_string(state: GameState, event: GameEvent, word: str) -> str | None:
    """A template target word as an eligible-list entry for this event; None if it cannot
    be named (the effect is then left out)."""
    cid = event.company_id
    founder = state.founder_of(cid)
    people = event.person_ids
    if word == "person":
        return f"person:{people[0]}" if people else None
    if word == "other":
        return f"person:{people[1]}" if len(people) > 1 else None
    if word == "pair":
        if len(people) > 1:
            a, b = sorted(people[:2])
        elif people and founder is not None:
            a, b = sorted((founder.id, people[0]))
        else:
            return None
        return f"pair:{a}-{b}"
    if word == "unit":
        return f"unit:{event.unit_id}" if event.unit_id is not None else f"company:{cid}"
    if word == "company":
        return f"company:{cid}"
    if word == "product":
        return f"product:{event.product_id}" if event.product_id is not None else None
    if word == "founder":
        return f"founder:{founder.id}" if founder is not None else None
    if word == "board":
        return "board"
    if word == "loan":  # M10
        return f"loan:{event.loan_id}" if event.loan_id is not None else None
    return ""  # follow_up


def event_names(
    state: GameState, event: GameEvent, data: GameData, balance: Balance | None = None
) -> dict[str, str]:
    names = placeholder_names(
        state,
        data,
        event.company_id,
        person_ids=event.person_ids,
        unit_id=event.unit_id,
        product_id=event.product_id,
        segment=event.segment,
        rival_id=event.rival_id,
        months=event.months,
    ) | loan_names(state, data, event.loan_id)
    if event.category == "press":  # M14b (29.1)
        names |= press_names(state, data, event.company_id, event.turn)
    if balance is not None:  # M24 (32.4): the founder's strongest public trait
        from tst.sim.founder.persona import public_words

        names["persona"] = public_words(state, event.company_id, balance)
    if event.category == "geopolitics":  # M22 (39): the rule the event is about
        from tst.sim.geopolitics.events import rule_names

        names |= rule_names(state, data, event)
    if event.category == "public" and balance is not None:  # M13 (25)
        names |= public_names(state, data, balance, event.company_id)
    return names


def template_draft(
    state: GameState, event: GameEvent, template: EventTemplate, balance: Balance, data: GameData
) -> dict[str, Any]:
    names = event_names(state, event, data, balance)
    first_cost = next(
        (
            share_value(
                "cash_delta", e.share, event.severity, balance.events, event.cash_base_cents
            )
            for c in template.choices
            for e in c.effects
            if e.type == "cash_delta"
        ),
        None,
    )
    if first_cost is not None:
        names["amount"] = f"${abs(first_cost) / CENTS_PER_DOLLAR:,.0f}"
    choices = []
    for choice in template.choices:
        effects = []
        for spec in choice.effects:
            target = target_string(state, event, spec.target)
            if target is None:
                continue
            value = share_value(
                spec.type, spec.share, event.severity, balance.events, event.cash_base_cents
            )
            if spec.type == "cash_delta":
                value = value / CENTS_PER_DOLLAR
            effect: dict[str, Any] = {"type": spec.type, "target": target, "value": value}
            if spec.type == "modifier":  # M10b (23.2)
                effect |= {"stat": spec.stat, "months": spec.months}
            elif spec.type in (
                "public_step",
                "press_step",
                "founder_step",
                "group_step",
                "exploration_step",
                "mining_step",
                "geopolitics_step",
                "refining_step",
            ):  # M16, M18, M19, M20 too
                effect |= {"stat": spec.stat}
            effects.append(effect)
        choices.append(
            {
                "key": choice.key,
                "label": render(choice.label, names),
                "effects": effects,
                **({"do_nothing": True} if choice.do_nothing else {}),
            }
        )
    summary = render(template.storyline.summary, names) if template.storyline else ""
    return {
        "title": render(template.title, names),
        "body": render(template.body, names),
        "choices": choices,
        "storyline_summary": summary,
    }
