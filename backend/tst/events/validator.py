"""validate_event (ADR-0005 section 3, docs/formulas.md 16.3): the LLM's draft is untrusted
JSON. Unknown effects and targets outside the eligible list are dropped, values are clamped to
the severity's caps, the body and summary are cut to their word limits, and a draft without
two valid choices is rejected (the service retries once, then uses the template).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tst.sim.data_models import EventsBalance
from tst.sim.events.data import (
    EFFECT_TARGETS,
    EFFECT_TYPES,
    EXPLORATION_STEPS,
    FOUNDER_STEPS,
    GROUP_STEPS,
    MINING_STEPS,
    MODIFIER_STATS,
    PRESS_STEPS,
    PUBLIC_STEPS,
    REFINING_STEPS,
    VALUELESS,
    EventTemplate,
    Severity,
)
from tst.sim.events.formulas import clamp_effect
from tst.sim.events.models import Effect, EventChoice
from tst.sim.events.modifiers import clamp_modifier

CENTS_PER_DOLLAR = 100  # tunable-exempt: unit conversion
TITLE_CHARS = 120  # tunable-exempt: inbox title width
LABEL_CHARS = 80  # tunable-exempt: button text width
MIN_CHOICES, MAX_CHOICES, MAX_EFFECTS = 2, 3, 3  # tunable-exempt: 16.3
KEYS = ("A", "B", "C")
TARGET_KIND = {"person": "person", "other": "person", "pair": "pair", "unit": "unit"}


@dataclass(frozen=True, slots=True)
class ValidatedEvent:
    title: str
    body: str
    choices: tuple[EventChoice, ...]
    summary: str | None
    dropped: int  # effects dropped or values clamped, for the call log


@dataclass(frozen=True, slots=True)
class Rejection:
    reason: str


def allowed_effects(
    template: EventTemplate, severity: Severity, targets: tuple[str, ...]
) -> list[str]:
    """Effects this event may carry (16.3): the catalog, less resign unless the template
    allows it at major or critical, less follow_up unless critical with a follow-up, less any
    effect with no eligible target."""
    kinds = {t.partition(":")[0] for t in targets} | ({""} if severity == "critical" else set())
    template_types = {e.type for c in template.choices for e in c.effects}
    out = []
    for effect in EFFECT_TYPES:
        if effect == "resign" and (severity == "minor" or "resign" not in template_types):
            continue
        if effect == "follow_up" and (severity != "critical" or not template.follow_up):
            continue
        if effect == "modifier" and not template.modifier_stats():  # 23.2: template's list
            continue
        if effect == "retain" and (severity != "critical" or "retain" not in template_types):
            continue  # 23.3: only a crisis template's own counter-offer
        if effect == "press_step" and "press_step" not in template_types:
            continue  # M14b (29.1): only a press template's own tones
        if effect == "founder_step" and "founder_step" not in template_types:
            continue  # M24 (32): only a founder template's own answers
        if effect == "group_step" and "group_step" not in template_types:
            continue  # M16 (31.6): only a group template's own answers
        if effect == "exploration_step" and "exploration_step" not in template_types:
            continue  # M18 (34.3): only an exploration template's own answers
        if effect == "mining_step" and "mining_step" not in template_types:
            continue  # M19 (35.4): only a mining template's own answers
        if effect == "public_step" and "public_step" not in template_types:
            continue  # M13 (25): only a public template's own steps
        words = {TARGET_KIND.get(w, w) for w in EFFECT_TARGETS[effect]}
        if words & kinds:
            out.append(effect)
    return out


def _modifier(
    item: dict[str, Any],
    target: str,
    value: float,
    template: EventTemplate,
    severity: Severity,
    events: EventsBalance,
) -> Effect | None:
    """A modifier effect from the draft: its stat must be one the template's own modifiers
    use, for a target that stat accepts; value and months are clamped (23.2)."""
    stat, months = item.get("stat"), item.get("months")
    if not isinstance(stat, str) or stat not in template.modifier_stats():
        return None
    if isinstance(months, bool) or not isinstance(months, int):
        return None
    words = {TARGET_KIND.get(w, w) for w in MODIFIER_STATS[stat]}
    if (target.partition(":")[0] if target else "") not in words:
        return None
    value_pct, months = clamp_modifier(value, months, severity, events)
    return None if value_pct == 0 else Effect("modifier", target, value_pct, stat, months)


def _words(text: str, limit: int) -> str:
    words = text.split()
    return text.strip() if len(words) <= limit else " ".join(words[:limit]) + "…"


def validate_event(
    draft: Any,
    *,
    template: EventTemplate,
    severity: Severity,
    targets: tuple[str, ...],
    cash_base_cents: int,
    events: EventsBalance,
) -> ValidatedEvent | Rejection:
    if not isinstance(draft, dict):
        return Rejection("the draft is not a JSON object")
    title, body = draft.get("title"), draft.get("body")
    if not isinstance(title, str) or not title.strip():
        return Rejection("missing title")
    if not isinstance(body, str) or not body.strip():
        return Rejection("missing body")
    raw_choices = draft.get("choices")
    if not isinstance(raw_choices, list):
        return Rejection("choices must be a list")
    allowed = set(allowed_effects(template, severity, targets))
    eligible = set(targets) | ({""} if "follow_up" in allowed else set())
    dropped = 0
    choices: list[EventChoice] = []
    for raw in raw_choices[:MAX_CHOICES]:
        if not isinstance(raw, dict):
            dropped += 1
            continue
        label = raw.get("label")
        if not isinstance(label, str) or not label.strip():
            dropped += 1
            continue
        effects: list[Effect] = []
        raw_effects = raw.get("effects") if isinstance(raw.get("effects"), list) else []
        for item in raw_effects:  # type: ignore[union-attr]
            if len(effects) >= MAX_EFFECTS or not isinstance(item, dict):
                dropped += 1
                continue
            kind, target, value = item.get("type"), item.get("target", ""), item.get("value", 0)
            if kind not in allowed or not isinstance(target, str) or target not in eligible:
                dropped += 1
                continue
            words = {TARGET_KIND.get(w, w) for w in EFFECT_TARGETS[kind]}
            if (target.partition(":")[0] if target else "") not in words:
                dropped += 1
                continue
            if kind in (
                "public_step",
                "press_step",
                "founder_step",
                "group_step",
                "exploration_step",
                "refining_step",
                "mining_step",
            ):  # engine steps
                stat = item.get("stat")
                steps = {
                    "public_step": PUBLIC_STEPS,
                    "press_step": PRESS_STEPS,
                    "founder_step": FOUNDER_STEPS,
                    "group_step": GROUP_STEPS,
                    "exploration_step": EXPLORATION_STEPS,
                    "refining_step": REFINING_STEPS,
                    "mining_step": MINING_STEPS,
                }[kind]
                if stat not in steps:
                    dropped += 1
                    continue
                effects.append(Effect(kind, target, 0.0, str(stat)))
                continue
            if kind in VALUELESS:
                effects.append(Effect(kind, target, 0.0))
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                dropped += 1
                continue
            if kind == "modifier":  # M10b (23.2): a stat the template allows, months capped
                modifier = _modifier(item, target, float(value), template, severity, events)
                if modifier is None:
                    dropped += 1
                    continue
                if (modifier.value, modifier.months) != (float(value), item.get("months")):
                    dropped += 1
                effects.append(modifier)
                continue
            raw_value = float(value) * (CENTS_PER_DOLLAR if kind == "cash_delta" else 1)
            clamped = clamp_effect(kind, raw_value, severity, events, cash_base_cents)
            if clamped != raw_value:
                dropped += 1
            if clamped == 0:
                continue
            effects.append(Effect(kind, target, clamped))
        do_nothing = not effects and raw.get("do_nothing") is True  # 23.2: said as such
        choices.append(
            EventChoice(KEYS[len(choices)], label.strip()[:LABEL_CHARS], tuple(effects), do_nothing)
        )
    if len(choices) < MIN_CHOICES:
        return Rejection(f"needs {MIN_CHOICES} or {MAX_CHOICES} valid choices")
    summary = draft.get("storyline_summary")
    return ValidatedEvent(
        title=title.strip()[:TITLE_CHARS],
        body=_words(body, events.body_words),
        choices=tuple(choices),
        summary=_words(summary, events.summary_words)
        if isinstance(summary, str) and summary.strip()
        else None,
        dropped=dropped,
    )
