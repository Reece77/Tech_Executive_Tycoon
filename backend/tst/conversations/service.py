"""The conversation service (ADR-0023; docs/formulas.md 58): negotiations between turns.

A negotiation opens on a deal the engine prices (tst.sim.negotiation.deals), plays rounds
through the pure engine, and ends through an ordinary action (the deal kind's own, or
WalkAway), logged in decision_log like any action: so a replay of the game never reads a
conversation and never calls the LLM. Each round stores the player's message, the moves it was
scored into and the reply, so a reload resumes exactly and `replayed` rebuilds the engine's
record from the stored moves alone.

The LLM only (a) scores the player's message into moves, (b) suggests replies and (c) words the
counterpart's decided reply, each validated, within the conversations' own monthly cap. Over the
cap, offline, set to templates or in tests, conversations run in template mode: the player picks
moves from labelled buttons and the engine is identical. The player's text is untrusted: quoted
as data, never an instruction (prompts.py), and never executed."""

from __future__ import annotations

import os
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from tst.conversations import classifier, prompts, store, templates
from tst.conversations.view import PublicNegotiation, public
from tst.db import repository
from tst.db.events import default_adapter
from tst.db.models import ConversationRoundRow, ConversationRow, LLMCallLogRow
from tst.events.service import Writer
from tst.llm.base import ConversationPrompt, LLMAdapter
from tst.llm.settings import LLMSettings, add_spend, load_settings, month_spend
from tst.loader import LoadedData
from tst.sim.errors import NegotiationRuleError, SimError, UnknownNegotiationError
from tst.sim.negotiation import deals, engine
from tst.sim.negotiation.config import DEAL_KINDS, MOVE_KINDS, DealKind
from tst.sim.negotiation.models import Move, Negotiation
from tst.sim.rng import RngFactory

PURPOSE = "negotiation"  # llm_call_log.purpose
OPEN = "open"
type Mode = Literal["llm", "template"]
type ModeReason = Literal["", "setting", "offline", "budget"]


@dataclass(frozen=True, slots=True)
class ModeInfo:
    mode: Mode
    reason: ModeReason  # why template mode ("" when the LLM is in use)
    cap_cents: int
    spent_cents: float


@dataclass(frozen=True, slots=True)
class Talks:
    """A conversation as the API shows it: its row's public fields and the public view."""

    id: int
    status: str
    opened_turn: int
    cooldown_until: int | None
    error: str | None
    suggestions: tuple[str, ...]
    view: PublicNegotiation
    messages: tuple[tuple[int, str, str, str, str], ...]  # (round, said, source, reply, by)
    opening_line: str
    mode: ModeInfo


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def cap_cents(settings: LLMSettings, data: LoadedData) -> int:
    chosen = settings.conversation_budget_cents
    return data.balance.llm.conversation_budget_cents if chosen is None else chosen


def conversation_adapter(save_dir: Path) -> LLMAdapter:
    """The adapter conversations use: TST_CONVERSATION_ADAPTER, else the events' adapter."""
    from tst.config import get_settings
    from tst.llm.settings import active_adapter

    forced = get_settings().conversation_adapter
    if forced:
        settings = get_settings()
        return active_adapter(load_settings(save_dir), settings.anthropic_api_key, forced)
    return default_adapter(save_dir)


def mode_info(save_dir: Path, data: LoadedData, adapter: LLMAdapter | None = None) -> ModeInfo:
    """LLM or template mode now (ADR-0023 section 4)."""
    settings = load_settings(save_dir)
    cap = cap_cents(settings, data)
    spent = month_spend(save_dir).conversation_cents
    live = (adapter or conversation_adapter(save_dir)).name != "template"
    if settings.conversation_mode == "template":
        return ModeInfo("template", "setting", cap, spent)
    if not live:
        return ModeInfo("template", "offline", cap, spent)
    if spent >= cap:
        return ModeInfo("template", "budget", cap, spent)
    return ModeInfo("llm", "", cap, spent)


def _writer(save_dir: Path, data: LoadedData, adapter: LLMAdapter | None) -> Writer:
    settings = load_settings(save_dir)
    cap = cap_cents(settings, data)
    spent = month_spend(save_dir).conversation_cents
    return Writer(
        adapter=adapter or conversation_adapter(save_dir),
        settings=settings,
        budget_left=lambda: cap - spent,
        debug=os.environ.get("TST_LLM_DEBUG") == "1",
    )


