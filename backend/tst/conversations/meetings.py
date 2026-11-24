"""The meetings service (ADR-0023; docs/formulas.md 59): board meetings, earnings calls and
investor days between turns, on M47's conversation machinery (tst.conversations.common).

A meeting opens on the month's facts (tst.sim.meetings.agenda), plays one answer an item
through the pure engine, and ends through an ordinary action (`MeetingOutcome`) logged in
decision_log like any action: so a replay of the game never reads a meeting and never calls the
LLM. Skipping (before or during the meeting) runs no action at all: today's outcome. Each
answer is stored with the player's text, the moves it was scored into and the reply, so a
reload resumes exactly and `replayed` rebuilds the meeting from the stored moves alone.

The LLM only (a) scores the player's answer into the kind's closed moves, (b) suggests answers
and (c) words the speaker's decided reaction and next question, each validated, within the
conversations' monthly cap. Over it, offline, set to templates or in tests, meetings run in
template mode: the player picks moves from labelled buttons, and the engine is identical. The
player's text is untrusted: quoted as data, never an instruction, never executed."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.conversations import classifier, meeting_prompts, meeting_store, meeting_templates
from tst.conversations.common import (
    ModeInfo,
    _ask,
    _log_calls,
    _now,
    _run,
    _spend,
    _writer,
    clean_message,
    mode_info,
)
from tst.conversations.meeting_view import PublicMeeting, public, reaction_of
from tst.db import repository
from tst.db.models import ConversationRoundRow, ConversationRow
from tst.events.service import Writer
from tst.llm.base import LLMAdapter
from tst.loader import LoadedData
from tst.sim.errors import MeetingRuleError, SimError, UnknownMeetingError
from tst.sim.ledger import CASH
from tst.sim.meetings import agenda, engine
from tst.sim.meetings.actions import outcome_action
from tst.sim.meetings.config import MEETING_KINDS, MOVES, PLAN_KINDS, MeetingKind
from tst.sim.meetings.engine import raw_strength_public
from tst.sim.meetings.models import Meeting, Move, Plan
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

PURPOSE = "meeting"  # llm_call_log.purpose
OPEN = "open"


@dataclass(frozen=True, slots=True)
class MeetingTalks:
    """A meeting as the API shows it: its row's public fields and the public view."""

    id: int
    status: str
    opened_turn: int
    error: str | None
    suggestions: tuple[str, ...]
    view: PublicMeeting
    # (item, said, source, reply, by): the speakers' lines; item -1 is the opening question
    messages: tuple[tuple[int, str, str, str, str], ...]
    opening_line: str
    mode: ModeInfo


@dataclass(frozen=True, slots=True)
class Availability:
    kind: str
    available: bool
    reason: str  # why not ("" when available)
    meeting_id: int | None  # this month's meeting, if one was opened


def as_kind(kind: str) -> MeetingKind:
    for k in MEETING_KINDS:
        if k == kind:
            return k
    raise MeetingRuleError(f"unknown meeting kind {kind!r}")


def meeting_key(kind: str, turn: int) -> str:
    return f"meeting:{kind}:{turn}"


def _history(session: Session, conv_id: int) -> list[ConversationRoundRow]:
    return list(
        session.scalars(
            select(ConversationRoundRow)
            .where(ConversationRoundRow.conversation_id == conv_id)
            .order_by(ConversationRoundRow.n)
        )
    )


def _said(rows: Sequence[ConversationRoundRow]) -> list[tuple[str, str]]:
    return [(r.message, r.reply) for r in rows if r.n >= 0]


def _shown_status(row: ConversationRow, turn: int) -> str:
    return "lapsed" if row.status == OPEN and row.opened_turn < turn else row.status


def _lapse(session: Session, turn: int) -> None:
    """Meetings run within the month they are held: one still open at Continue lapses (its
    outcome is today's, as a skip)."""
    for row in session.scalars(
        select(ConversationRow).where(
            ConversationRow.status == OPEN,
            ConversationRow.opened_turn < turn,
            ConversationRow.kind.in_(MEETING_KINDS),
        )
    ):
        row.status = "lapsed"
        row.closed_turn = turn


