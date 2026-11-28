"""The talks service (ADR-0023; docs/formulas.md 61): press interviews, crisis conferences and
one-to-ones between turns, on M47's conversation machinery (tst.conversations.common).

A talk opens on the month's facts (tst.sim.talks.opening), plays one answer a question through
the pure engine, and ends through an ordinary action (`TalkOutcome`) logged in decision_log
like any action: so a replay of the game never reads a talk and never calls the LLM. Skipping
(before or during the talk) runs no action at all: today's outcome. An interview skipped leaves
its press event to be answered as today. Each answer is stored with the player's text, the
moves it was scored into and the reply, so a reload resumes exactly and `replayed` rebuilds the
talk from the stored moves alone.

The LLM only (a) scores the player's answer into the kind's closed moves, (b) suggests answers
and (c) words the other side's decided reaction and next question, each validated, within the
conversations' monthly cap. Over it, offline, set to templates or in tests, talks run in
template mode: the player picks moves from labelled buttons, and the engine is identical. The
player's text is untrusted: quoted as data, never an instruction, never executed."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.conversations import classifier, talk_prompts, talk_store, talk_templates
from tst.conversations.common import (
    ConversationMovedError,
    ConversationWriter,
    ModeInfo,
    _ask,
    _log_calls,
    _now,
    _writer,
    clean_message,
    mode_info,
    must,
)
from tst.conversations.talk_view import PublicTalk, public, reaction_of
from tst.db import repository
from tst.db.models import ConversationRoundRow, ConversationRow
from tst.llm.base import LLMAdapter
from tst.loader import LoadedData
from tst.sim.errors import SimError, TalkRuleError, UnknownTalkError
from tst.sim.rng import RngFactory
from tst.sim.state import GameState
from tst.sim.talks import engine, opening
from tst.sim.talks.actions import outcome_action
from tst.sim.talks.config import MOVES, TALK_KINDS, TalkKind
from tst.sim.talks.engine import strength_public
from tst.sim.talks.models import Move, Subject, Talk

PURPOSE = "talk"  # llm_call_log.purpose
type Source = Literal["free", "suggested", "template"]  # M57r-B (item 22): a message's source
OPEN = "open"


@dataclass(frozen=True, slots=True)
class TalkTalks:
    """A talk as the API shows it: its row's public fields and the public view."""

    id: int
    status: str
    opened_turn: int
    error: str | None
    suggestions: tuple[str, ...]
    view: PublicTalk
    # (question, said, source, reply, by): the other side's lines
    messages: tuple[tuple[int, str, str, str, str], ...]
    opening_line: str
    mode: ModeInfo


@dataclass(frozen=True, slots=True)
class Available:
    """A talk the player can hold this month (press and crises; one-to-ones are per person)."""

    kind: str
    source: str
    key: int
    subject: str
    talk_id: int | None  # this month's talk, if one was opened
    status: str  # "" before it is opened


def as_kind(kind: str) -> TalkKind:
    for k in TALK_KINDS:
        if k == kind:
            return k
    raise TalkRuleError(f"unknown talk kind {kind!r}")


def talk_key(kind: str, source: str, key: int, turn: int) -> str:
    return f"talk:{kind}:{source}:{key}:{turn}"


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
    """Talks run within the month they are held: one still open at Continue lapses."""
    for row in session.scalars(
        select(ConversationRow).where(
            ConversationRow.status == OPEN,
            ConversationRow.opened_turn < turn,
            ConversationRow.kind.in_(TALK_KINDS),
        )
    ):
        row.status = "lapsed"
        row.closed_turn = turn


def _talks(
    row: ConversationRow, rounds: Sequence[ConversationRoundRow], data: LoadedData, mode: ModeInfo
) -> TalkTalks:
    talk = talk_store.load(row.state)
    view = public(talk, data.balance.talks)
    opening_line = next((r.reply for r in rounds if r.n < 0), "")
    return TalkTalks(
        id=row.id,
        status=row.status,
        opened_turn=row.opened_turn,
        error=row.error,
        suggestions=tuple(row.suggestions),
        view=view,
        messages=tuple(
            (r.n, r.message, r.message_source, r.reply, r.reply_source) for r in rounds if r.n >= 0
        ),
        opening_line=opening_line
        or (talk_templates.question_line(view, 0) if view.questions else ""),
        mode=mode,
    )