def clean_message(text: str, max_chars: int) -> str:
    """The player's message as stored and quoted: control characters removed, whitespace
    collapsed, at most `max_chars`. It stays untrusted: nothing reads it as an instruction."""
    kept = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch == " ")
    clean = " ".join(kept.split())
    if not clean:
        raise NegotiationRuleError("write a message, or pick moves")
    if len(clean) > max_chars:
        raise NegotiationRuleError(f"a message has at most {max_chars} characters")
    return clean


def as_kind(kind: str) -> DealKind:
    for k in DEAL_KINDS:
        if k == kind:
            return k
    raise NegotiationRuleError(f"unknown deal kind {kind!r}")


def deal_key(kind: str, key: Sequence[int]) -> str:
    return ":".join([kind, *(str(k) for k in key)])


def _relationship(session: Session, counterpart: str, data: LoadedData) -> int:
    b = data.balance.negotiation
    total: int = sum(
        r.relationship_change
        for r in session.scalars(
            select(ConversationRow).where(ConversationRow.counterpart_key == counterpart)
        )
    )
    return min(max(total, b.relationship_floor), b.relationship_ceiling)


def _lapse(session: Session, turn: int) -> None:
    """Talks run within the month they open (M47 decision): the deal's prices are that month's."""
    for row in session.scalars(
        select(ConversationRow).where(
            ConversationRow.status == OPEN, ConversationRow.opened_turn < turn
        )
    ):
        row.status = "lapsed"
        row.closed_turn = turn


def _history(session: Session, conv_id: int) -> list[ConversationRoundRow]:
    return list(
        session.scalars(
            select(ConversationRoundRow)
            .where(ConversationRoundRow.conversation_id == conv_id)
            .order_by(ConversationRoundRow.n)
        )
    )


def _said(rows: Sequence[ConversationRoundRow]) -> list[tuple[str, str]]:
    return [(r.message, r.reply) for r in rows]


def _log_calls(session: Session, turn: int, writer: Writer) -> None:
    now = _now()
    session.add_all(
        LLMCallLogRow(
            turn=turn,
            purpose=r.purpose,
            model=r.model,
            prompt_hash=r.prompt_hash,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            cost_cents=r.cost_cents,
            latency_ms=r.latency_ms,
            outcome=r.outcome,
            created_at=now,
            prompt=r.prompt,
            response=r.response,
        )
        for r in writer.records
    )


def _spend(save_dir: Path, writer: Writer) -> None:
    calls = sum(1 for r in writer.records if r.outcome != "budget")
    if writer.spent_cents or calls:
        add_spend(
            save_dir,
            0.0,
            conversation_cents=writer.spent_cents,
            conversation_calls=calls,
        )


def _ask(writer: Writer, kind: str, system: str, user: str, fallback: Any) -> Any | None:
    """One conversation call within the cap; None if over it or it failed."""
    if not writer.live or not writer.can_spend():
        return None
    completion = writer.adapter.generate_conversation(
        ConversationPrompt(kind, system, user, fallback)  # type: ignore[arg-type]
    )
    outcome = "ok" if completion.content is not None and completion.error is None else "error"
    writer.record(PURPOSE, system + "\n" + user, completion, outcome)
    return completion.content if outcome == "ok" else None


def _suggest(
    writer: Writer | None, view: PublicNegotiation, said: list[tuple[str, str]], data: LoadedData
) -> tuple[list[str], str]:
    b = data.balance.negotiation
    fallback = templates.suggestions(view, b.suggestions)
    if writer is None or view.status != OPEN:
        return fallback, "template"
    system, user = prompts.suggest_prompt(view, said, b.suggestions, b.history_rounds)
    got = _ask(writer, "suggest", system, user, {"replies": fallback})
    out = classifier.suggestions_from(got, b.suggestions, b.max_message_chars)
    return (out, writer.adapter.name) if out else (fallback, "template")


# --- Reading ------------------------------------------------------------------------------


def _talks(
    row: ConversationRow, rounds: Sequence[ConversationRoundRow], data: LoadedData, mode: ModeInfo
) -> Talks:
    neg = store.load(row.state)
    view = public(neg, data.balance.negotiation)
    return Talks(
        id=row.id,
        status=row.status,
        opened_turn=row.opened_turn,
        cooldown_until=row.cooldown_until,
        error=row.error,
        suggestions=tuple(row.suggestions),
        view=view,
        messages=tuple((r.n, r.message, r.message_source, r.reply, r.reply_source) for r in rounds),
        opening_line=templates.opening_line(
            public(replace(neg, rounds=(), counter=neg.opening), data.balance.negotiation)
        ),
        mode=mode,
    )