def _talks(
    row: ConversationRow, rounds: Sequence[ConversationRoundRow], data: LoadedData, mode: ModeInfo
) -> MeetingTalks:
    meeting = meeting_store.load(row.state)
    view = public(meeting, data.balance.meetings)
    opening = next((r.reply for r in rounds if r.n < 0), "")
    return MeetingTalks(
        id=row.id,
        status=row.status,
        opened_turn=row.opened_turn,
        error=row.error,
        suggestions=tuple(row.suggestions),
        view=view,
        messages=tuple(
            (r.n, r.message, r.message_source, r.reply, r.reply_source) for r in rounds if r.n >= 0
        ),
        opening_line=opening or meeting_templates.question_line(view, 0),
        mode=mode,
    )


def _row(session: Session, conv_id: int) -> ConversationRow:
    row = session.get(ConversationRow, conv_id)
    if row is None or row.kind not in MEETING_KINDS:
        raise UnknownMeetingError(f"no meeting {conv_id}")
    return row


# --- Reading ------------------------------------------------------------------------------------


def get(path: Path, data: LoadedData, conv_id: int) -> MeetingTalks:
    """A read: never writes (a lapse is recorded by the next write)."""
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        row = _row(session, conv_id)
        talks = _talks(row, _history(session, conv_id), data, mode_info(path.parent, data))
    return replace(talks, status=_shown_status(row, state.turn))


def listing(path: Path, data: LoadedData) -> list[MeetingTalks]:
    mode = mode_info(path.parent, data)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        rows = list(
            session.scalars(
                select(ConversationRow)
                .where(ConversationRow.kind.in_(MEETING_KINDS))
                .order_by(ConversationRow.id.desc())
            )
        )
        return [
            replace(
                _talks(r, _history(session, r.id), data, mode),
                status=_shown_status(r, state.turn),
            )
            for r in rows
        ]


def _last_day(session: Session) -> int | None:
    return session.scalar(
        select(ConversationRow.opened_turn)
        .where(ConversationRow.kind == "investor_day", ConversationRow.status == "done")
        .order_by(ConversationRow.opened_turn.desc())
    )


def _why_not(session: Session, state: GameState, kind: MeetingKind, data: LoadedData) -> str | None:
    why = agenda.problem(state, kind, data.balance)
    if why is not None:
        return why
    if kind == "investor_day":
        last = _last_day(session)
        every = data.balance.meetings.investor_day.every_months
        if last is not None and state.turn - last < every:
            return (
                f"the next investor day can be held {every - (state.turn - last)} months from now"
            )
    held = session.scalars(
        select(ConversationRow).where(
            ConversationRow.deal_key == meeting_key(kind, state.turn),
            ConversationRow.status != OPEN,
        )
    ).first()
    if held is not None:
        return f"this month's meeting is over ({held.status})"
    return None


def availability(path: Path, data: LoadedData) -> list[Availability]:
    """Which meetings can be held this month, and why not."""
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        out = []
        for kind in MEETING_KINDS:
            row = session.scalars(
                select(ConversationRow).where(
                    ConversationRow.deal_key == meeting_key(kind, state.turn)
                )
            ).first()
            why = _why_not(session, state, kind, data)
            out.append(Availability(kind, why is None, why or "", row.id if row else None))
        return out


def replayed(path: Path, data: LoadedData, conv_id: int) -> Meeting:
    """The meeting rebuilt from its opening and its stored moves: no LLM (ADR-0023)."""
    with repository.open_session(path) as session:
        row = _row(session, conv_id)
        rounds = [r for r in _history(session, conv_id) if r.n >= 0]
        stored = meeting_store.load(row.state)
    start = replace(stored, answers=(), status="open", effects=None)
    played = tuple(tuple(meeting_store.move(m) for m in r.moves) for r in rounds)
    return engine.replay(start, played, data.balance.meetings)


# --- Opening --------------------------------------------------------------------------------------