def _row(session: Session, conv_id: int) -> ConversationRow:
    row = session.get(ConversationRow, conv_id)
    if row is None or row.kind not in TALK_KINDS:
        raise UnknownTalkError(f"no talk {conv_id}")
    return row


# --- Reading ------------------------------------------------------------------------------------


def get(path: Path, data: LoadedData, conv_id: int) -> TalkTalks:
    """A read: never writes (a lapse is recorded by the next write)."""
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        row = _row(session, conv_id)
        talks = _talks(row, _history(session, conv_id), data, mode_info(path.parent, data))
    return replace(talks, status=_shown_status(row, state.turn))


def listing(path: Path, data: LoadedData, person_id: int | None = None) -> list[TalkTalks]:
    mode = mode_info(path.parent, data)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        q = select(ConversationRow).where(ConversationRow.kind.in_(TALK_KINDS))
        if person_id is not None:
            q = q.where(ConversationRow.counterpart_key == f"person:{person_id}")
        rows = list(session.scalars(q.order_by(ConversationRow.id.desc())))
        return [
            replace(
                _talks(r, _history(session, r.id), data, mode),
                status=_shown_status(r, state.turn),
            )
            for r in rows
        ]


def _subjects(state: GameState, data: LoadedData) -> list[tuple[TalkKind, Subject]]:
    out: list[tuple[TalkKind, Subject]] = []
    press = opening.press_subject(state, data.game_data)
    if press is not None:
        out.append(press)
    out += [("crisis", s) for s in opening.crisis_subjects(state, data.balance.talks)]
    return out


def available(path: Path, data: LoadedData) -> list[Available]:
    """This month's interviews and press conferences, and the talks already held on them."""
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        out = []
        for kind, s in _subjects(state, data):
            row = session.scalars(
                select(ConversationRow).where(
                    ConversationRow.deal_key == talk_key(kind, s.source, s.key, state.turn)
                )
            ).first()
            out.append(
                Available(
                    kind,
                    s.source,
                    s.key,
                    s.words,
                    row.id if row else None,
                    _shown_status(row, state.turn) if row else "",
                )
            )
        return out


def held_this_month(path: Path, person_ids: Sequence[int]) -> dict[int, str]:
    """Person id -> this month's one-to-one status, for those who had one."""
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        out = {}
        for pid in person_ids:
            row = session.scalars(
                select(ConversationRow).where(
                    ConversationRow.deal_key == talk_key("one_to_one", "person", pid, state.turn)
                )
            ).first()
            if row is not None:
                out[pid] = _shown_status(row, state.turn)
        return out


def replayed(path: Path, data: LoadedData, conv_id: int) -> Talk:
    """The talk rebuilt from its opening and its stored moves: no LLM (ADR-0023)."""
    with repository.open_session(path) as session:
        row = _row(session, conv_id)
        rounds = [r for r in _history(session, conv_id) if r.n >= 0]
        stored = talk_store.load(row.state)
    start = replace(stored, answers=(), status="open", effects=None)
    played = tuple(tuple(talk_store.move(m) for m in r.moves) for r in rounds)
    return engine.replay(start, played, data.balance.talks)


# --- Opening --------------------------------------------------------------------------------------


def _allowed(view: PublicTalk) -> list[str]:
    out = [view.offer, view.subject]
    for q in view.questions:
        out += [*q.facts, q.question, q.offer]
    if view.counterpart.morale is not None:
        out.append(str(view.counterpart.morale))
    return out