def _shown_status(row: ConversationRow, turn: int) -> str:
    """Talks still open from an earlier month read as lapsed (written at the next write)."""
    return "lapsed" if row.status == OPEN and row.opened_turn < turn else row.status


def get(path: Path, data: LoadedData, conv_id: int) -> Talks:
    """A read: never writes (a lapse is recorded by the next open or round)."""
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        row = session.get(ConversationRow, conv_id)
        if row is None:
            raise UnknownNegotiationError(f"no negotiation {conv_id}")
        talks = _talks(row, _history(session, conv_id), data, mode_info(path.parent, data))
    return replace(talks, status=_shown_status(row, state.turn))


def listing(path: Path, data: LoadedData) -> list[Talks]:
    mode = mode_info(path.parent, data)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        rows = list(session.scalars(select(ConversationRow).order_by(ConversationRow.id.desc())))
        return [
            replace(
                _talks(r, _history(session, r.id), data, mode), status=_shown_status(r, state.turn)
            )
            for r in rows
        ]


def replayed(path: Path, data: LoadedData, conv_id: int) -> Negotiation:
    """The negotiation rebuilt from its opening and its stored moves: no LLM (ADR-0023)."""
    with repository.open_session(path) as session:
        row = session.get(ConversationRow, conv_id)
        if row is None:
            raise UnknownNegotiationError(f"no negotiation {conv_id}")
        rounds = _history(session, conv_id)
    neg = store.load(row.state)
    start = replace(
        neg,
        level=1.0,
        patience_left=neg.hidden.patience,
        counter=neg.opening,
        offer=None,
        rounds=(),
        status="open",
        final=None,
        relationship=neg.relationship_start,
        used_facts=(),
    )
    played = tuple((tuple(r.offer), tuple(store._move(m) for m in r.moves)) for r in rounds)
    return engine.replay(start, played, data.balance.negotiation)


# --- Opening -------------------------------------------------------------------------------


def open_talks(
    path: Path,
    data: LoadedData,
    kind: str,
    params: dict[str, Any],
    *,
    adapter: LLMAdapter | None = None,
) -> Talks:
    """Open talks on a deal, or resume the open talks on it this month."""
    deal_kind = as_kind(kind)
    b = data.balance.negotiation
    save_dir = path.parent
    mode = mode_info(save_dir, data, adapter)
    writer = _writer(save_dir, data, adapter) if mode.mode == "llm" else None
    repository.migrate.ensure_current(path)
    with repository.write_session(path) as session:
        state = repository.load_current(session)
        _lapse(session, state.turn)
        balances = repository.current_balances(session, state.turn)
        rng = RngFactory(state.save_meta.master_seed)
        deal = deals.deal_for(state, deal_kind, params, rng, balances, data.balance, data.game_data)
        key = deal_key(kind, deal.ref.key)
        found = session.scalars(
            select(ConversationRow).where(
                ConversationRow.deal_key == key, ConversationRow.status == OPEN
            )
        ).first()
        if found is not None:
            return _talks(found, _history(session, found.id), data, mode)
        cooled = session.scalars(
            select(ConversationRow).where(
                ConversationRow.kind == kind,
                ConversationRow.counterpart_key == deal.ref.counterpart.key,
                ConversationRow.cooldown_until > state.turn,
            )
        ).first()
        if cooled is not None and cooled.cooldown_until is not None:
            months = cooled.cooldown_until - state.turn
            raise NegotiationRuleError(
                f"{deal.ref.counterpart.organisation or deal.ref.counterpart.name} won't talk "
                f"about this for {months} more months"
            )
        skills, persona = deals.negotiator(state, data.balance)
        neg = engine.open_negotiation(
            deal.ref,
            rng,
            state.turn,
            engine.skill_factor(skills, b),
            persona,
            _relationship(session, deal.ref.counterpart.key, data),
            data.balance,
        )
        view = public(neg, b)
        suggestions, source = _suggest(writer, view, [], data)
        row = ConversationRow(
            kind=kind,
            deal_key=key,
            counterpart_key=deal.ref.counterpart.key,
            subject=deal.ref.subject,
            status=OPEN,
            opened_turn=state.turn,
            params=dict(params),
            state=store.dump(neg),
            suggestions=suggestions,
            suggestions_source=source,
            relationship_change=0,
            created_at=_now(),
        )
        session.add(row)
        if writer is not None:
            _log_calls(session, state.turn, writer)
        session.flush()
        talks = _talks(row, [], data, mode)
    if writer is not None:
        _spend(save_dir, writer)
    return talks