def _plan(session: Session, state: GameState, params: dict[str, Any], data: LoadedData) -> Plan:
    """An investor day's plan and its displayed economics: the conglomerate view's return on
    capital for last year (the group's, and the industry's for a new industry)."""
    from tst.db.conglomerate import current_year, read_books

    kind = params.get("plan_kind")
    if kind not in PLAN_KINDS:
        raise MeetingRuleError(f"a plan is one of {', '.join(PLAN_KINDS)}")
    books, _ = read_books(session, state, data)
    year = current_year(state) - 1
    group = books.group(year)
    roc = group.return_on_capital
    facts = [
        f"the group's return on capital in {year} was {roc:.0%}"
        if roc is not None
        else f"the group had no capital employed to measure in {year}"
    ]
    if group.operating_margin is not None:
        facts.append(f"the group's operating margin in {year} was {group.operating_margin:.0%}")
    labels = {i.key: i.label for i in data.balance.conglomerate.industries}
    if kind == "new_industry":
        industry = str(params.get("industry", ""))
        if industry not in labels:
            raise MeetingRuleError("name the industry the plan enters")
        subject = f"entering {labels[industry].lower()}"
        cell = books.by_industry(year).get(industry)
        if cell is not None and cell.return_on_capital is not None:
            roc = cell.return_on_capital
            facts.append(f"{labels[industry]} earned {roc:.0%} on its capital in {year}")
        else:
            facts.append(f"the group has no {labels[industry].lower()} business yet")
    elif kind == "capital_plan":
        subject = "a capital plan"
    else:
        subject = "a restructuring"
    return agenda.plan_for(kind, subject, tuple(facts), roc, data.balance.meetings)


def _opening(
    writer: Writer | None, view: PublicMeeting, data: LoadedData
) -> tuple[str, str, list[str], str]:
    """(the first question's line, its source, suggestions, their source)."""
    mb = data.balance.meetings
    line = meeting_templates.question_line(view, 0)
    source = "template"
    if writer is not None:
        system, user = meeting_prompts.speak_prompt(
            view, view.items[0].speaker, None, 0, [], "", mb.max_reply_words, mb.history_items
        )
        got = _ask(writer, "reply", system, user, line, PURPOSE)
        ok = classifier.reply_ok(got, _allowed(view, 0), mb.max_reply_words)
        if ok:
            line, source = ok, writer.adapter.name
    sug, sug_source = _suggest(writer, view, 0, [], data)
    return line, source, sug, sug_source


def _allowed(view: PublicMeeting, item: int | None) -> list[str]:
    out = [*view.plan_facts, f"{view.credibility:.0f}"]
    for it in view.items:
        out += [*it.facts, it.figure, it.question]
    for s in view.speakers:
        if s.confidence is not None:
            out.append(f"{s.confidence:.0f}")
    return out


def _suggest(
    writer: Writer | None,
    view: PublicMeeting,
    item: int,
    said: list[tuple[str, str]],
    data: LoadedData,
) -> tuple[list[str], str]:
    mb = data.balance.meetings
    fallback = meeting_templates.suggestions(view, item, mb.suggestions)
    if writer is None:
        return fallback, "template"
    system, user = meeting_prompts.suggest_prompt(
        view, item, said, mb.suggestions, mb.history_items
    )
    got = _ask(writer, "suggest", system, user, {"replies": fallback}, PURPOSE)
    out = classifier.suggestions_from(got, mb.suggestions, mb.max_message_chars)
    return (out, writer.adapter.name) if out else (fallback, "template")


def _cash(session: Session, state: GameState) -> int:
    balances = repository.current_balances(session, state.turn)
    return balances.get((state.player.id, CASH), 0)


def _energy_problem(state: GameState, kind: MeetingKind, data: LoadedData) -> str | None:
    founder = state.founder_of(state.player.id)
    if founder is None:
        return "the founder attends the company's meetings; there is none"
    energy = state.person_state(founder.id).energy
    need = data.balance.meetings.energy[kind]
    if energy is not None and energy < need:
        return f"the meeting needs {need} energy; {energy} left this month"
    return None


