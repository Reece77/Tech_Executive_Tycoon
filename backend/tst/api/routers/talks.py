"""Talk routes (docs/formulas.md 61; M49, ADR-0023): this month's interviews and press
conferences, one-to-ones with the company's people, an answer a question, and skip. Talks run
between turns; their outcome reaches the game through `TalkOutcome`, logged like any action,
and a skip changes nothing."""

from __future__ import annotations

from fastapi import APIRouter

from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.negotiations import _mode
from tst.api.routers.saves import ERRORS
from tst.api.schemas.talks import (
    TalkAnswerIn,
    TalkAnswerOut,
    TalkAvailableOut,
    TalkCounterpartOut,
    TalkEffectOut,
    TalkListOut,
    TalkMoveChoiceOut,
    TalkMoveOut,
    TalkOpenIn,
    TalkOut,
    TalkPersonOut,
    TalkPromiseOut,
    TalkQuestionOut,
    TalkSummaryOut,
)
from tst.conversations import talks
from tst.conversations.common import mode_info
from tst.conversations.talk_view import PublicMove
from tst.db import repository
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.press.promises import TALK_KINDS, talk_words
from tst.sim.state import GameState

router = APIRouter(prefix="/api/saves/{save_id}/talks", tags=["talks"])


def _move(m: PublicMove) -> TalkMoveOut:
    return TalkMoveOut(kind=m.kind, words=m.words)


def talk_out(t: talks.TalkTalks) -> TalkOut:
    v = t.view
    said = {n: (msg, src, reply, by) for n, msg, src, reply, by in t.messages}
    blank = ("", "", "", "")
    c = v.counterpart
    return TalkOut(
        talk_id=t.id,
        kind=v.kind,
        subject=v.subject,
        source=v.source,
        status=t.status,
        opened_turn=t.opened_turn,
        date_label=format_turn(t.opened_turn),
        error=t.error,
        counterpart=TalkCounterpartOut(
            name=c.name,
            role=c.role,
            organisation=c.organisation,
            person_id=c.person_id,
            beat=c.beat,
            stance=c.stance,
            morale=c.morale,
        ),
        questions=[
            TalkQuestionOut(
                n=q.n,
                topic=q.topic,
                title=q.title,
                question=q.question,
                facts=list(q.facts),
                offer=q.offer,
                rival=q.rival,
            )
            for q in v.questions
        ],
        answers=[
            TalkAnswerOut(
                n=a.n,
                message=said.get(a.n, blank)[0],
                message_source=said.get(a.n, blank)[1],
                reply=said.get(a.n, blank)[2],
                reply_source=said.get(a.n, blank)[3],
                claimed=[_move(m) for m in a.claimed],
                moves=[_move(m) for m in a.moves],
                reaction=a.reaction,
                reaction_words=a.reaction_words,
            )
            for a in v.answers
        ],
        next_question=v.next_question if t.status == "open" else None,
        opening_line=t.opening_line,
        move_choices=[TalkMoveChoiceOut(kind=k, label=label) for k, label in v.moves],
        offer=v.offer,
        approached_by=v.approached_by,
        delegated=v.delegated_to is not None,
        effects=[TalkEffectOut(what=e.what, change=e.change, words=e.words) for e in v.effects],
        suggestions=list(t.suggestions),
        mode=_mode(t.mode),
    )


def _people(state: GameState, data: LoadedData, held: dict[int, str]) -> list[TalkPersonOut]:
    from tst.sim.org.rules import org_view

    cid = state.player.id
    tb = data.balance.talks
    founder = state.founder_of(cid)
    seats = {s.person_id for s in state.exec_seats if s.company_id == cid}
    labels = {r.key: r.label for r in data.game_data.roles}
    view = org_view(state, cid)
    approached = {
        a.person_id: state.company(a.rival_id).name
        for a in state.approaches
        if a.status == "pending" and a.made_turn < state.turn
    }
    out = []
    for e in sorted(state.staff(cid), key=lambda e: e.person_id):
        if e.status != "active" or (founder is not None and e.person_id == founder.id):
            continue
        ps = state.person_state(e.person_id)
        morale = round(ps.morale) if ps.morale is not None else None
        flags = []
        if morale is not None and morale < tb.one_to_one.unhappy_below:
            flags.append("unhappy")
        if e.person_id in approached:
            flags.append("approached")
        if e.person_id in seats:
            flags.append("seat")
        above: list[int] = []
        m = view.manager_of.get(e.person_id)
        while m is not None and m not in above:
            above.append(m)
            m = view.manager_of.get(m)
        person = state.person(e.person_id)
        out.append(
            TalkPersonOut(
                person_id=e.person_id,
                name=f"{person.first_name} {person.last_name}",
                role_label=f"{e.level} {labels.get(e.role, e.role)}",
                morale=morale,
                flags=flags,
                approached_by=approached.get(e.person_id, ""),
                held=held.get(e.person_id, ""),
                delegates=[p for p in above if p in seats],
            )
        )
    return out