# --- Rounds and outcomes (58.3-58.4) --------------------------------------------------------


def _parse_moves(raw: Sequence[dict[str, Any]], max_moves: int) -> tuple[Move, ...]:
    """Template mode's buttons: the same closed set, checked like the classifier's."""
    out = []
    for m in list(raw)[:max_moves]:
        kind = m.get("kind")
        if kind not in MOVE_KINDS:
            raise NegotiationRuleError(f"unknown move {kind!r}")
        out.append(
            Move(
                kind,
                classifier._index(m.get("term")),
                classifier._index(m.get("other")),
                classifier._index(m.get("fact")),
            )
        )
    if not out:
        raise NegotiationRuleError("pick at least one move")
    return tuple(out)


def _load_open(session: Session, conv_id: int, turn: int) -> tuple[ConversationRow, Negotiation]:
    _lapse(session, turn)
    row = session.get(ConversationRow, conv_id)
    if row is None:
        raise UnknownNegotiationError(f"no negotiation {conv_id}")
    if row.status != OPEN:
        raise NegotiationRuleError(f"these talks are over ({row.status})")
    return row, store.load(row.state)


def _deal(path: Path, data: LoadedData, row: ConversationRow) -> deals.Deal:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        balances = repository.current_balances(session, state.turn)
        rng = RngFactory(state.save_meta.master_seed)
        return deals.deal_for(
            state,
            as_kind(row.kind),
            row.params,
            rng,
            balances,
            data.balance,
            data.game_data,
        )


def _actor(path: Path) -> int:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    founder = state.founder_of(state.player.id)
    if founder is None:
        raise NegotiationRuleError("the founder negotiates; there is none")
    return founder.id


def _conclude(
    path: Path, data: LoadedData, row_id: int, neg: Negotiation
) -> tuple[str | None, int | None]:
    """Run the outcome's action: the agreement, or the walk-away. (error, cooldown_until)."""
    b = data.balance.negotiation
    actor = _actor(path)
    with repository.open_session(path) as session:
        row = session.get(ConversationRow, row_id)
        assert row is not None
        params_row = row
        session.expunge(row)
    deal = _deal(path, data, params_row) if neg.status != "walked" else None
    try:
        if neg.status == "walked":
            stub = deals.Deal(
                neg.kind, params_row.params, _ref_stub(neg), _deal_id(neg.kind, params_row.params)
            )
            action: Any = deals.walk_away(stub, actor, data.balance)
            repository.run_action(path, data, action)
            with repository.read_session(path) as session:
                turn = repository.read_state(session).turn
            return None, turn + b.cooldown_months
        assert deal is not None and neg.final is not None
        action = deals.agreement(deal, neg.final, actor, deal.ref.terms[0].base)
        repository.run_action(path, data, action)
    except SimError as exc:
        return exc.message, None
    return None, None


def _deal_id(kind: str, params: dict[str, Any]) -> int:
    key = {
        "acquisition": "target_id",
        "hire": "candidate_id",
        "retention": "approach_id",
        "government": "contract_id",
        "settlement": "event_id",
        "licence_in": "asset_id",
    }.get(kind)
    return int(params[key]) if key is not None else 0


def _ref_stub(neg: Negotiation) -> Any:
    from tst.sim.negotiation.models import DealRef

    return DealRef(
        neg.kind, (), neg.subject, neg.terms, neg.hidden.medians, neg.counterpart, neg.facts
    )


def _close(
    row: ConversationRow,
    neg: Negotiation,
    data: LoadedData,
    turn: int,
    error: str | None,
    cooldown: int | None,
) -> None:
    b = data.balance.negotiation
    if error is not None:
        row.status = "failed"
        row.error = error
    else:
        row.status = neg.status
    row.closed_turn = turn
    row.cooldown_until = cooldown
    change = neg.relationship - neg.relationship_start
    if neg.status == "walked":
        change += b.relationship_walk
    elif error is None and neg.status in ("agreed", "skipped"):
        change += b.relationship_agree if neg.status == "agreed" else 0
    row.relationship_change = change
    row.state = store.dump(neg)
    row.suggestions = []