def open_meeting(
    path: Path,
    data: LoadedData,
    kind: str,
    params: dict[str, Any] | None = None,
    *,
    adapter: LLMAdapter | None = None,
) -> MeetingTalks:
    """Open this month's meeting of `kind`, or resume it if it is open."""
    mkind = as_kind(kind)
    save_dir = path.parent
    mode = mode_info(save_dir, data, adapter)
    writer = _writer(save_dir, data, adapter) if mode.mode == "llm" else None
    repository.migrate.ensure_current(path)
    with repository.write_session(path) as session:
        state = repository.load_current(session)
        _lapse(session, state.turn)
        key = meeting_key(kind, state.turn)
        found = session.scalars(
            select(ConversationRow).where(
                ConversationRow.deal_key == key, ConversationRow.status == OPEN
            )
        ).first()
        if found is not None:
            return _talks(found, _history(session, found.id), data, mode)
        why = _why_not(session, state, mkind, data) or _energy_problem(state, mkind, data)
        if why is not None:
            raise MeetingRuleError(why)
        plan = _plan(session, state, dict(params or {}), data) if mkind == "investor_day" else None
        rng = RngFactory(state.save_meta.master_seed)
        meeting = agenda.open_meeting(
            state, mkind, rng, data.balance, data.game_data, _cash(session, state), plan
        )
        view = public(meeting, data.balance.meetings)
        line, line_source, suggestions, sug_source = _opening(writer, view, data)
        row = ConversationRow(
            kind=kind,
            deal_key=key,
            counterpart_key=f"company:{state.player.id}",
            subject=meeting.subject,
            status=OPEN,
            opened_turn=state.turn,
            params=dict(params or {}),
            state=meeting_store.dump(meeting),
            suggestions=suggestions,
            suggestions_source=sug_source,
            relationship_change=0,
            created_at=_now(),
        )
        session.add(row)
        session.flush()
        session.add(
            ConversationRoundRow(
                conversation_id=row.id,
                n=-1,  # the opening question, before any answer
                message="",
                message_source="",
                moves=[],
                moves_source="",
                offer=[],
                reply=line,
                reply_source=line_source,
                created_at=_now(),
            )
        )
        if writer is not None:
            _log_calls(session, state.turn, writer)
        session.flush()
        talks = _talks(row, _history(session, row.id), data, mode)
    if writer is not None:
        _spend(save_dir, writer)
    return talks


# --- Answers and the outcome ---------------------------------------------------------------------


def _parse_moves(
    raw: Sequence[dict[str, Any]], kind: MeetingKind, max_moves: int
) -> tuple[Move, ...]:
    """Template mode's buttons: the kind's closed set, checked like the classifier's."""
    out = []
    for m in list(raw)[:max_moves]:
        k = m.get("kind")
        if k not in MOVES[kind]:
            raise MeetingRuleError(f"unknown move {k!r}")
        out.append(Move(str(k), classifier._index(m.get("fact"))))
    if not out:
        raise MeetingRuleError("pick at least one move")
    return tuple(out)


def moves_from(content: object, kind: MeetingKind, max_moves: int) -> tuple[tuple[Move, ...], bool]:
    """The classifier's JSON validated (ADR-0005): only the kind's moves, else `neutral`."""
    if not isinstance(content, dict) or set(content) != {"moves"}:
        return (Move("neutral"),), False
    raw = content["moves"]
    if not isinstance(raw, list) or not raw:
        return (Move("neutral"),), False
    out = []
    for item in raw[:max_moves]:
        if not isinstance(item, dict) or not set(item) <= {"move", "fact"}:
            return (Move("neutral"),), False
        k = item.get("move")
        if k not in MOVES[kind]:
            return (Move("neutral"),), False
        out.append(Move(str(k), classifier._index(item.get("fact"))))
    return tuple(out), True


