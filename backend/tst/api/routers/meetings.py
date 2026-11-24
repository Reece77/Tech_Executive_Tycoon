"""Meeting routes (docs/formulas.md 59; M48, ADR-0023): this month's board meeting, earnings
call or investor day, an answer an item, and skip. Meetings run between turns; their outcome
reaches the game through `MeetingOutcome`, logged like any action, and a skip changes
nothing."""

from __future__ import annotations

from fastapi import APIRouter

from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.negotiations import _mode
from tst.api.routers.saves import ERRORS
from tst.api.schemas.meetings import (
    MeetingAnswerIn,
    MeetingAnswerOut,
    MeetingAvailabilityOut,
    MeetingCommitmentOut,
    MeetingEffectOut,
    MeetingItemOut,
    MeetingListOut,
    MeetingMoveChoiceOut,
    MeetingMoveOut,
    MeetingOpenIn,
    MeetingOut,
    MeetingSpeakerOut,
    MeetingSummaryOut,
    MeetingVoteOut,
)
from tst.conversations import meetings
from tst.conversations.common import mode_info
from tst.conversations.meeting_view import PublicMove
from tst.db import repository
from tst.sim.calendar import format_turn
from tst.sim.press.moments import credibility
from tst.sim.press.promises import MEETING_KINDS, meeting_words

router = APIRouter(prefix="/api/saves/{save_id}/meetings", tags=["meetings"])


def _move(m: PublicMove) -> MeetingMoveOut:
    return MeetingMoveOut(kind=m.kind, fact=m.fact, words=m.words)


def meeting_out(t: meetings.MeetingTalks) -> MeetingOut:
    v = t.view
    said = {n: (msg, src, reply, by) for n, msg, src, reply, by in t.messages}
    blank = ("", "", "", "")
    return MeetingOut(
        meeting_id=t.id,
        kind=v.kind,
        subject=v.subject,
        status=t.status,
        opened_turn=t.opened_turn,
        date_label=format_turn(t.opened_turn),
        error=t.error,
        speakers=[
            MeetingSpeakerOut(
                key=s.key,
                kind=s.kind,
                name=s.name,
                role=s.role,
                organisation=s.organisation,
                focus=s.focus,
                confidence=s.confidence,
                rating=s.rating,
                target_cents=s.target_cents,
            )
            for s in v.speakers
        ],
        items=[
            MeetingItemOut(
                n=i.n,
                speaker=i.speaker,
                topic=i.topic,
                title=i.title,
                question=i.question,
                facts=list(i.facts),
                problem=i.problem,
                figure=i.figure,
                guidance=i.guidance,
            )
            for i in v.items
        ],
        answers=[
            MeetingAnswerOut(
                n=a.n,
                message=said.get(a.n, blank)[0],
                message_source=said.get(a.n, blank)[1],
                reply=said.get(a.n, blank)[2],
                reply_source=said.get(a.n, blank)[3],
                claimed=[_move(m) for m in a.claimed],
                moves=[_move(m) for m in a.moves],
                reaction=a.reaction,
                reaction_words=a.reaction_words,
                commitment=a.commitment,
            )
            for a in v.answers
        ],
        next_item=v.next_item if t.status == "open" else None,
        opening_line=t.opening_line,
        move_choices=[MeetingMoveChoiceOut(kind=k, label=label) for k, label in v.moves],
        credibility=v.credibility,
        persona=list(v.persona),
        plan_subject=v.plan_subject,
        plan_facts=list(v.plan_facts),
        effects=[
            MeetingEffectOut(who=e.who, what=e.what, change=e.change, words=e.words)
            for e in v.effects
        ],
        votes=[MeetingVoteOut(name=n, backs_plan=b) for n, b in v.votes],
        commitments=list(v.commitments),
        suggestions=list(t.suggestions),
        mode=_mode(t.mode),
    )


@router.get("", response_model=MeetingListOut, responses=ERRORS, operation_id="listMeetings")
def list_meetings(save_id: str, settings: SettingsDep, data: DataDep) -> MeetingListOut:
    """This month's meetings and why any cannot be held, past meetings newest first, the
    commitments made in meetings and their status, and credibility."""
    path = _path(settings, save_id)
    talks = meetings.listing(path, data)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    cid = state.player.id
    return MeetingListOut(
        mode=_mode(mode_info(path.parent, data)),
        available=[
            MeetingAvailabilityOut(
                kind=a.kind, available=a.available, reason=a.reason, meeting_id=a.meeting_id
            )
            for a in meetings.availability(path, data)
        ],
        items=[
            MeetingSummaryOut(
                meeting_id=t.id,
                kind=t.view.kind,
                subject=t.view.subject,
                status=t.status,
                opened_turn=t.opened_turn,
                date_label=format_turn(t.opened_turn),
                effects=[e.words for e in t.view.effects],
            )
            for t in talks
        ],
        commitments=[
            MeetingCommitmentOut(
                promise_id=p.id,
                kind=p.kind,
                words=meeting_words(p),
                made_label=format_turn(p.made_turn),
                deadline_label=format_turn(p.deadline_turn),
                status=p.status,
            )
            for p in sorted(state.promises, key=lambda p: -p.id)
            if p.company_id == cid and p.kind in MEETING_KINDS
        ],
        credibility=round(credibility(state, cid, data.balance), 1),
        industries=[
            MeetingMoveChoiceOut(kind=i.key, label=i.label)
            for i in data.balance.conglomerate.industries
        ],
    )


@router.post("", response_model=MeetingOut, responses=ERRORS, operation_id="openMeeting")
def open_meeting(
    save_id: str, body: MeetingOpenIn, settings: SettingsDep, data: DataDep
) -> MeetingOut:
    """Hold this month's meeting of a kind (or resume it while it is open)."""
    path = _path(settings, save_id)
    return meeting_out(meetings.open_meeting(path, data, body.kind, dict(body.params)))


@router.get("/{meeting_id}", response_model=MeetingOut, responses=ERRORS, operation_id="getMeeting")
def get_meeting(save_id: str, meeting_id: int, settings: SettingsDep, data: DataDep) -> MeetingOut:
    """The meeting and, once it is over, its visible effects."""
    return meeting_out(meetings.get(_path(settings, save_id), data, meeting_id))


@router.post(
    "/{meeting_id}/answers",
    response_model=MeetingOut,
    responses=ERRORS,
    operation_id="answerMeetingItem",
)
def answer_item(
    save_id: str, meeting_id: int, body: MeetingAnswerIn, settings: SettingsDep, data: DataDep
) -> MeetingOut:
    """Answer the current item: free text (scored by the LLM into moves) or template moves."""
    t = meetings.answer(
        _path(settings, save_id),
        data,
        meeting_id,
        message=body.message,
        moves=None if body.moves is None else [m.model_dump(exclude_none=True) for m in body.moves],
        source=body.source,
    )
    return meeting_out(t)


@router.post(
    "/{meeting_id}/skip", response_model=MeetingOut, responses=ERRORS, operation_id="skipMeeting"
)
def skip_meeting(save_id: str, meeting_id: int, settings: SettingsDep, data: DataDep) -> MeetingOut:
    """Skip: today's outcome; nothing the meeting would have moved moves (59)."""
    return meeting_out(meetings.skip(_path(settings, save_id), data, meeting_id))