def play(
    path: Path,
    data: LoadedData,
    conv_id: int,
    offer: Sequence[int],
    *,
    message: str | None = None,
    moves: Sequence[dict[str, Any]] | None = None,
    source: str = "free",
    adapter: LLMAdapter | None = None,
) -> Talks:
    """One round: the player's message (scored by the LLM) or picked moves (template mode),
    and an offer. The engine decides; the reply is worded after."""
    b = data.balance.negotiation
    save_dir = path.parent
    mode = mode_info(save_dir, data, adapter)
    writer = _writer(save_dir, data, adapter) if mode.mode == "llm" else None
    offer_t = tuple(int(v) for v in offer)
    with repository.write_session(path) as session:
        state = repository.read_state(session)
        row, neg = _load_open(session, conv_id, state.turn)
        engine.check_offer(neg, offer_t)
        said = _said(_history(session, conv_id))
        view = public(neg, b)
        text = clean_message(message, b.max_message_chars) if message is not None else ""
        if moves:
            claimed, moves_source = _parse_moves(moves, b.max_moves), "template"
            source = "template" if not text else source
        elif text and writer is not None:
            offer_shown = [view_value(neg, t, v) for t, v in enumerate(offer_t)]
            system, user = prompts.classify_prompt(view, said, text, offer_shown, b.history_rounds)
            got = _ask(writer, "classify", system, user, {"moves": [{"move": "neutral"}]})
            claimed, valid = classifier.moves_from(got, b.max_moves)
            moves_source = writer.adapter.name if valid else "invalid"
        elif text:
            raise NegotiationRuleError(
                "conversations are in template mode: pick moves from the buttons"
            )
        else:
            raise NegotiationRuleError("write a message, or pick moves")
        after = engine.play_round(neg, offer_t, claimed, b)
        view_after = public(after, b)
        fallback = templates.reply_line(view_after)
        reply, reply_source = fallback, "template"
        if writer is not None:
            system, user = prompts.reply_prompt(
                view_after, said, text, b.max_reply_words, b.history_rounds
            )
            got = _ask(writer, "reply", system, user, fallback)
            allowed = [
                *view_after.rounds[-1].counter_shown,
                *view_after.rounds[-1].offer_shown,
                *view_after.facts,
                *view_after.opening_shown,
            ]
            ok = classifier.reply_ok(got, allowed, b.max_reply_words)
            if ok:
                reply, reply_source = ok, writer.adapter.name
        session.add(
            ConversationRoundRow(
                conversation_id=conv_id,
                n=after.rounds[-1].n,
                message=text or ", ".join(m.words for m in view_after.rounds[-1].claimed),
                message_source=source,
                moves=[_move_json(m) for m in claimed],
                moves_source=moves_source,
                offer=list(offer_t),
                reply=reply,
                reply_source=reply_source,
                created_at=_now(),
            )
        )
        row.state = store.dump(after)
        if after.status == OPEN:
            suggestions, sug_source = _suggest(writer, view_after, [*said, (text, reply)], data)
            row.suggestions = suggestions
            row.suggestions_source = sug_source
        if writer is not None:
            _log_calls(session, state.turn, writer)
        turn = state.turn
    if writer is not None:
        _spend(save_dir, writer)
    if after.status != OPEN:
        error, cooldown = _conclude(path, data, conv_id, after)
        with repository.write_session(path) as session:
            closing = session.get(ConversationRow, conv_id)
            assert closing is not None
            _close(closing, after, data, turn, error, cooldown)
    return get(path, data, conv_id)


def view_value(neg: Negotiation, t: int, v: int) -> str:
    from tst.conversations.view import show_value

    return show_value(neg.terms[t], v)


def _move_json(m: Move) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": m.kind}
    for k in ("term", "other", "fact"):
        if getattr(m, k) is not None:
            out[k] = getattr(m, k)
    return out


def _finish(path: Path, data: LoadedData, conv_id: int, how: Literal["accept", "skip"]) -> Talks:
    with repository.write_session(path) as session:
        state = repository.read_state(session)
        _row, neg = _load_open(session, conv_id, state.turn)
        turn = state.turn
    done = engine.accept_counter(neg) if how == "accept" else engine.skip(neg)
    error, cooldown = _conclude(path, data, conv_id, done)
    with repository.write_session(path) as session:
        closing = session.get(ConversationRow, conv_id)
        assert closing is not None
        if error is not None and how == "accept":
            raise NegotiationRuleError(f"the deal could not close: {error}")
        _close(closing, done, data, turn, error, cooldown)
    return get(path, data, conv_id)


def accept(path: Path, data: LoadedData, conv_id: int) -> Talks:
    """The player takes the counterpart's offer as shown."""
    return _finish(path, data, conv_id, "accept")


def skip(path: Path, data: LoadedData, conv_id: int) -> Talks:
    """58.4: the median outcome, today's terms (always available)."""
    return _finish(path, data, conv_id, "skip")