def answer(
    path: Path,
    data: LoadedData,
    conv_id: int,
    *,
    message: str | None = None,
    moves: Sequence[dict[str, Any]] | None = None,
    source: str = "free",
    adapter: LLMAdapter | None = None,
) -> MeetingTalks:
    """One answer to the current item: the player's text (scored by the LLM) or picked moves
    (template mode). The engine decides; the speaker's line is worded after."""
    mb = data.balance.meetings
    save_dir = path.parent
    mode = mode_info(save_dir, data, adapter)
    writer = _writer(save_dir, data, adapter) if mode.mode == "llm" else None
    with repository.write_session(path) as session:
        state = repository.read_state(session)
        _lapse(session, state.turn)
        row = _row(session, conv_id)
        if row.status != OPEN:
            raise MeetingRuleError(f"this meeting is over ({row.status})")
        meeting = meeting_store.load(row.state)
        item = meeting.next_item
        if item is None:
            raise MeetingRuleError("the agenda is finished")
        kind = as_kind(row.kind)
        said = _said(_history(session, conv_id))
        view = public(meeting, mb)
        text = (
            clean_message(message, mb.max_message_chars, MeetingRuleError)
            if message is not None
            else ""
        )
        if moves:
            claimed, moves_source = _parse_moves(moves, kind, mb.max_moves), "template"
            source = "template" if not text else source
        elif text and writer is not None:
            system, user = meeting_prompts.classify_prompt(
                view, item.n, said, text, mb.history_items
            )
            got = _ask(writer, "classify", system, user, {"moves": [{"move": "neutral"}]}, PURPOSE)
            claimed, valid = moves_from(got, kind, mb.max_moves)
            moves_source = writer.adapter.name if valid else "invalid"
        elif text:
            raise MeetingRuleError("meetings are in template mode: pick moves from the buttons")
        else:
            raise MeetingRuleError("write an answer, or pick moves")
        after = engine.play_item(meeting, claimed, mb)
        view_after = public(after, mb)
        checked = after.answers[-1].moves
        reaction = reaction_of(raw_strength_public(after, item, checked, mb))
        nxt = after.next_item.n if after.next_item is not None else None
        speaker = after.items[nxt].speaker if nxt is not None else item.speaker
        fallback = meeting_templates.speak_line(view_after, reaction, nxt)
        reply, reply_source = fallback, "template"
        if writer is not None:
            system, user = meeting_prompts.speak_prompt(
                view_after, speaker, reaction, nxt, said, text, mb.max_reply_words, mb.history_items
            )
            got = _ask(writer, "reply", system, user, fallback, PURPOSE)
            ok = classifier.reply_ok(got, _allowed(view_after, nxt), mb.max_reply_words)
            if ok:
                reply, reply_source = ok, writer.adapter.name
        session.add(
            ConversationRoundRow(
                conversation_id=conv_id,
                n=item.n,
                message=text or ", ".join(m.words for m in view_after.answers[-1].claimed),
                message_source=source,
                moves=[_move_json(m) for m in claimed],
                moves_source=moves_source,
                offer=[],
                reply=reply,
                reply_source=reply_source,
                created_at=_now(),
            )
        )
        row.state = meeting_store.dump(after)
        if nxt is not None:
            sug, sug_source = _suggest(writer, view_after, nxt, [*said, (text, reply)], data)
            row.suggestions, row.suggestions_source = sug, sug_source
        else:
            row.suggestions = []
        if writer is not None:
            _log_calls(session, state.turn, writer)
        turn = state.turn
    if writer is not None:
        _spend(save_dir, writer)
    if after.status == "done":
        error = _conclude(path, data, after)
        with repository.write_session(path) as session:
            closing = _row(session, conv_id)
            closing.status = "failed" if error else "done"
            closing.error = error
            closing.closed_turn = turn
    return get(path, data, conv_id)


def _move_json(m: Move) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": m.kind}
    if m.fact is not None:
        out["fact"] = m.fact
    return out


def _conclude(path: Path, data: LoadedData, meeting: Meeting) -> str | None:
    """Run the outcome's action; the error's message if the rules refused it."""
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    founder = state.founder_of(state.player.id)
    if founder is None:
        return "the founder attends the company's meetings; there is none"
    try:
        _run(path, data, outcome_action(meeting, founder.id))
    except SimError as exc:
        return exc.message
    return None


def skip(path: Path, data: LoadedData, conv_id: int) -> MeetingTalks:
    """59: today's outcome. Nothing the meeting would have moved moves; no action runs."""
    with repository.write_session(path) as session:
        state = repository.read_state(session)
        _lapse(session, state.turn)
        row = _row(session, conv_id)
        if row.status != OPEN:
            raise MeetingRuleError(f"this meeting is over ({row.status})")
        row.state = meeting_store.dump(engine.skip(meeting_store.load(row.state)))
        row.status = "skipped"
        row.closed_turn = state.turn
        row.suggestions = []
    return get(path, data, conv_id)