def _suggest(
    writer: ConversationWriter | None,
    view: PublicTalk,
    q: int,
    said: list[tuple[str, str]],
    data: LoadedData,
) -> tuple[list[str], str]:
    tb = data.balance.talks
    fallback = talk_templates.suggestions(view, q, tb.suggestions)
    if writer is None:
        return fallback, "template"
    system, user = talk_prompts.suggest_prompt(view, q, said, tb.suggestions, tb.history_items)
    got = _ask(writer, "suggest", system, user, {"replies": fallback}, PURPOSE)
    out = classifier.suggestions_from(got, tb.suggestions, tb.max_message_chars)
    return (out, writer.adapter.name) if out else (fallback, "template")


def _opening(
    writer: ConversationWriter | None, view: PublicTalk, data: LoadedData
) -> tuple[str, str, list[str], str]:
    tb = data.balance.talks
    line = talk_templates.question_line(view, 0)
    source = "template"
    if writer is not None:
        system, user = talk_prompts.speak_prompt(
            view, None, 0, [], "", tb.max_reply_words, tb.history_items
        )
        got = _ask(writer, "reply", system, user, line, PURPOSE)
        ok = classifier.reply_ok(got, _allowed(view), tb.max_reply_words)
        if ok:
            line, source = ok, writer.adapter.name
    sug, sug_source = _suggest(writer, view, 0, [], data)
    return line, source, sug, sug_source


def _energy_problem(
    state: GameState, kind: TalkKind, data: LoadedData, press_event: bool = False
) -> str | None:
    founder = state.founder_of(state.player.id)
    if founder is None:
        return "the founder speaks for the company; there is none"
    energy = state.person_state(founder.id).energy
    need = data.balance.talks.energy[kind]
    if press_event:  # the press event's own answer costs what it does today (29.1)
        need += data.balance.founder.energy_cost["choose_event"]
    if energy is not None and energy < need:
        return f"the talk needs {need} energy; {energy} left this month"
    return None


def _morale_facts(
    session: Session, state: GameState, pid: int, data: LoadedData
) -> tuple[int | None, tuple[str, ...], tuple[str, ...]]:
    """What the company sees of a person: shown morale, its two weakest causes, and revealed
    interests (the morale breakdown's and the profile's own words)."""
    from tst.api import org_views
    from tst.sim.hiring.phases import monthly_costs
    from tst.sim.state import company_cash

    cid = state.player.id
    ps = state.person_state(pid)
    shown = round(ps.morale) if ps.morale is not None else None
    cash = company_cash(repository.ledger_balances(session), cid)
    projected = sum(a for _, _, a in monthly_costs(state, cid, data.balance, data.game_data))
    terms = org_views.morale_breakdown(state, cid, pid, data, cash, projected).terms
    weak = sorted((t for t in terms if t.key != "base" and t.value < 0), key=lambda t: t.value)
    causes = tuple(f"{t.label.lower()} weighs on their morale" for t in weak[:2])
    reveal = state.reveal(cid, pid)
    interests: tuple[str, ...] = ()
    if reveal is not None and reveal.profile_revealed_turn is not None:
        labels = {i.key: i.label for i in data.game_data.interests}
        interests = tuple(labels.get(k, k).lower() for k in state.person(pid).interests)
    return shown, causes, interests


def _delegate_ok(state: GameState, delegate_id: int, pid: int) -> None:
    """A seat holder may hold one-to-ones with their own reports (40): someone in a unit they
    manage, or below it."""
    from tst.sim.org.rules import org_view

    cid = state.player.id
    if not any(s.person_id == delegate_id and s.company_id == cid for s in state.exec_seats):
        raise TalkRuleError("only a seat holder holds one-to-ones for you")
    view = org_view(state, cid)
    above: list[int] = []
    manager = view.manager_of.get(pid)
    while manager is not None and manager not in above:
        above.append(manager)
        manager = view.manager_of.get(manager)
    if delegate_id not in above:
        raise TalkRuleError("a seat holder holds one-to-ones with their own reports")


