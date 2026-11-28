"""What every conversation kind shares (ADR-0023): the conversations' own monthly cap and
template mode, the adapter, the player's text cleaned as untrusted input, one LLM call within
the cap, its log and spend, and running an outcome's action through a busy save. Generalised
from M47's negotiation service for M48's meetings; behaviour unchanged."""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from tst.db.events import default_adapter
from tst.db.models import LLMCallLogRow
from tst.events.service import Writer
from tst.llm.base import ConversationPrompt, LLMAdapter
from tst.llm.settings import LLMSettings, add_spend, load_settings, month_spend
from tst.loader import LoadedData
from tst.sim.errors import NegotiationRuleError, SimError

type Mode = Literal["llm", "template"]
type ModeReason = Literal["", "setting", "offline", "budget"]


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


def _spend(save_dir: Path, writer: Writer) -> None:
    calls = sum(1 for r in writer.records if r.outcome != "budget")
    if writer.spent_cents or calls:
        add_spend(
            save_dir,
            0.0,
            conversation_cents=writer.spent_cents,
            conversation_calls=calls,
        )


def _ask(
    writer: Writer, kind: str, system: str, user: str, fallback: Any, purpose: str = "negotiation"
) -> Any | None:
    """One conversation call within the cap; None if over it or it failed."""
    if not writer.live or not writer.can_spend():
        return None
    completion = writer.adapter.generate_conversation(
        ConversationPrompt(kind, system, user, fallback)  # type: ignore[arg-type]
    )
    outcome = "ok" if completion.content is not None and completion.error is None else "error"
    writer.record(purpose, system + "\n" + user, completion, outcome)
    return completion.content if outcome == "ok" else None
