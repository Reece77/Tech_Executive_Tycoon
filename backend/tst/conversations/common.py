"""What every conversation kind shares (ADR-0023): the conversations' own monthly cap and
template mode, the adapter, the player's text cleaned as untrusted input, one LLM call within
the cap, and its log and spend. Generalised from M47's negotiation service for M48's meetings.

M57r-B (review 10 items 20 and 22): each call reserves its bounded cost against the folder's
cap before it runs and records what it cost in a `finally` (`budget`); a call that fails, or
the cap refusing a call the round needs, is a retryable `ConversationCallError`, never a
`neutral` score. The kinds' services make their calls outside the save's write transaction
and re-check that the conversation has not moved on before they store the round."""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from tst.conversations import budget
from tst.db.events import default_adapter
from tst.db.models import LLMCallLogRow
from tst.events.service import Writer
from tst.llm.base import ConversationPrompt, LLMAdapter
from tst.llm.settings import LLMSettings, load_settings, month_spend
from tst.loader import LoadedData
from tst.sim.errors import NegotiationRuleError, SimError

type Mode = Literal["llm", "template"]
type ModeReason = Literal["", "setting", "offline", "budget"]


class ConversationCallError(SimError):
    """The LLM call a round needs failed (unreachable, rate-limited, refused) or the month's
    cap could not cover it: the round is not played, and sending it again is safe."""

    code = "conversation_call_failed"


class ConversationMovedError(SimError):
    """The conversation changed while this round's calls ran (another tab, a retry): nothing
    was stored, and sending it again is safe."""

    code = "conversation_moved"


@dataclass
class ConversationWriter(Writer):
    """The events' Writer, with the folder and cap each call reserves against."""

    save_dir: Path = Path()
    cap_cents: float = 0.0
    failed: bool = False  # a call came back with an error
    refused: bool = False  # the cap could not cover a call


@dataclass(frozen=True, slots=True)
class ModeInfo:
    mode: Mode
    reason: ModeReason  # why template mode ("" when the LLM is in use)
    cap_cents: int
    spent_cents: float


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
    # M57r-B: what's left (open reservations aside) must cover a typical call's bound, so a
    # call refused for the cap is followed by template mode, as its message says
    left = cap - spent - budget.outstanding(save_dir)
    if spent >= cap or left < _typical_bound(settings, adapter or conversation_adapter(save_dir)):
        return ModeInfo("template", "budget", cap, spent)
    return ModeInfo("llm", "", cap, spent)


TYPICAL_PROMPT_CHARS = 4000  # tunable-exempt: about a conversation prompt's length, for the bound


def _typical_bound(settings: LLMSettings, adapter: LLMAdapter) -> float:
    model = getattr(adapter, "model_events", None) or getattr(
        adapter, "model", settings.model_events
    )
    return settings.cost_cents(str(model), TYPICAL_PROMPT_CHARS, budget.MAX_OUTPUT_TOKENS)


def _writer(save_dir: Path, data: LoadedData, adapter: LLMAdapter | None) -> ConversationWriter:
    settings = load_settings(save_dir)
    cap = cap_cents(settings, data)
    spent = month_spend(save_dir).conversation_cents
    return ConversationWriter(
        adapter=adapter or conversation_adapter(save_dir),
        settings=settings,
        budget_left=lambda: cap - spent,
        debug=os.environ.get("TST_LLM_DEBUG") == "1",
        save_dir=save_dir,
        cap_cents=cap,
    )


def clean_message(text: str, max_chars: int, error: type[SimError] = NegotiationRuleError) -> str:
    """The player's message as stored and quoted: control characters removed, whitespace
    collapsed, at most `max_chars`. It stays untrusted: nothing reads it as an instruction."""
    kept = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch == " ")
    clean = " ".join(kept.split())
    if not clean:
        raise error("write a message, or pick moves")
    if len(clean) > max_chars:
        raise error(f"a message has at most {max_chars} characters")
    return clean


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


def _bound_cents(writer: ConversationWriter, system: str, user: str) -> float:
    """The most a call can cost: its prompt at one token a character, and the most output."""
    model = getattr(writer.adapter, "model_events", None) or getattr(
        writer.adapter, "model", writer.settings.model_events
    )
    return writer.settings.cost_cents(str(model), len(system) + len(user), budget.MAX_OUTPUT_TOKENS)


def _ask(
    writer: ConversationWriter,
    kind: str,
    system: str,
    user: str,
    fallback: Any,
    purpose: str = "negotiation",
) -> Any | None:
    """One conversation call within the cap; None if the cap refused it or it failed
    (`writer.refused`, `writer.failed` say which). Its cost is reserved first and recorded
    in a `finally`, so a failure after the call never loses its spend."""
    if not writer.live:
        return None
    held = budget.reserve(writer.save_dir, writer.cap_cents, _bound_cents(writer, system, user))
    if held is None:
        writer.refused = True
        writer.records.append(_budget_record(purpose))
        return None
    cost = 0.0
    try:
        completion = writer.adapter.generate_conversation(
            ConversationPrompt(kind, system, user, fallback)  # type: ignore[arg-type]
        )
        ok = completion.content is not None and completion.error is None
        cost = writer.record(purpose, system + "\n" + user, completion, "ok" if ok else "error")
    finally:
        budget.settle(writer.save_dir, held, cost, 1)
    if not ok:
        writer.failed = True
        return None
    return completion.content


def _budget_record(purpose: str) -> Any:
    from tst.llm.base import CallRecord

    return CallRecord(purpose, "template", "", outcome="budget")


def must(got: Any | None, writer: ConversationWriter) -> Any:
    """A call the round cannot be played without (scoring the player's text): its answer, or
    a retryable error that plays nothing (never a `neutral` score)."""
    if got is not None:
        return got
    if writer.refused:
        raise ConversationCallError(
            "this month's conversation budget can't cover another call: send it again to "
            "play by the buttons"
        )
    raise ConversationCallError(
        "the counterpart didn't hear you (the language model did not answer): send it again"
    )
