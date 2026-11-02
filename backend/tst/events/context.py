"""The context builder (docs/formulas.md 16.5; ADR-0005 section 4): an allowlist of what the
player could plausibly know, never true attributes, potential, hidden tags or numbers the API
would not show. People are described by name, role, level, tenure, morale, and their skills
as words from the player's displayed ranges; tags only once noticed; interests only once the
profile is known. Everything is built from these fields and nothing else.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from tst.events.validator import allowed_effects
from tst.sim.data_models import Balance, GameData
from tst.sim.events.data import EFFECT_TARGETS, MODIFIER_STATS, EventTemplate
from tst.sim.events.formulas import effect_cap
from tst.sim.events.models import GameEvent
from tst.sim.events.render import full_name
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState

STRONG_AT, WEAK_AT = 14, 6  # tunable-exempt: words for displayed 1-20 ranges
CENTS_PER_DOLLAR = 100  # tunable-exempt: unit conversion
MONTHS_PER_YEAR = 12  # tunable-exempt: calendar

SYSTEM = (
    "You write events for a single-player business game about running a tech startup that "
    "began in January 2010. The engine has already decided that this event happens, who it "
    "is about, how serious it is and which effects are allowed. You write the words: a short "
    "title, a body of at most {body_words} words in the second person addressed to the "
    "founder, and two or three choices. Each choice may carry up to three effects, chosen "
    "only from the allowed effects, aimed only at the listed targets, with values within the "
    "caps (cash in dollars; negative is a cost). The first choice is what happens if the "
    "player does not answer, so make it the reasonable default. Never invent people, "
    "companies or numbers that are not in the context. Use names, not pronouns, for people. "
    "Tone: {tone}. Return only the JSON object."
)
GROUNDED = "grounded business realism"
LIGHT = "grounded, with a light or gently satirical touch this time"


@dataclass(frozen=True, slots=True)
class Kpis:
    """The company numbers the player sees on the Overview."""

    cash_cents: int
    runway_months: int | None
    mrr_cents: int
    headcount: int
    stage: int


def _person(state: GameState, company_id: int, person_id: int, data: GameData) -> dict[str, Any]:
    person = state.person(person_id)
    employment = state.employment_of(person_id)
    reveal = state.reveal(company_id, person_id)
    out: dict[str, Any] = {"name": full_name(person)}
    if employment is not None:
        role = "founder" if employment.role == "founder" else data.role(employment.role).label
        out.update(
            role=role,
            level=employment.level,
            tenure_months=state.turn - employment.start_turn,
        )
    ps = state.person_state(person_id)
    if ps.morale is not None:
        out["morale"] = round(ps.morale)
    if reveal is not None:
        labels = {s.key: s.label for s in data.skills}
        strong, weak = [], []
        for skill in data.skill_keys:
            lo, hi = revealed_range(person, reveal, skill)
            mid = (lo + hi) / 2
            label = labels[skill].lower()
            if mid >= STRONG_AT:
                strong.append(label)
            elif mid <= WEAK_AT and hi - lo <= WEAK_AT:
                weak.append(label)
        if strong:
            out["strong_at"] = strong
        if weak:
            out["weak_at"] = weak
        tags = {t.key: t.label for t in data.tags}
        noticed = [tags[t] for t, _ in reveal.revealed_tags]
        if noticed:
            out["noticed"] = noticed
        if reveal.profile_revealed_turn is not None:
            out["interests"] = list(person.interests)
    return out


def facts(state: GameState, event: GameEvent, data: GameData) -> list[str]:
    """The situation in plain words, from values the player can see (16.5)."""
    out: list[str] = []
    for pid in event.person_ids:
        person = state.person(pid)
        employment = state.employment_of(pid)
        ps = state.person_state(pid)
        name = full_name(person)
        if ps.morale is not None:
            out.append(f"{name}'s morale is {round(ps.morale)} out of 100.")
        if employment is not None and employment.role != "founder":
            mid = data.role(employment.role).salary_band_mid_cents[employment.level]
            ratio = employment.salary_cents / mid if mid else 1.0
            out.append(
                f"{name} is paid ${employment.salary_cents // CENTS_PER_DOLLAR:,} a year, "
                f"{ratio:.2f} of the usual rate for the role and level."
            )
            years = (state.turn - employment.start_turn) // MONTHS_PER_YEAR
            if years:
                out.append(f"{name} has been at the company {years} year(s).")
    if event.months is not None:
        out.append(f"At the current burn the company has about {event.months} months of cash.")
    if event.rival_id is not None:
        rival = state.company(event.rival_id)
        out.append(f"The rival involved is {rival.name}.")
    if event.product_id is not None:
        product = state.product(event.product_id)
        if product is not None:
            customers = sum(s.customers for s in state.segments_of(product.id))
            out.append(f"{product.name} has about {round(customers)} customers.")
    return out


def build_prompt(
    state: GameState,
    event: GameEvent,
    template: EventTemplate,
    targets: tuple[str, ...],
    kpis: Kpis,
    balance: Balance,
    data: GameData,
) -> tuple[str, str]:
    """(system, user) for one event. The user message is JSON built from the allowlist."""
    ev = balance.events
    cid = event.company_id
    company = state.company(cid)
    people = []
    for target in targets:
        kind, _, rest = target.partition(":")
        if kind in ("person", "founder") and rest.isdigit():
            people.append({"target": target, **_person(state, cid, int(rest), data)})
    products = []
    for target in targets:
        kind, _, rest = target.partition(":")
        if kind == "product" and rest.isdigit():
            product = state.product(int(rest))
            if product is not None:
                products.append(
                    {
                        "target": target,
                        "name": product.name,
                        "status": product.status.replace("_", " "),
                    }
                )
    allowed = []
    for effect in allowed_effects(template, event.severity, targets):
        cap = effect_cap(effect, event.severity, ev, event.cash_base_cents, gain=False)
        entry: dict[str, Any] = {"type": effect, "targets": list(EFFECT_TARGETS[effect])}
        if effect == "cash_delta":
            entry["max_cost_dollars"] = round(cap / CENTS_PER_DOLLAR)
            entry["max_gain_dollars"] = round(cap * ev.cash_gain_share / CENTS_PER_DOLLAR)
        elif effect == "modifier":  # M10b (23.2): percent a month, for at most max_months
            entry["max_percent"] = cap
            entry["max_months"] = ev.max_months(event.severity)
            entry["stats"] = {s: list(MODIFIER_STATS[s]) for s in sorted(template.modifier_stats())}
        elif cap:
            entry["max"] = cap
        allowed.append(entry)
    recent = [
        f"{e.title} (chose: {c.label})" if (c := e.choice(e.chosen or "")) else e.title
        for e in sorted(state.events, key=lambda e: -e.id)
        if e.company_id == cid and e.id != event.id and e.title
    ][: ev.recent_summaries]
    stories = [
        {"title": s.title, "summary": s.summary}
        for s in state.storylines
        if s.company_id == cid and s.status == "active"
    ]
    story = state.storyline(event.storyline_id) if event.storyline_id is not None else None
    context: dict[str, Any] = {
        "company": {
            "name": company.name,
            "stage": kpis.stage,
            "cash_dollars": kpis.cash_cents // CENTS_PER_DOLLAR,
            "runway_months": kpis.runway_months,
            "monthly_revenue_dollars": kpis.mrr_cents // CENTS_PER_DOLLAR,
            "headcount": kpis.headcount,
        },
        "category": event.category,
        "severity": event.severity,
        "situation": facts(state, event, data),
        "people": people,
        "products": products,
        "rival": state.company(event.rival_id).name if event.rival_id is not None else None,
        "eligible_targets": list(targets),
        "allowed_effects": allowed,
        "recent_events": recent,
        "active_storylines": stories,
        "this_storyline": {"title": story.title, "summary": story.summary} if story else None,
        "template_idea": {"title": template.title, "body": " ".join(template.body.split())},
    }
    system = SYSTEM.format(
        body_words=ev.body_words, tone=LIGHT if event.tone == "light" else GROUNDED
    )
    if story is not None:
        system += (
            " This event is a step in an ongoing storyline: continue it, and write a new "
            f"storyline_summary of at most {ev.summary_words} words."
        )
    else:
        system += " Leave storyline_summary empty."
    return system, json.dumps(context, indent=1, sort_keys=True)


def text_prompt(kind: str, lines: list[str], company_name: str) -> tuple[str, str]:
    """Read-only text (16.8): the facts to write from, as plain lines."""
    asks = {
        "headlines": "Write two or three one-line newspaper headlines about this month in the "
        "tech market, one per line, no numbering. Use only these facts.",
        "minutes": "Write a short paragraph (at most 80 words) of board meeting minutes for "
        f"{company_name}. Use only these facts.",
        "exec_report": "Rewrite this executive's quarterly report to the founder in their own "
        "voice, first person, at most 120 words: their numbers, what they did and their "
        "concerns. Use only these facts; keep every number as given.",
        "exit_line": "Write one line, in quotes, that this person said in their exit "
        "interview. Use only these facts; no numbers.",
    }
    system = "You write short flavour text for a business game. Grounded, plain English."
    return system, asks[kind] + "\n\n" + "\n".join(f"- {line}" for line in lines)
