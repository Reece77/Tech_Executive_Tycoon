"""Events, storylines and relationships as the player sees them (docs/formulas.md 16.9):
effects as words with a size, relationship labels, never caps, trigger strengths or numbers."""

from __future__ import annotations

from tst.api.schemas.events import (
    EventChoiceOut,
    EventOut,
    EventStorylineOut,
    RelationshipOut,
    StorylineOut,
    TeamMoodOut,
    TeamMoodPairOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.events.effects import parse_target
from tst.sim.events.formulas import size_word
from tst.sim.events.models import Effect, GameEvent, Storyline
from tst.sim.events.render import full_name
from tst.sim.org.rules import org_view
from tst.sim.people.relationships import pair_key, relationship_label
from tst.sim.state import GameState

CATEGORY_LABELS = {
    "personnel": "People",
    "market": "Market",
    "operations": "Operations",
    "finance": "Finance",
    "board": "Board and investors",
    "rivals": "Rivals",
}
SOURCE_LABELS = {"claude": "Claude", "template": "template", "mock": "mock", "replay": "replay"}
CENTS_PER_DOLLAR = 100  # tunable-exempt: unit conversion
MONTHS_PER_YEAR = 12  # tunable-exempt: calendar


def about_dollars(cents: float) -> str:
    """Round to two significant figures: "about $8,000"."""
    dollars = abs(cents) / CENTS_PER_DOLLAR
    if dollars < 1:
        return "$1"
    digits = len(str(int(dollars)))
    step = 10 ** max(0, digits - 2)
    return f"${round(dollars / step) * step:,.0f}"


def _name(state: GameState, person_id: int) -> str:
    person = next((p for p in state.people if p.id == person_id), None)
    return full_name(person) if person else "someone who has left"


def _who(state: GameState, target: str) -> str:
    kind, ids = parse_target(target)
    if kind == "person" and ids:
        return _name(state, ids[0])
    if kind == "unit" and ids:
        unit = state.unit(ids[0])
        return unit.name if unit else "the team"
    if kind == "pair" and len(ids) == 2:  # tunable-exempt: a pair
        return f"{_name(state, ids[0])} and {_name(state, ids[1])}"
    if kind == "product" and ids:
        product = state.product(ids[0])
        return product.name if product else "the product"
    return "everyone"


def effect_words(state: GameState, event: GameEvent, effect: Effect, data: LoadedData) -> str:
    v = effect.value
    size = size_word(effect.type, v, event.severity, data.balance.events)
    sized = f"{size} " if size else ""
    up = v > 0
    who = _who(state, effect.target)
    match effect.type:
        case "morale_delta":
            return f"{sized}morale {'lift' if up else 'hit'} for {who}"
        case "relationship_delta":
            return f"{sized}{'warmer' if up else 'cooler'} relationship between {who}"
        case "cash_delta":
            return f"{'brings in' if up else 'costs'} about {about_dollars(v)}"
        case "brand_delta":
            return f"{sized}brand {'lift' if up else 'hit'} for {who}"
        case "quality_delta":
            return f"{sized}quality {'gain' if up else 'loss'} for {who}"
        case "customers_pct":
            return f"{sized}{'customer gain' if up else 'customer loss'} for {who}"
        case "growth_boost":
            return f"{sized}skill growth for {who}"
        case "reveal_tag":
            return f"you learn more about {who}"
        case "energy_delta":
            return f"{sized}{'more' if up else 'less'} energy for you next month"
        case "board_confidence":
            return f"{sized}board confidence {'lift' if up else 'drop'}"
        case "salary_change":
            _, ids = parse_target(effect.target)
            employment = state.employment_of(ids[0]) if ids else None
            if employment is None:
                return f"{sized}raise for {who}"
            cost = employment.salary_cents * v / 100  # tunable-exempt: percent
            return f"{sized}raise for {who} · costs about {about_dollars(cost)} a year"
        case "resign":
            return f"{who} leaves"
        case "follow_up":
            return "a follow-up decision comes next month"
    return effect.type.replace("_", " ")


def event_out(state: GameState, event: GameEvent, data: LoadedData) -> EventOut:
    story = state.storyline(event.storyline_id) if event.storyline_id is not None else None
    template = data.game_data.event_template(event.template_id)
    step = template.storyline.step if template.storyline else 1
    follow = (
        "Whatever you choose, a follow-up comes next month."
        if event.severity == "critical"
        and template.follow_up
        and any(e.type == "follow_up" for c in event.choices for e in c.effects)
        else None
    )
    return EventOut(
        event_id=event.id,
        turn=event.turn,
        date_label=format_turn(event.turn),
        category=event.category,
        category_label=CATEGORY_LABELS.get(event.category, event.category.title()),
        severity=event.severity,
        status=event.status,
        title=event.title,
        body=event.body,
        choices=[
            EventChoiceOut(
                key=c.key,
                label=c.label,
                effects=[effect_words(state, event, e, data) for e in c.effects],
            )
            for c in event.choices
        ],
        chosen=event.chosen,
        written_by=SOURCE_LABELS.get(event.source, event.source),
        storyline=EventStorylineOut(storyline_id=story.id, title=story.title, step=step)
        if story
        else None,
        follow_up_note=follow,
        person_ids=list(event.person_ids),
    )


def storyline_out(story: Storyline) -> StorylineOut:
    return StorylineOut(
        storyline_id=story.id,
        title=story.title,
        step=story.step,
        summary=story.summary,
        status=story.status,
        started_label=format_turn(story.started_turn),
    )


def relationships_out(state: GameState, person_id: int, data: LoadedData) -> list[RelationshipOut]:
    """The person's unit-mates and manager links with a label (16.7, 16.9)."""
    cid = state.player.id
    view = org_view(state, cid)
    rels = state.relationship_map()
    out = []
    for rel in state.relationships_of(person_id):
        other = rel.other(person_id)
        if other not in view.unit_of:
            continue
        if view.manager_of.get(person_id) == other:
            link = "manager"
        elif view.manager_of.get(other) == person_id:
            link = "report"
        else:
            link = "unit-mate"
        current = rels[pair_key(person_id, other)]
        out.append(
            RelationshipOut(
                person_id=other,
                name=_name(state, other),
                link=link,
                label=relationship_label(current.value, data.balance.relationships),
            )
        )
    return sorted(out, key=lambda r: (r.link, r.name))


def team_mood(state: GameState, unit_id: int | None, data: LoadedData) -> TeamMoodOut:
    """The org unit panel's "Team mood": strained or hostile pairs in the unit."""
    cid = state.player.id
    view = org_view(state, cid)
    members = set(view.members.get(unit_id, ()))
    pairs = []
    for rel in state.relationships:
        if rel.a in members and rel.b in members:
            label = relationship_label(rel.value, data.balance.relationships)
            if label in ("strained", "hostile"):
                pairs.append(
                    TeamMoodPairOut(
                        a_name=_name(state, rel.a), b_name=_name(state, rel.b), label=label
                    )
                )
    if not pairs:
        line = "No strained relationships in this team."
    else:
        line = "; ".join(f"{p.a_name} and {p.b_name}: {p.label}" for p in pairs)
    return TeamMoodOut(unit_id=unit_id, line=line, pairs=pairs)
