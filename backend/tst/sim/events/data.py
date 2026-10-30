"""Event template data (`data/events/*.yaml`, docs/formulas.md 16.4), validated at load.

Templates are the offline mode and the LLM fallback, so the checks here make sure every
trigger has a template the director can always use, every placeholder can be filled from
the trigger's targets, and every effect is in the catalog within its caps (16.3).
"""

from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

type Severity = Literal["minor", "major", "critical"]
SEVERITIES: Final = ("minor", "major", "critical")

CATEGORIES: Final = (
    "personnel",
    "market",
    "operations",
    "finance",
    "board",
    "rivals",
    "founder",  # M7a: the founder's own early days (16.1 "founder templates")
)
# Templates a company with no employees may draw (16.1: founder, market and finance).
NO_STAFF_CATEGORIES: Final = ("market", "finance", "founder")

# Triggers the director computes from state (16.2), in table order; `storyline` and
# `follow_up` templates are never drawn, only scheduled (16.3, 16.6).
TRIGGERS: Final = (
    "low_morale",
    "unhappy_unit",
    "underpaid",
    "star_performer",
    "team_clash",
    "team_bond",
    "office_politics",
    "tag_noticed",
    "anniversary",
    "product_launched",
    "product_slipping",
    "price_war",
    "rival_move",
    "poached",
    "customer_milestone",
    "runway_short",
    "funding_closed",
    "board_unhappy",
    "early_days",  # M7a: no live product yet
    "quiet_month",
)
SCHEDULED: Final = ("storyline", "follow_up")
CRITICAL_TRIGGERS: Final = ("runway_short",)  # 16.2: critical allowed below 3 months

EFFECT_TYPES: Final = (
    "morale_delta",
    "relationship_delta",
    "cash_delta",
    "brand_delta",
    "quality_delta",
    "customers_pct",
    "growth_boost",
    "reveal_tag",
    "energy_delta",
    "board_confidence",
    "salary_change",
    "resign",
    "follow_up",
)
VALUELESS: Final = ("reveal_tag", "resign", "follow_up")  # no size: they happen or not
NON_NEGATIVE: Final = ("growth_boost", "salary_change")  # 16.3: never a cut

# Template target words and the effects that may use each (16.3 "Target" column).
EFFECT_TARGETS: Final[dict[str, tuple[str, ...]]] = {
    "morale_delta": ("person", "other", "unit", "company"),
    "relationship_delta": ("pair",),
    "cash_delta": ("company",),
    "brand_delta": ("product",),
    "quality_delta": ("product",),
    "customers_pct": ("product",),
    "growth_boost": ("person", "other"),
    "reveal_tag": ("person", "other"),
    "energy_delta": ("founder",),
    "board_confidence": ("board",),
    "salary_change": ("person", "other"),
    "resign": ("person", "other"),
    "follow_up": ("",),
}

