"""Events, storylines, relationships and AI writing settings (M6, docs/formulas.md 16)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from tst.api import event_views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _act, _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.events import (
    ChooseEventIn,
    ChooseEventOut,
    EventOut,
    EventsOut,
    LLMSettingsIn,
    LLMSettingsOut,
    RelationshipOut,
    StorylineOut,
    TeamMoodOut,
)
from tst.db import repository
from tst.db.mappers import storyline_from_row
from tst.db.models import StorylineRow
from tst.db.state_io import has_table
from tst.llm.settings import (
    LLMSettings,
    load_settings,
    month_spend,
    reset_date,
    save_settings,
)
from tst.sim.actions import ChooseEvent
from tst.sim.errors import NotFoundError

router = APIRouter(prefix="/api/saves/{save_id}", tags=["events"])
settings_router = APIRouter(prefix="/api/settings", tags=["settings"])

RECENT_MONTHS = 3  # tunable-exempt: answered events listed under the open ones
RECENT_LIMIT = 20  # tunable-exempt: list length

CAN_SEE = [
    "Your company's cash, runway, revenue, headcount and stage",
    "The names, roles, levels, tenure and morale of the people an event is about",
    "Skills as words from the ranges you can see, tags you have noticed, interests you know",
    "Your products' names, rivals' names, and the last ten events and storylines",
]
CANNOT_SEE = [
    "True attributes, potential, hidden traits or tags you have not noticed",
    "Rivals' cash, plans or people's true values",
    "Any number the game does not show you; and it never changes the game itself",
]


class UnknownEventError(NotFoundError):
    code = "unknown_event"


@router.get("/events", response_model=EventsOut, responses=ERRORS, operation_id="listEvents")
def list_events(save_id: str, settings: SettingsDep, data: DataDep) -> EventsOut:
    """This month's events to answer (minor and major resolve to their first choice at
    Continue; an open critical event blocks it) and recently answered ones (16.3)."""
    state = _state(_path(settings, save_id))
    cid = state.player.id
    shown = [e for e in state.open_events(cid) if e.status == "open"]
    recent = sorted(
        (
            e
            for e in state.events
            if e.company_id == cid
            and e.status in ("answered", "auto")
            and e.turn > state.turn - RECENT_MONTHS
        ),
        key=lambda e: -e.id,
    )[:RECENT_LIMIT]
    blocking = next((e.id for e in shown if e.severity == "critical"), None)
    llm = load_settings(settings.resolved_save_dir())
    return EventsOut(
        to_answer=len(shown),
        blocking_event_id=blocking,
        open=[event_views.event_out(state, e, data) for e in shown],
        recent=[event_views.event_out(state, e, data) for e in recent],
        ai_spend_cents=round(month_spend(settings.resolved_save_dir()).cents, 4),
        ai_budget_cents=llm.monthly_budget_cents,
    )


@router.get(
    "/events/{event_id}", response_model=EventOut, responses=ERRORS, operation_id="getEvent"
)
def get_event(save_id: str, event_id: int, settings: SettingsDep, data: DataDep) -> EventOut:
    state = _state(_path(settings, save_id))
    event = state.event(event_id)
    if event is None or event.company_id != state.player.id or event.status == "pending":
        raise UnknownEventError(f"no event {event_id}")
    return event_views.event_out(state, event, data)


@router.post(
    "/events/{event_id}/choose",
    response_model=ChooseEventOut,
    responses=ERRORS,
    operation_id="chooseEvent",
)
def choose_event(
    save_id: str, event_id: int, body: ChooseEventIn, settings: SettingsDep, data: DataDep
) -> ChooseEventOut:
    """Answer an event: its effects apply at once (energy 0, 16.3)."""
    path = _path(settings, save_id)
    result, out = _act(path, data, ChooseEvent(_founder_id(_state(path)), event_id, body.choice))
    event = result.new_state.event(event_id)
    assert event is not None
    return ChooseEventOut(
        event=event_views.event_out(result.new_state, event, data),
        energy=out.energy.energy,
        unread_inbox=out.unread_inbox,
    )


@router.get(
    "/storylines",
    response_model=list[StorylineOut],
    responses=ERRORS,
    operation_id="listStorylines",
)
def list_storylines(save_id: str, settings: SettingsDep) -> list[StorylineOut]:
    """Active storylines first, then ended ones, newest first (16.6)."""
    with repository.open_session(_path(settings, save_id)) as session:
        if not has_table(session, StorylineRow):
            return []
        rows = session.scalars(select(StorylineRow).order_by(StorylineRow.id.desc())).all()
        stories = [storyline_from_row(r) for r in rows]
    stories.sort(key=lambda s: (s.status != "active", -s.id))
    return [event_views.storyline_out(s) for s in stories]


@router.get(
    "/people/{person_id}/relationships",
    response_model=list[RelationshipOut],
    responses=ERRORS,
    operation_id="getRelationships",
)
def get_relationships(
    save_id: str, person_id: int, settings: SettingsDep, data: DataDep
) -> list[RelationshipOut]:
    """Unit-mates and manager links with a label (16.7); never a number."""
    state = _state(_path(settings, save_id))
    return event_views.relationships_out(state, person_id, data)


@router.get(
    "/org/team-mood", response_model=TeamMoodOut, responses=ERRORS, operation_id="getTeamMood"
)
def get_team_mood(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    unit_id: Annotated[int | None, Query()] = None,
) -> TeamMoodOut:
    """The org unit panel's "Team mood" line: strained or hostile pairs (16.9)."""
    return event_views.team_mood(_state(_path(settings, save_id)), unit_id, data)


def _settings_out(settings: SettingsDep) -> LLMSettingsOut:
    save_dir = settings.resolved_save_dir()
    llm = load_settings(save_dir)
    spend = month_spend(save_dir)
    key = bool(settings.anthropic_api_key)
    claude = llm.adapter == "claude" and key and spend.cents < llm.monthly_budget_cents
    return LLMSettingsOut(
        adapter="claude" if llm.adapter == "claude" else "templates",
        in_use="Claude" if claude else "Offline templates",
        key_found=key,
        spend_cents=round(spend.cents, 4),
        budget_cents=llm.monthly_budget_cents,
        calls=spend.calls,
        reset_date=reset_date(),
        model_events=llm.model_events,
        model_story=llm.model_story,
        events_by_claude=spend.events_claude,
        rejected_drafts=spend.events_rejected,
        average_cost_cents=round(spend.event_cents / spend.events_claude, 4)
        if spend.events_claude
        else None,
        can_see=CAN_SEE,
        cannot_see=CANNOT_SEE,
    )


@settings_router.get("/llm", response_model=LLMSettingsOut, operation_id="getLlmSettings")
def get_llm_settings(settings: SettingsDep) -> LLMSettingsOut:
    """AI writing: the adapter, this calendar month's spend against the budget, models."""
    return _settings_out(settings)


@settings_router.put("/llm", response_model=LLMSettingsOut, operation_id="updateLlmSettings")
def update_llm_settings(body: LLMSettingsIn, settings: SettingsDep) -> LLMSettingsOut:
    """Change the adapter, budget (0 is offline play) or model ids; prices stay as they are."""
    save_dir = settings.resolved_save_dir()
    current = load_settings(save_dir)
    updated = LLMSettings(
        adapter="claude" if body.adapter == "claude" else "templates",
        monthly_budget_cents=body.monthly_budget_cents,
        model_events=body.model_events,
        model_story=body.model_story,
        price_per_mtok_cents=current.price_per_mtok_cents,
    )
    save_settings(save_dir, updated)
    return _settings_out(settings)
