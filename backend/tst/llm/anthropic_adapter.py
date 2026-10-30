"""The Claude adapter (ADR-0005): one Messages API call per event or text, with the event
JSON constrained by a schema (`output_config.format`). Model ids come from settings: a small
model for events, headlines and minutes, a larger one for storyline steps. Never used in
tests (they use MockLLMAdapter); a missing key or any API error is a failed completion, which
the service answers with the template.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import anthropic

from tst.llm.base import EVENT_SCHEMA, Completion, EventPrompt, TextPrompt, Usage

log = logging.getLogger(__name__)

EVENT_MAX_TOKENS = 4000  # tunable-exempt: room for thinking plus a 180-word event
TEXT_MAX_TOKENS = 1500  # tunable-exempt: a few lines of text
TIMEOUT_SECONDS = 60.0  # tunable-exempt: one call; the player is waiting on Continue
EFFORT = "low"  # flavour text, not reasoning (ADR-0005 section 7)


class AnthropicAdapter:
    name = "claude"

    def __init__(self, api_key: str, model_events: str, model_story: str) -> None:
        self.client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=1)
        self.model_events = model_events
        self.model_story = model_story

    def _call(
        self, model: str, system: str, user: str, max_tokens: int, schema: bool
    ) -> Completion:
        started = time.monotonic()
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": EFFORT},
        }
        if schema:
            params["output_config"]["format"] = {"type": "json_schema", "schema": EVENT_SCHEMA}
        try:
            response = self.client.messages.create(**params)
        except anthropic.APIConnectionError as exc:
            return Completion(None, error=f"connection: {exc}")
        except anthropic.RateLimitError as exc:
            return Completion(None, error=f"rate limited: {exc.message}")
        except anthropic.APIStatusError as exc:
            return Completion(None, error=f"api {exc.status_code}: {exc.message}")
        latency = int((time.monotonic() - started) * 1000)
        usage = Usage(response.model, response.usage.input_tokens, response.usage.output_tokens)
        if response.stop_reason in ("refusal", "max_tokens"):
            return Completion(None, usage, latency, f"stopped: {response.stop_reason}")
        text = next((b.text for b in response.content if b.type == "text"), "")
        if not schema:
            return Completion(text.strip(), usage, latency)
        try:
            return Completion(json.loads(text), usage, latency)
        except ValueError as exc:
            return Completion(None, usage, latency, f"invalid JSON: {exc}")

    def generate_event(self, prompt: EventPrompt) -> Completion:
        model = self.model_story if prompt.kind == "story" else self.model_events
        user = prompt.user if prompt.retry_note is None else f"{prompt.user}\n\n{prompt.retry_note}"
        return self._call(model, prompt.system, user, EVENT_MAX_TOKENS, schema=True)

    def generate_text(self, prompt: TextPrompt) -> Completion:
        return self._call(self.model_events, prompt.system, prompt.user, TEXT_MAX_TOKENS, False)