@router.get("", response_model=TalkListOut, responses=ERRORS, operation_id="listTalks")
def list_talks(
    save_id: str, settings: SettingsDep, data: DataDep, person_id: int | None = None
) -> TalkListOut:
    """This month's interviews and press conferences, past talks newest first (or one
    person's), the company's people with their flags, and promised promotions."""
    path = _path(settings, save_id)
    past = talks.listing(path, data, person_id)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    cid = state.player.id
    staff = [e.person_id for e in state.staff(cid)]
    held = talks.held_this_month(path, staff)
    founder = state.founder_of(cid)
    energy = state.person_state(founder.id).energy if founder is not None else None
    people = _people(state, data, held)
    if person_id is not None:
        people = [p for p in people if p.person_id == person_id]
    return TalkListOut(
        mode=_mode(mode_info(path.parent, data)),
        available=[
            TalkAvailableOut(
                kind=a.kind,
                source=a.source,
                key=a.key,
                subject=a.subject,
                talk_id=a.talk_id,
                status=a.status,
            )
            for a in talks.available(path, data)
        ],
        items=[
            TalkSummaryOut(
                talk_id=t.id,
                kind=t.view.kind,
                subject=t.view.subject,
                status=t.status,
                opened_turn=t.opened_turn,
                date_label=format_turn(t.opened_turn),
                person_id=t.view.counterpart.person_id,
                effects=[e.words for e in t.view.effects],
            )
            for t in past
        ],
        people=people,
        promises=[
            TalkPromiseOut(
                promise_id=p.id,
                person_id=p.level or 0,
                words=talk_words(state, p),
                made_label=format_turn(p.made_turn),
                deadline_label=format_turn(p.deadline_turn),
                status=p.status,
            )
            for p in sorted(state.promises, key=lambda p: -p.id)
            if p.company_id == cid
            and p.kind in TALK_KINDS
            and (person_id is None or p.level == person_id)
        ],
        energy=energy,
        one_to_one_energy=data.balance.talks.energy["one_to_one"],
    )


@router.post("", response_model=TalkOut, responses=ERRORS, operation_id="openTalk")
def open_talk(save_id: str, body: TalkOpenIn, settings: SettingsDep, data: DataDep) -> TalkOut:
    """Take an interview or press conference, or hold a one-to-one (or resume an open one)."""
    path = _path(settings, save_id)
    return talk_out(talks.open_talk(path, data, body.kind, dict(body.params)))


@router.get("/{talk_id}", response_model=TalkOut, responses=ERRORS, operation_id="getTalk")
def get_talk(save_id: str, talk_id: int, settings: SettingsDep, data: DataDep) -> TalkOut:
    """The talk and, once it is over, its visible effects."""
    return talk_out(talks.get(_path(settings, save_id), data, talk_id))


@router.post(
    "/{talk_id}/answers", response_model=TalkOut, responses=ERRORS, operation_id="answerTalk"
)
def answer_talk(
    save_id: str, talk_id: int, body: TalkAnswerIn, settings: SettingsDep, data: DataDep
) -> TalkOut:
    """Answer the current question: free text (scored by the LLM into moves) or template
    moves."""
    t = talks.answer(
        _path(settings, save_id),
        data,
        talk_id,
        message=body.message,
        moves=None if body.moves is None else [m.model_dump() for m in body.moves],
        source=body.source,
    )
    return talk_out(t)


@router.post("/{talk_id}/skip", response_model=TalkOut, responses=ERRORS, operation_id="skipTalk")
def skip_talk(save_id: str, talk_id: int, settings: SettingsDep, data: DataDep) -> TalkOut:
    """Skip: today's outcome; nothing the talk would have moved moves (61). An interview's
    press event can still be answered as before."""
    return talk_out(talks.skip(_path(settings, save_id), data, talk_id))
