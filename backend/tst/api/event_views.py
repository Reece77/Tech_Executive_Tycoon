"""Events, storylines and relationships as the player sees them: effects as plain numbers
(formulas.md 23.2, M10b, replacing 16.9's words with a size), relationship labels; never caps
or trigger strengths."""

from __future__ import annotations

from tst.api.event_links import event_links
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
from tst.sim.events.describe import choice_texts, person_label
from tst.sim.events.models import GameEvent, Storyline
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
    "founder": "Founder",
    "executive": "Executives",  # M10c (24.3)
}
SOURCE_LABELS = {"claude": "Claude", "template": "template", "mock": "mock", "replay": "replay"}


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
        template_id=event.template_id,
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
                effects=choice_texts(state, event, c, data.balance),
                do_nothing=c.do_nothing,
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
        links=event_links(state, event, data),
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
                name=person_label(state, other),
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
                        a_name=person_label(state, rel.a),
                        b_name=person_label(state, rel.b),
                        label=label,
                    )
                )
    if not pairs:
        line = "No strained relationships in this team."
    else:
        line = "; ".join(f"{p.a_name} and {p.b_name}: {p.label}" for p in pairs)
    return TeamMoodOut(unit_id=unit_id, line=line, pairs=pairs)
