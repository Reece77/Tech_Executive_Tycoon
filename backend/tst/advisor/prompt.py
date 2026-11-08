"""The "Ask why" prompt (M25 section 1; ADR-0005; formulas.md 16.5 and 17.3): one number's
breakdown, its trend, its drivers, related events and the 16.5 allowlist of company KPIs.
Built from an Explanation, which holds only shown values, and from allowlisted people
descriptions. The model explains; it never decides, and its answer is never fed back."""

from __future__ import annotations

import json
from typing import Any

from tst.advisor.model import Explanation
from tst.advisor.template import amount
from tst.events.context import Kpis, _person
from tst.sim.calendar import format_turn
from tst.sim.data_models import GameData
from tst.sim.state import GameState

CENTS_PER_DOLLAR = 100  # tunable-exempt: unit conversion

SYSTEM = (
    "You are {speaker} at {company}, a tech startup in a business game that began in January "
    "2010. The founder clicked a number on a screen and asks you why it is what it is. "
    "Answer in plain prose, at most {words} words, in your own voice as {speaker}. Explain "
    "only from the numbers and facts given: its breakdown, its trend, its drivers and the "
    "events listed. Never invent people, companies, causes or figures, and never recommend "
    "a course of action as if you had taken it. If the facts do not explain it, say plainly "
    "that you don't know."
)


def _value(v: float | None, unit: str) -> str | None:
    return None if v is None else amount(v, unit)  # type: ignore[arg-type]


def context(e: Explanation, kpis: Kpis, template: str) -> dict[str, Any]:
    unit = e.metric.unit
    return {
        "number": {
            "name": e.metric.label,
            "what_it_is": e.metric.description,
            "of": e.subject,
            "now": _value(e.value, unit),
        },
        "breakdown": [{"line": i.label, "amount": amount(i.amount, i.unit)} for i in e.items],
        "breakdown_note": e.note,
        "last_months": [
            {"month": format_turn(p.turn), "value": amount(p.value, unit)} for p in e.trend
        ],
        "trend_note": e.trend_note,
        "drivers_of_the_last_change": [
            {
                "driver": d.label,
                **(
                    {"its_effect": amount(d.effect, unit, signed=True)}
                    if d.effect is not None
                    else {}
                ),
                **(
                    {"its_own_move": amount(d.change, d.unit, signed=True)}
                    if d.change is not None and d.unit is not None
                    else {}
                ),
                **({"kind": "a term of the number as it stands"} if d.kind == "level" else {}),
            }
            for d in e.drivers
        ],
        "related_events": list(e.related),
        "reading_of_the_breakdown": template,
        "company": {
            "cash_dollars": kpis.cash_cents // CENTS_PER_DOLLAR,
            "runway_months": kpis.runway_months,
            "mrr_dollars": kpis.mrr_cents // CENTS_PER_DOLLAR,
            "headcount": kpis.headcount,
            "stage": kpis.stage,
        },
    }


def explain_prompt(
    state: GameState,
    e: Explanation,
    kpis: Kpis,
    template: str,
    speaker: str,
    question: str,
    words: int,
    data: GameData,
) -> tuple[str, str]:
    """(system, user) for one question about one number. A person's number adds that
    person as the 16.5 allowlist describes them, and nothing more."""
    ctx = context(e, kpis, template)
    if e.metric.scope == "person" and e.entity is not None:
        ctx["person"] = _person(state, state.player.id, int(e.entity), data)
    system = SYSTEM.format(speaker=speaker, company=state.player.name, words=words)
    user = (
        f"Date: {format_turn(state.turn)}\n\nContext:\n{json.dumps(ctx, indent=1)}\n\n"
        f"The founder asks: {question}"
    )
    return system, user
