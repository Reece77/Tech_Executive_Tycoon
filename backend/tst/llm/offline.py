"""The two adapters that never call a network (ADR-0005 section 1).

`TemplateAdapter` is offline play: it returns the template's own draft and text.
`MockLLMAdapter` is used by every test: deterministic, it returns the template draft with a
marked title (so tests can tell its events from templates), or scripted drafts in order when
given some, and reports token counts so the budget meter can be exercised without a network.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Sequence
from typing import Any

from tst.llm.base import Completion, EventPrompt, TextPrompt, Usage

MOCK_MODEL = "mock"
CHARS_PER_TOKEN = 4  # tunable-exempt: rough token estimate for the mock's usage


class TemplateAdapter:
    name = "template"

    def generate_event(self, prompt: EventPrompt) -> Completion:
        return Completion(copy.deepcopy(prompt.fallback))

    def generate_text(self, prompt: TextPrompt) -> Completion:
        return Completion(prompt.fallback)


class MockLLMAdapter:
    """Deterministic stand-in for Claude. `script` drafts (or a function of the prompt) are
    returned in order; after them, or without them, the template draft with "[mock]" ahead of
    its title."""

    name = "mock"

    def __init__(
        self,
        script: Sequence[dict[str, Any] | None]
        | Callable[[EventPrompt], dict[str, Any] | None] = (),
        model: str = MOCK_MODEL,
    ) -> None:
        self.script = script
        self.model = model
        self.calls: list[EventPrompt | TextPrompt] = []

    def _usage(self, system: str, user: str, out: str) -> Usage:
        return Usage(
            self.model,
            (len(system) + len(user)) // CHARS_PER_TOKEN,
            max(1, len(out) // CHARS_PER_TOKEN),
        )

    def generate_event(self, prompt: EventPrompt) -> Completion:
        index = sum(1 for c in self.calls if isinstance(c, EventPrompt))
        self.calls.append(prompt)
        draft: dict[str, Any] | None
        if callable(self.script):
            draft = self.script(prompt)
        elif index < len(self.script):
            draft = self.script[index]
        else:
            draft = copy.deepcopy(prompt.fallback)
            draft["title"] = f"[mock] {draft['title']}"
        return Completion(draft, self._usage(prompt.system, prompt.user, str(draft)))

    def generate_text(self, prompt: TextPrompt) -> Completion:
        self.calls.append(prompt)
        text = (
            mock_coo_answer(prompt.user)
            if prompt.kind == "coo"
            else f"[mock] {prompt.fallback}"
            if prompt.kind == "explain"  # M25: the template explanation, marked
            else prompt.fallback
        )
        return Completion(text, self._usage(prompt.system, prompt.user, text))


def mock_coo_answer(user: str) -> str:
    """A deterministic COO answer (M7b): the first briefing line, marked as the mock's."""
    lines = [ln[2:] for ln in user.splitlines() if ln.startswith("- ")]
    first = lines[0] if lines else "Nothing urgent."
    return f"[mock] Looking at the numbers you gave me, the first thing I would watch: {first}"