# What each trigger can name. Company, founder, product and board can always be asked for;
# the director skips a template when the company has no product or board to name.
ALWAYS: Final = frozenset({"company", "founder", "product", "board", "amount"})
_PERSON = frozenset({"person", "pair", "unit"})
TRIGGER_SUPPLIES: Final[dict[str, frozenset[str]]] = {
    "low_morale": _PERSON,
    "unhappy_unit": frozenset({"unit"}),
    "underpaid": _PERSON,
    "star_performer": _PERSON,
    "team_clash": _PERSON | {"other"},
    "team_bond": _PERSON | {"other"},
    "office_politics": _PERSON,
    "tag_noticed": _PERSON,
    "anniversary": _PERSON,
    "product_launched": frozenset({"segment"}),
    "product_slipping": frozenset({"segment"}),
    "price_war": frozenset({"segment", "rival"}),
    "rival_move": frozenset({"segment", "rival"}),
    "poached": frozenset({"rival"}),
    "customer_milestone": frozenset({"segment"}),
    "runway_short": frozenset({"months"}),
    "funding_closed": frozenset(),
    "board_unhappy": frozenset(),
    "early_days": frozenset(),  # names the product in development, if any
    "quiet_month": frozenset(),
}
PLACEHOLDER_RE: Final = re.compile(r"\{([a-z_]+)\}")
PLACEHOLDERS: Final = (
    "person",
    "other",
    "unit",
    "product",
    "segment",
    "rival",
    "amount",
    "months",
    "founder",
    "company",
)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EffectSpec(_Frozen):
    """One effect of a template choice. `share` is the fraction of the severity's cap
    (negative: a loss or a cost; a cash gain is a share of the smaller gain cap)."""

    type: str
    target: str = ""
    share: float = Field(default=0.0, ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def _check(self) -> EffectSpec:
        if self.type not in EFFECT_TYPES:
            raise ValueError(f"unknown effect {self.type!r}")
        if self.target not in EFFECT_TARGETS[self.type]:
            raise ValueError(
                f"{self.type} may target {list(EFFECT_TARGETS[self.type])}, not {self.target!r}"
            )
        if self.type in VALUELESS and self.share:
            raise ValueError(f"{self.type} takes no share")
        if self.type not in VALUELESS and not self.share:
            raise ValueError(f"{self.type} needs a non-zero share")
        if self.type in NON_NEGATIVE and self.share < 0:
            raise ValueError(f"{self.type} cannot be negative")
        return self


class ChoiceSpec(_Frozen):
    key: str = Field(pattern=r"^[ABC]$")
    label: str = Field(min_length=1, max_length=80)  # tunable-exempt: button text length
    effects: tuple[EffectSpec, ...] = Field(default=(), max_length=3)  # tunable-exempt: 16.3


class StorylineSpec(_Frozen):
    """A storyline step (16.6). Step 1 opens it (and names it); later steps are scheduled."""

    key: str = Field(min_length=1)
    step: int = Field(ge=1)
    title: str | None = None  # step 1 only
    next_after_turns: int | None = Field(default=None, ge=1)
    next_template: str | None = None
    summary: str = Field(min_length=1)


class EventTemplate(_Frozen):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    category: str
    trigger: str
    severities: tuple[Severity, ...] = Field(min_length=1)
    weight: float = Field(gt=0)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    choices: tuple[ChoiceSpec, ...] = Field(min_length=2, max_length=3)  # tunable-exempt: 16.3
    storyline: StorylineSpec | None = None
    follow_up: str | None = None

    @property
    def is_critical(self) -> bool:
        return "critical" in self.severities

    def texts(self) -> tuple[str, ...]:
        story = (self.storyline.summary, self.storyline.title or "") if self.storyline else ()
        return (self.title, self.body, *(c.label for c in self.choices), *story)

    def needs(self) -> frozenset[str]:
        """Everything the template names: placeholders and effect targets."""
        names = {m for t in self.texts() for m in PLACEHOLDER_RE.findall(t)}
        for choice in self.choices:
            for effect in choice.effects:
                if effect.target == "pair":
                    names |= {"pair", "person"}
                elif effect.target:
                    names.add(effect.target)
        return frozenset(names)

    @model_validator(mode="after")
    def _check(self) -> EventTemplate:
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category {self.category!r}")
        if self.trigger not in TRIGGERS + SCHEDULED:
            raise ValueError(f"unknown trigger {self.trigger!r}")
        keys = [c.key for c in self.choices]
        if keys != ["A", "B", "C"][: len(keys)]:
            raise ValueError(f"choices must be keyed A, B[, C] in order, got {keys}")
        unknown = sorted(
            {m for t in self.texts() for m in PLACEHOLDER_RE.findall(t)} - set(PLACEHOLDERS)
        )
        if unknown:
            raise ValueError(f"unknown placeholders {unknown}")
        types = {e.type for c in self.choices for e in c.effects}
        if "resign" in types and self.severities == ("minor",):
            raise ValueError("resign is for major and critical events only (16.3)")
        if "follow_up" in types and (not self.is_critical or not self.follow_up):
            raise ValueError("follow_up needs a critical template that names its follow_up")
        if self.follow_up and not self.is_critical:
            raise ValueError("only a critical template names a follow_up")
        if self.trigger in SCHEDULED and self.storyline is None and self.trigger == "storyline":
            raise ValueError("a storyline-triggered template needs a storyline step")
        return self


class EventTemplatesFile(_Frozen):
    templates: tuple[EventTemplate, ...]


def template_problems(templates: tuple[EventTemplate, ...]) -> list[str]:
    """Cross-template checks (16.4): ids unique; every trigger has a minor template and
    every critical trigger a critical one; placeholders and targets resolvable from the
    trigger; storyline steps and follow-ups point at scheduled templates."""
    problems: list[str] = []
    by_id: dict[str, EventTemplate] = {}
    for t in templates:
        if t.id in by_id:
            problems.append(f"duplicate event template id {t.id!r}")
        by_id[t.id] = t
    for trigger in TRIGGERS:
        drawn = [t for t in templates if t.trigger == trigger]
        if not any("minor" in t.severities for t in drawn):
            problems.append(f"trigger {trigger!r} has no minor template")
        if trigger in CRITICAL_TRIGGERS and not any(t.is_critical for t in drawn):
            problems.append(f"critical trigger {trigger!r} has no critical template")
    for t in templates:
        if t.is_critical and t.trigger not in CRITICAL_TRIGGERS:
            problems.append(f"{t.id}: only {list(CRITICAL_TRIGGERS)} may be critical (16.2)")
    # Scheduled templates inherit their origin's targets: walk each chain from its start.
    origin: dict[str, str] = {}
    for t in templates:
        if t.trigger in SCHEDULED:
            continue
        nxt = t.storyline.next_template if t.storyline else None
        chain = [nxt] if nxt else []
        if t.follow_up:
            chain.append(t.follow_up)
        for first in chain:
            seen: set[str] = set()
            current: str | None = first
            while current and current not in seen:
                seen.add(current)
                origin.setdefault(current, t.trigger)
                step = by_id.get(current)
                current = step.storyline.next_template if step and step.storyline else None
    for t in templates:
        trigger = origin.get(t.id, t.trigger) if t.trigger in SCHEDULED else t.trigger
        if t.trigger in SCHEDULED and t.id not in origin:
            problems.append(f"{t.id}: scheduled template that nothing schedules")
            continue
        missing = sorted(t.needs() - ALWAYS - TRIGGER_SUPPLIES.get(trigger, frozenset()))
        if missing:
            problems.append(f"{t.id}: trigger {trigger!r} cannot supply {missing}")
        if t.follow_up:
            follow = by_id.get(t.follow_up)
            if follow is None or follow.trigger != "follow_up":
                problems.append(f"{t.id}: follow_up {t.follow_up!r} is not a follow_up template")
        story = t.storyline
        if story is None:
            continue
        if (story.step == 1) != (t.trigger != "storyline"):
            problems.append(f"{t.id}: only step 1 of a storyline is drawn by a trigger")
        if story.step == 1 and not story.title:
            problems.append(f"{t.id}: step 1 of a storyline needs a title")
        if (story.next_template is None) != (story.next_after_turns is None):
            problems.append(f"{t.id}: next_template and next_after_turns go together")
        if story.next_template:
            following = by_id.get(story.next_template)
            if (
                following is None
                or following.storyline is None
                or following.storyline.key != story.key
                or following.storyline.step != story.step + 1
            ):
                problems.append(
                    f"{t.id}: next_template must be step {story.step + 1} of {story.key!r}"
                )
    return problems
