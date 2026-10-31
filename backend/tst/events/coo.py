"""The "Ask my COO" prompt (docs/formulas.md 17.3; ADR-0005): the briefing, the 16.5 allowlist
context and the last 12 months of the player's KPIs. Only what the player could see; the
answer is read-only text and is never fed into events."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from tst.events.context import _person
from tst.sim.coo import Issue
from tst.sim.data_models import GameData
from tst.sim.events.render import full_name
from tst.sim.state import GameState

CENTS_PER_DOLLAR = 100  # tunable-exempt: unit conversion
OFFLINE = "I can't think that through right now."
NOTEBOOK = "Founder's notebook"
STAFF_LISTED = 12  # tunable-exempt: people named in the context, by seniority

SYSTEM = (
    "You are {speaker} at {company}, a tech startup in a business game that began in January "
    "2010. The founder asks you a question. Answer in plain prose, at most {words} words, in "
    "your own voice as {speaker}. Use only the numbers and facts given; never invent people, "
    "companies or figures. If the facts do not answer the question, say that you don't know."
)


@dataclass(frozen=True, slots=True)
class KpiMonth:
    """One month end as the Overview shows it."""

    date_label: str
    cash_cents: int
    burn_cents: int
    arr_cents: int
    headcount: int
    avg_morale: float | None
    board_confidence: float | None


def speaker(state: GameState, person_id: int | None, data: GameData) -> str:
    if person_id is None:
        return "the founder, thinking aloud in a notebook"
    employment = state.employment_of(person_id)
    role = data.role(employment.role).label if employment is not None else "an employee"
    return f"{full_name(state.person(person_id))}, {role}"


def offline_reply(issues: Sequence[Issue]) -> str:
    """The reply offline, over budget or after an error: the briefing still helps."""
    if not issues:
        return f"{OFFLINE} Nothing urgent on my list, though."
    return OFFLINE + " Here is what is on my list:\n" + "\n".join(f"- {i.text}" for i in issues)


def coo_prompt(
    state: GameState,
    person_id: int | None,
    issues: Sequence[Issue],
    kpis: Sequence[KpiMonth],
    question: str,
    words: int,
    data: GameData,
) -> tuple[str, str]:
    """(system, user) for one question. People are described as the 16.5 allowlist does."""
    company = state.player
    staff = sorted(
        state.staff(company.id), key=lambda e: (e.role != "founder", e.start_turn, e.person_id)
    )[:STAFF_LISTED]
    context: dict[str, Any] = {
        "company": company.name,
        "stage": company.stage,
        "date": kpis[-1].date_label if kpis else "January 2010",
        "people": [_person(state, company.id, e.person_id, data) for e in staff],
        "products": [
            {"name": p.name, "status": p.status} for p in state.company_products(company.id)
        ],
        "last_12_months": [
            {
                "month": k.date_label,
                "cash_dollars": k.cash_cents // CENTS_PER_DOLLAR,
                "burn_dollars": k.burn_cents // CENTS_PER_DOLLAR,
                "arr_dollars": k.arr_cents // CENTS_PER_DOLLAR,
                "headcount": k.headcount,
                "average_morale": None if k.avg_morale is None else round(k.avg_morale),
                "board_confidence": None
                if k.board_confidence is None
                else round(k.board_confidence),
            }
            for k in kpis
        ],
    }
    briefing = "\n".join(f"- {i.text}" for i in issues) or "- Nothing urgent."
    who = speaker(state, person_id, data)
    system = SYSTEM.format(speaker=who, company=company.name, words=words)
    user = (
        f"Briefing:\n{briefing}\n\nContext:\n{json.dumps(context, indent=1)}\n\n"
        f"The founder asks: {question}"
    )
    return system, user
