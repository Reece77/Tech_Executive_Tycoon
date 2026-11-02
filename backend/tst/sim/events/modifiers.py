"""Event modifiers (docs/formulas.md 23.2, M10b): a choice's lasting percent change to one stat
of a product, unit, person, the company or the founder. A modifier starts in the month it is
chosen, applies every month for its months, then expires. Several on the same stat multiply.

The engine reads them through the factors below: a product's team (brand target, quality cap,
builder output, seller capacity, awareness, churn), a person's morale target and the
founder's monthly energy.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import EventsBalance
from tst.sim.events.data import MODIFIER_STATS, Severity
from tst.sim.events.models import Effect, Modifier
from tst.sim.state import GameState, with_modifier

COMPANY, PRODUCT, UNIT, PERSON, FOUNDER = "company", "product", "unit", "person", "founder"


def _kind_id(target: str) -> tuple[str, int | None]:
    kind, _, rest = target.partition(":")
    return kind, int(rest) if rest.isdigit() else None


def running(state: GameState, company_id: int) -> tuple[Modifier, ...]:
    """The company's modifiers that apply this month."""
    return tuple(m for m in state.modifiers if m.company_id == company_id and m.active(state.turn))


def _factor(state: GameState, company_id: int, stat: str, targets: set[tuple[str, int]]) -> float:
    if not state.modifiers:  # the common case: no event has started one
        return 1.0
    out = 1.0
    for m in state.modifiers:
        if m.company_id != company_id or m.stat != stat or not m.active(state.turn):
            continue
        kind, ident = _kind_id(m.target)
        if (kind, ident) in targets:
            out *= m.factor
    return out


def product_factor(state: GameState, company_id: int, product_id: int, stat: str) -> float:
    """A product stat: modifiers on the product and on the whole company."""
    return _factor(state, company_id, stat, {(PRODUCT, product_id), (COMPANY, company_id)})


def unit_factor(state: GameState, company_id: int, unit_id: int | None, stat: str) -> float:
    """A stat of the people in one unit (not the company's: product_factor covers that)."""
    if unit_id is None:
        return 1.0
    return _factor(state, company_id, stat, {(UNIT, unit_id)})


def person_factor(
    state: GameState, company_id: int, person_id: int, unit_id: int | None, stat: str
) -> float:
    """A person stat (morale target): modifiers on the person, their unit and the company."""
    targets = {(PERSON, person_id), (COMPANY, company_id)}
    if unit_id is not None:
        targets.add((UNIT, unit_id))
    return _factor(state, company_id, stat, targets)


def founder_factor(state: GameState, company_id: int, founder_id: int) -> float:
    return _factor(state, company_id, "founder_energy", {(FOUNDER, founder_id)})


def clamp_modifier(
    value_pct: float, months: int, severity: Severity, events: EventsBalance
) -> tuple[float, int]:
    """Value and months held to the severity's caps (23.2): +-5% for 6 months (minor), +-10%
    for 12 (major), +-20% for 12 (critical)."""
    cap = events.cap("modifier", severity)
    return max(-cap, min(cap, value_pct)), max(1, min(events.max_months(severity), months))


def start(
    state: GameState,
    company_id: int,
    event_id: int | None,
    effect: Effect,
    severity: Severity,
    events: EventsBalance,
) -> GameState:
    """A chosen modifier effect starts this month, its value and months clamped again (the
    stored choice was validated already; this keeps a hand-edited save inside the caps)."""
    kind, ident = _kind_id(effect.target)
    if effect.stat not in MODIFIER_STATS or ident is None:
        return state
    if kind not in {PERSON if w == "other" else w for w in MODIFIER_STATS[effect.stat]}:
        return state
    value, months = clamp_modifier(effect.value, effect.months, severity, events)
    if value == 0:
        return state
    modifier_id, ids = state.next_ids.take("modifier")
    state = replace(state, next_ids=ids)
    return with_modifier(
        state,
        Modifier(
            id=modifier_id,
            company_id=company_id,
            event_id=event_id,
            target=effect.target,
            stat=effect.stat,
            value_pct=value,
            start_turn=state.turn,
            end_turn=state.turn + months,
        ),
    )


def expire(state: GameState) -> tuple[GameState, tuple[Modifier, ...]]:
    """At month end: modifiers whose last month was this one leave the state (their rows
    stay in the save for history). Returns the state and the expired modifiers."""
    done = tuple(m for m in state.modifiers if m.end_turn <= state.turn + 1)
    if not done:
        return state, ()
    gone = {m.id for m in done}
    return replace(state, modifiers=tuple(m for m in state.modifiers if m.id not in gone)), done
