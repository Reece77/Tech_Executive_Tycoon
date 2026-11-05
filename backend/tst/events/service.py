"""The event service (docs/formulas.md 16.5; ADR-0005): after a turn commits, each pending
event gets its words and validated choices, from the LLM if the budget allows, else from its
template; a draft rejected twice also falls back to the template. Read-only texts (16.8) are
written the same way. Nothing here touches the turn's RNG or the clock-free sim; the stored
results are what replay copies, so replay never calls an adapter.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from tst.events.context import Kpis, build_prompt, text_prompt
from tst.events.drafts import template_draft
from tst.events.validator import Rejection, ValidatedEvent, validate_event
from tst.llm.base import CallRecord, Completion, EventPrompt, LLMAdapter, TextPrompt
from tst.llm.settings import LLMSettings
from tst.sim.data_models import Balance, GameData
from tst.sim.events.director import eligible_targets
from tst.sim.events.models import GameEvent
from tst.sim.events.render import full_name
from tst.sim.state import GameState, with_event, with_storyline

log = logging.getLogger(__name__)

RETRY = (
    "Your previous draft was rejected ({reason}). Write it again: two or three choices, "
    "only the allowed effects, only the eligible targets, values within the caps."
)


@dataclass
class Writer:
    """One batch of writing: the adapter, the prices, a budget check and what was spent."""

    adapter: LLMAdapter
    settings: LLMSettings
    budget_left: Callable[[], float]  # cents left this calendar month
    debug: bool = False
    records: list[CallRecord] = field(default_factory=list)
    spent_cents: float = 0.0
    claude_events: int = 0
    rejected: int = 0
    event_cents: float = 0.0

    @property
    def live(self) -> bool:
        """An adapter that calls a model (Claude, or the mock standing in for it)."""
        return self.adapter.name != "template"

    def can_spend(self) -> bool:
        return self.budget_left() - self.spent_cents > 0

    def record(self, purpose: str, prompt: str, completion: Completion, outcome: str) -> float:
        usage = completion.usage
        cost = (
            self.settings.cost_cents(usage.model, usage.input_tokens, usage.output_tokens)
            if usage
            else 0.0
        )
        self.spent_cents += cost
        self.records.append(
            CallRecord(
                purpose=purpose,
                model=usage.model if usage else self.adapter.name,
                prompt_hash=hashlib.sha256(prompt.encode()).hexdigest()[:16],
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                cost_cents=cost,
                latency_ms=completion.latency_ms,
                outcome=outcome,
                prompt=prompt if self.debug else None,
                response=str(completion.content) if self.debug else None,
            )
        )
        return cost


def write_event(
    state: GameState,
    event: GameEvent,
    kpis: Kpis,
    writer: Writer,
    balance: Balance,
    data: GameData,
) -> GameState:
    """Give one pending event its words and choices; status becomes "open"."""
    template = data.event_template(event.template_id)
    targets = eligible_targets(state, event)
    fallback = template_draft(state, event, template, balance, data)

    def check(draft: object) -> ValidatedEvent | Rejection:
        return validate_event(
            draft,
            template=template,
            severity=event.severity,
            targets=targets,
            cash_base_cents=event.cash_base_cents,
            events=balance.events,
        )

    result: ValidatedEvent | Rejection = Rejection("not written")
    source = "template"
    story = event.storyline_id is not None and template.trigger == "storyline"
    purpose = "story" if story else "event"
    # M10: a lender event's choices are the 20.3 terms, so its words come from the template.
    engine_terms = template.category == "lender"
    if writer.live and writer.can_spend() and not engine_terms:
        system, user = build_prompt(state, event, template, targets, kpis, balance, data)
        prompt = EventPrompt(event.id, "story" if story else "events", system, user, fallback)
        for attempt in range(2):  # tunable-exempt: one retry (ADR-0005 section 3)
            completion = writer.adapter.generate_event(prompt)
            result = (
                check(completion.content)
                if completion.content is not None
                else Rejection(completion.error or "no draft")
            )
            outcome = "ok" if isinstance(result, ValidatedEvent) else "rejected"
            cost = writer.record(purpose, system + "\n" + user, completion, outcome)
            writer.event_cents += cost
            if isinstance(result, ValidatedEvent):
                source = writer.adapter.name
                writer.claude_events += 1
                break
            log.info(
                "Event %s draft rejected (%s), attempt %d", event.id, result.reason, attempt + 1
            )
            if not writer.can_spend():
                break
            prompt = replace(prompt, retry_note=RETRY.format(reason=result.reason))
        else:
            writer.rejected += 1
    elif writer.live and not engine_terms:
        log.info("LLM budget reached: event %s from its template", event.id)
        writer.records.append(CallRecord(purpose, "template", "", outcome="budget"))
    if not isinstance(result, ValidatedEvent):
        result = check(fallback)
        source = "template"
        if not isinstance(result, ValidatedEvent):  # templates are checked at load
            raise RuntimeError(f"template {template.id} failed validation: {result.reason}")
    elif template.category in ("public", "press"):  # M13, M14b: words only from the LLM
        # M13 (25): the LLM may write a public event's words; its choices are the engine's.
        fixed = check(fallback)
        if not isinstance(fixed, ValidatedEvent):
            raise RuntimeError(f"template {template.id} failed validation: {fixed.reason}")
        result = replace(result, choices=fixed.choices)
    state = with_event(
        state,
        replace(
            event,
            status="open",
            title=result.title,
            body=result.body,
            choices=result.choices,
            source=source,
        ),
    )
    if event.storyline_id is not None and result.summary and source != "template":
        thread = state.storyline(event.storyline_id)
        if thread is not None:
            state = with_storyline(state, replace(thread, summary=result.summary))
    return state


def fallback_text(
    state: GameState, kind: str, turn: int, ref_id: int | None
) -> tuple[str, list[str]]:
    """(template text, facts) for a read-only text (16.8)."""
    company = state.player
    if kind == "headlines":
        moves = [m for m in state.rival_moves if m.turn == turn and m.detail]
        lines = [m.detail for m in moves[:3]]  # news details already name the rival
        facts = lines or [f"A quiet month for software companies; {company.name} kept working."]
        text = "\n".join(
            f"{line[0].upper()}{line[1:]}"
            for line in (lines or ["Quiet month in enterprise software"])
        )
        return text, facts
    if kind == "minutes":
        lines = [f"The board of {company.name} met for the quarter."]
        return (
            f"The board of {company.name} met for the quarter, reviewed cash and revenue against "
            "plan, and asked for an update on hiring and the product roadmap before the next "
            "meeting.",
            lines,
        )
    person = (
        state.person(ref_id)
        if ref_id is not None and any(p.id == ref_id for p in state.people)
        else None
    )
    name = full_name(person) if person else "They"
    morale = state.person_state(ref_id).morale if ref_id is not None else None
    low = morale is not None and morale < 40  # tunable-exempt: an unhappy leaver's line
    quote = (
        "I stopped feeling that my work mattered here."
        if low
        else "It was a hard decision. I learned a lot here."
    )
    facts = [f"{name} has resigned from {company.name}."]
    if morale is not None:
        facts.append(f"{name}'s morale was {round(morale)} out of 100.")
    return f'"{quote}" — {name}', facts


def write_text(
    state: GameState,
    kind: str,
    turn: int,
    ref_id: int | None,
    writer: Writer,
    given: tuple[str, list[str]] | None = None,
) -> tuple[str, str]:
    """(text, source) for one read-only text. `given` is (template text, facts) when the turn
    already wrote it (an executive's report, 24.3)."""
    fallback, facts = given or fallback_text(state, kind, turn, ref_id)
    if not writer.live or not writer.can_spend():
        return fallback, "template"
    system, user = text_prompt(kind, facts, state.player.name)
    completion = writer.adapter.generate_text(TextPrompt(kind, system, user, fallback))  # type: ignore[arg-type]
    text = completion.content if isinstance(completion.content, str) else None
    ok = bool(text and text.strip())
    writer.record(kind, system + "\n" + user, completion, "ok" if ok else "rejected")
    return (text.strip(), writer.adapter.name) if ok and text else (fallback, "template")