def open_talk(
    path: Path,
    data: LoadedData,
    kind: str,
    params: dict[str, Any] | None = None,
    *,
    adapter: LLMAdapter | None = None,
) -> TalkTalks:
    """Open this month's talk of `kind` on its subject, or resume it if it is open.

    params: {"source": press | recall | robotaxi, "key": id} for an interview or crisis;
    {"person_id": id, "delegate_id": id?} for a one-to-one."""
    tkind = as_kind(kind)
    params = dict(params or {})
    save_dir = path.parent
    mode = mode_info(save_dir, data, adapter)
    delegate_id = params.get("delegate_id")
    writer = _writer(save_dir, data, adapter) if mode.mode == "llm" and not delegate_id else None
    repository.migrate.ensure_current(path)
    # M57r-B (review 10 item 20): the opening line's and suggestions' calls run between a read
    # and the write, never inside the save's write transaction; the write opens the same talk
    # or refuses (ConversationMovedError) if the save moved on in between
    with repository.read_session(path) as session:
        first = _prepare_open(session, data, tkind, kind, params)
        if isinstance(first, ConversationRow):
            return _talks(first, _history(session, first.id), data, mode)
    view = public(first.talk, data.balance.talks)
    suggestions: list[str] = []
    if delegate_id is not None:
        line, line_source, sug_source = talk_templates.question_line(view, 0), "template", ""
    else:
        line, line_source, suggestions, sug_source = _opening(writer, view, data)
    with repository.write_session(path) as session:
        state = repository.load_current(session)
        _lapse(session, state.turn)
        again = _prepare_open(session, data, tkind, kind, params)
        if isinstance(again, ConversationRow):
            return _talks(again, _history(session, again.id), data, mode)
        if again != first:
            raise ConversationMovedError("the game moved on while the talk opened: open it again")
        talk = first.talk
        row = ConversationRow(
            kind=kind,
            deal_key=first.key,
            counterpart_key=first.counterpart,
            subject=view.subject,
            status=OPEN,
            opened_turn=state.turn,
            params=params,
            state=talk_store.dump(talk),
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
                n=-1,
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
        conv_id = row.id
        talks = _talks(row, _history(session, row.id), data, mode)
    if delegate_id is not None:
        for moves in engine.delegated_moves(talk):
            answer(path, data, conv_id, moves=[{"kind": m.kind} for m in moves], adapter=adapter)
        return get(path, data, conv_id)
    return talks


@dataclass(frozen=True, slots=True)
class _Opening:
    key: str
    counterpart: str
    talk: Talk


def _prepare_open(
    session: Session, data: LoadedData, tkind: TalkKind, kind: str, params: dict[str, Any]
) -> ConversationRow | _Opening:
    """The open talk on this subject this month, or the talk to open (TalkRuleError when it
    may not): the same in a read and in the write after it unless the save moved on."""
    state = repository.read_state(session)
    delegate_id = params.get("delegate_id")
    rng = RngFactory(state.save_meta.master_seed)
    if tkind == "one_to_one":
        pid = int(params.get("person_id", -1))
        source, key = "person", pid
    else:
        source, key = str(params.get("source", "press")), int(params.get("key", -1))
    dkey = talk_key(kind, source, key, state.turn)
    found = session.scalars(select(ConversationRow).where(ConversationRow.deal_key == dkey)).first()
    if found is not None and found.status == OPEN:
        return found
    if found is not None:
        what = "a one-to-one with them" if tkind == "one_to_one" else "this talk"
        raise TalkRuleError(f"{what} was already held this month ({found.status})")
    if tkind == "one_to_one":
        if delegate_id is not None:
            _delegate_ok(state, int(delegate_id), pid)
        else:
            why = _energy_problem(state, tkind, data)
            if why is not None:
                raise TalkRuleError(why)
        opening.person_subject(state, pid)  # raises for someone not on the staff
        shown, causes, interests = _morale_facts(session, state, pid, data)
        talk = opening.open_one_to_one(
            state,
            pid,
            rng,
            data.balance,
            data.game_data,
            morale_shown=shown,
            causes=causes,
            revealed_interests=interests,
            delegate_id=None if delegate_id is None else int(delegate_id),
        )
        return _Opening(dkey, f"person:{pid}", talk)
    subject = next(
        (
            s
            for k, s in _subjects(state, data)
            if k == tkind and s.source == source and s.key == key
        ),
        None,
    )
    if subject is None:
        raise TalkRuleError("there is no such press moment or crisis this month")
    why = _energy_problem(state, tkind, data, subject.event_id is not None)
    if why is not None:
        raise TalkRuleError(why)
    talk = opening.open_press(state, tkind, subject, rng, data.balance, data.game_data)
    return _Opening(dkey, f"press:{talk.counterpart.organisation}", talk)


# --- Answers and the outcome ---------------------------------------------------------------------


def _parse_moves(raw: Sequence[dict[str, Any]], kind: TalkKind, max_moves: int) -> tuple[Move, ...]:
    """Template mode's buttons: the kind's closed set, checked like the classifier's."""
    out = []
    for m in list(raw)[:max_moves]:
        k = m.get("kind")
        if k not in MOVES[kind]:
            raise TalkRuleError(f"unknown move {k!r}")
        out.append(Move(str(k)))
    if not out:
        raise TalkRuleError("pick at least one move")
    return tuple(out)


def moves_from(content: object, kind: TalkKind, max_moves: int) -> tuple[tuple[Move, ...], bool]:
    """The classifier's JSON validated (ADR-0005): only the kind's moves, else `neutral`."""
    if not isinstance(content, dict) or set(content) != {"moves"}:
        return (Move("neutral"),), False
    raw = content["moves"]
    if not isinstance(raw, list) or not raw:
        return (Move("neutral"),), False
    out = []
    for item in raw[:max_moves]:
        if not isinstance(item, dict) or set(item) != {"move"}:
            return (Move("neutral"),), False
        k = item.get("move")
        if k not in MOVES[kind]:
            return (Move("neutral"),), False
        out.append(Move(str(k)))
    return tuple(out), True


def answer(
    path: Path,
    data: LoadedData,
    conv_id: int,
    *,
    message: str | None = None,
    moves: Sequence[dict[str, Any]] | None = None,
    source: Source = "free",
    adapter: LLMAdapter | None = None,
) -> TalkTalks:
    """One answer to the current question: the player's text (scored by the LLM) or picked
    moves (template mode). The engine decides; the other side's line is worded after.

    M57r-B (review 10 items 20 and 3): the calls run between a read and the write; the write
    re-checks the talk has not moved on, then stores the answer and, when it ends the talk, the
    outcome's action and the closure in one transaction. A failed scoring call plays nothing."""
    tb = data.balance.talks
    save_dir = path.parent
    mode = mode_info(save_dir, data, adapter)
    writer = _writer(save_dir, data, adapter) if mode.mode == "llm" else None
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        row = _row(session, conv_id)
        if _shown_status(row, state.turn) != OPEN:
            raise TalkRuleError(f"this talk is over ({_shown_status(row, state.turn)})")
        seen, turn = row.state, state.turn
        talk = talk_store.load(row.state)
        kind = as_kind(row.kind)
        said = _said(_history(session, conv_id))
    q = talk.next_question
    if q is None:
        raise TalkRuleError("every question has been answered")
    if talk.delegate_id is not None:
        writer = None  # a delegated talk is played by the engine, never the LLM
    view = public(talk, tb)
    text = (
        clean_message(message, tb.max_message_chars, TalkRuleError) if message is not None else ""
    )
    if moves:
        claimed, moves_source = _parse_moves(moves, kind, tb.max_moves), "template"
        source = "template" if not text else source
    elif text and writer is not None:
        system, user = talk_prompts.classify_prompt(view, q.n, said, text, tb.history_items)
        fallback = {"moves": [{"move": "neutral"}]}
        got = must(_ask(writer, "classify", system, user, fallback, PURPOSE), writer)
        claimed, valid = moves_from(got, kind, tb.max_moves)
        moves_source = writer.adapter.name if valid else "invalid"
    elif text:
        raise TalkRuleError("talks are in template mode: pick moves from the buttons")
    else:
        raise TalkRuleError("write an answer, or pick moves")
    after = engine.play(talk, claimed, tb)
    view_after = public(after, tb)
    checked = after.answers[-1].moves
    reaction = reaction_of(strength_public(after, q, checked, tb))
    nxt = after.next_question.n if after.next_question is not None else None
    reply, reply_source = _line(writer, view_after, reaction, nxt, said, text, data)
    sug: list[str] = []
    sug_source = "template"
    if nxt is not None and talk.delegate_id is None:
        sug, sug_source = _suggest(writer, view_after, nxt, [*said, (text, reply)], data)
    acted = False
    with repository.write_session(path) as session:
        state = repository.read_state(session)
        _lapse(session, state.turn)
        row = _row(session, conv_id)
        if row.status != OPEN:
            raise TalkRuleError(f"this talk is over ({row.status})")
        if state.turn != turn or row.state != seen:
            raise ConversationMovedError("this talk moved on while you wrote: send it again")
        session.add(
            ConversationRoundRow(
                conversation_id=conv_id,
                n=q.n,
                message=text or ", ".join(m.words for m in view_after.answers[-1].claimed),
                message_source=source if talk.delegate_id is None else "delegate",
                moves=[{"kind": m.kind} for m in claimed],
                moves_source=moves_source,
                offer=[],
                reply=reply,
                reply_source=reply_source,
                created_at=_now(),
            )
        )
        row.state = talk_store.dump(after)
        row.suggestions = sug if nxt is not None and talk.delegate_id is None else []
        if row.suggestions:
            row.suggestions_source = sug_source
        if writer is not None:
            _log_calls(session, state.turn, writer)
        if after.status == "done":  # the outcome's action and the closure, in this transaction
            error = _conclude(session, data, after)
            row.status = "failed" if error else "done"
            row.error = error
            row.closed_turn = state.turn
            acted = error is None
    if acted:
        repository.after_action(path, data)
    return get(path, data, conv_id)


def _line(
    writer: ConversationWriter | None,
    view_after: PublicTalk,
    reaction: str,
    nxt: int | None,
    said: list[tuple[str, str]],
    text: str,
    data: LoadedData,
) -> tuple[str, str]:
    """The other side's line: the template's (the next question, or the close) unless the
    LLM's wording passes the checks (M57r-B, item 21: no number without its unit, no amount
    in words)."""
    tb = data.balance.talks
    fallback = talk_templates.speak_line(view_after, reaction, nxt)
    if writer is None:
        return fallback, "template"
    system, user = talk_prompts.speak_prompt(
        view_after, reaction, nxt, said, text, tb.max_reply_words, tb.history_items
    )
    got = _ask(writer, "reply", system, user, fallback, PURPOSE)
    ok = classifier.reply_ok(got, _allowed(view_after), tb.max_reply_words)
    return (ok, writer.adapter.name) if ok else (fallback, "template")


def _conclude(session: Session, data: LoadedData, talk: Talk) -> str | None:
    """Run the outcome's action in the caller's write transaction (M57r-B, review 10 item 3:
    the last answer, the action and the closure commit together); the error's message if the
    rules refused it (nothing is applied then)."""
    state = repository.load_current(session)
    founder = state.founder_of(state.player.id)
    if founder is None:
        return "the founder speaks for the company; there is none"
    salary = 0
    if talk.counterpart.person_id is not None:
        e = state.employment_of(talk.counterpart.person_id)
        salary = e.salary_cents if e is not None else 0
    try:
        action = outcome_action(talk, founder.id, salary, data.balance.talks.one_to_one.raise_share)
        repository.apply_in_session(session, data, action)
    except SimError as exc:
        return exc.message
    return None


def skip(path: Path, data: LoadedData, conv_id: int) -> TalkTalks:
    """61: today's outcome. Nothing the talk would have moved moves; no action runs."""
    with repository.write_session(path) as session:
        state = repository.read_state(session)
        _lapse(session, state.turn)
        row = _row(session, conv_id)
        if row.status != OPEN:
            raise TalkRuleError(f"this talk is over ({row.status})")
        row.state = talk_store.dump(engine.skip(talk_store.load(row.state)))
        row.status = "skipped"
        row.closed_turn = state.turn
        row.suggestions = []
    return get(path, data, conv_id)
