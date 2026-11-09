"""The LLM adapter interface (ADR-0005 section 1).

An adapter turns a prompt into words: an event draft (JSON in the spec 12 shape) or a line
of text. It never sees state and never writes it; the event service validates whatever comes
back. `Completion.usage` carries the token counts the budget meter prices (ADR-0005 section 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

type ModelKind = Literal["events", "story"]
# coo: M7b, 17.3; rival_story: M15b addendum 12; explain: M25 (Ask why)
type TextKind = Literal[
    "headlines", "minutes", "exit_line", "coo", "exec_report", "rival_story", "explain"
]

# The JSON the LLM returns for an event (spec 12, formulas.md 16.5). Cash values are dollars.
EVENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "body": {"type": "string"},
        "choices": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": ["A", "B", "C"]},
                    "label": {"type": "string"},
                    "do_nothing": {"type": "boolean"},  # M10b (23.2): no effects, said so
                    "effects": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "target": {"type": "string"},
                                "value": {"type": "number"},
                                # modifier only (M10b, 23.2)
                                "stat": {"type": "string"},
                                "months": {"type": "integer"},
                            },
                            "required": ["type", "target", "value"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["key", "label", "effects"],
                "additionalProperties": False,
            },
        },
        "storyline_summary": {"type": "string"},
    },
    "required": ["title", "body", "choices", "storyline_summary"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class Usage:
    model: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class Completion:
    """What an adapter returned: a parsed draft (dict) or text, or None with an error."""

    content: dict[str, Any] | str | None
    usage: Usage | None = None
    latency_ms: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class EventPrompt:
    """One event to write. `fallback` is the template's own draft in the same JSON shape:
    the template and mock adapters return it, and it is what the player gets if the LLM's
    draft is rejected twice."""

    event_id: int
    kind: ModelKind
    system: str
    user: str
    fallback: dict[str, Any]
    retry_note: str | None = None


@dataclass(frozen=True, slots=True)
class TextPrompt:
    kind: TextKind
    system: str
    user: str
    fallback: str


@dataclass
class CallRecord:
    """One adapter call, for llm_call_log and the meter."""

    purpose: str
    model: str
    prompt_hash: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_cents: float = 0.0
    latency_ms: int = 0
    outcome: str = "ok"  # ok, rejected, error, template, budget
    prompt: str | None = None  # only with TST_LLM_DEBUG=1
    response: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class LLMAdapter(Protocol):
    name: str  # "claude", "template" or "mock"

    def generate_event(self, prompt: EventPrompt) -> Completion: ...

    def generate_text(self, prompt: TextPrompt) -> Completion: ...
