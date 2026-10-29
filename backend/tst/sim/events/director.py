"""The event director (docs/formulas.md 16.1, 16.6; ADR-0005): phase 12 decides how many
events next month brings, which templates, about whom, and how severe. Stream `events`, key
(turn,). Draw order: the count; one uniform draw per pick; then one tone draw per queued
event in queue order (follow-ups, storyline steps, then picks).

Follow-ups and due storyline steps are queued first and always arrive; the drawn count
fills whatever slots remain.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from tst.sim.data_models import Balance, GameData
from tst.sim.events.data import NO_STAFF_CATEGORIES, TRIGGERS, EventTemplate, Severity
from tst.sim.events.formulas import candidate_weight, cash_base_cents, severity_for
from tst.sim.events.models import EventRequest, GameEvent, QueuedEvent, Storyline, Tone
from tst.sim.events.render import placeholder_names, render
from tst.sim.events.triggers import TriggerHit, triggers
from tst.sim.money import Cents
from tst.sim.org.rules import org_view
from tst.sim.rivals.models import RivalMove
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_event, with_queued, with_storyline

BP = 10_000  # tunable-exempt: basis-point scale


@dataclass(frozen=True, slots=True)
class Targets:
    """What one event is about (from a trigger hit, a storyline or a follow-up)."""

    person_ids: tuple[int, ...] = ()
    unit_id: int | None = None
    product_id: int | None = None
    segment: str | None = None
    rival_id: int | None = None
    months: int | None = None


@dataclass(frozen=True, slots=True)
class Candidate:
    template: EventTemplate
    hit: TriggerHit
    targets: Targets
    severity: Severity
    weight: float


def main_product(state: GameState, company_id: int) -> int | None:
    """The product an event names when its trigger names none: the launched product with
    the most customers, else any product not retired, by id."""
    products = [p for p in state.company_products(company_id) if p.status != "retired"]
    if not products:
        return None

    def customers(pid: int) -> float:
        return sum(s.customers for s in state.segments_of(pid))

    launched = [p for p in products if p.launched_turn is not None]
    pool = launched or products
    return max(pool, key=lambda p: (customers(p.id), -p.id)).id


def main_segment(state: GameState, product_id: int | None) -> str | None:
    if product_id is None:
        return None
    segs = state.segments_of(product_id)
    return max(segs, key=lambda s: s.customers).segment if segs else None


def has_board(state: GameState, company_id: int) -> bool:
    return any(s.confidence is not None for s in state.board(company_id))


def resolve(state: GameState, template: EventTemplate, base: Targets) -> Targets | None:
    """Fill in what the template names and the trigger did not; None if it cannot be
    named (no product, no second person, no rival, no runway)."""
    needs = template.needs()
    cid = state.player.id
    product_id = base.product_id
    if product_id is None and "product" in needs:
        product_id = main_product(state, cid)
        if product_id is None:
            return None
    segment = base.segment
    if segment is None and "segment" in needs:
        segment = main_segment(state, product_id)
        if segment is None:
            return None
    unit_id = base.unit_id
    if unit_id is None and base.person_ids and "unit" in needs:
        unit_id = org_view(state, cid).unit_of.get(base.person_ids[0])
    if "other" in needs and len(base.person_ids) < 2:
        return None
    if "person" in needs and not base.person_ids:
        return None
    if "pair" in needs and len(base.person_ids) < 2 and state.founder_of(cid) is None:
        return None
    if "rival" in needs and base.rival_id is None:
        return None
    if "months" in needs and base.months is None:
        return None
    return replace(base, product_id=product_id, segment=segment, unit_id=unit_id)


def eligible_targets(state: GameState, event: GameEvent) -> tuple[str, ...]:
    """The request's eligible list (16.3): the trigger's people and pair, its unit, the
    company, the founder, its product, and the board if it has voting directors."""
    cid = event.company_id
    founder = state.founder_of(cid)
    out = [f"person:{p}" for p in event.person_ids]
    if len(event.person_ids) >= 2:  # tunable-exempt: a pair
        a, b = sorted(event.person_ids[:2])
        out.append(f"pair:{a}-{b}")
    elif event.person_ids and founder is not None:
        a, b = sorted((founder.id, event.person_ids[0]))
        out.append(f"pair:{a}-{b}")
    if event.unit_id is not None:
        out.append(f"unit:{event.unit_id}")
    out.append(f"company:{cid}")
    if founder is not None:
        out.append(f"founder:{founder.id}")
    if event.product_id is not None:
        out.append(f"product:{event.product_id}")
    if has_board(state, cid):
        out.append("board")
    return tuple(out)


def _recent(state: GameState, next_month: int, turns: int) -> list[GameEvent]:
    return [
        e for e in state.events if e.company_id == state.player.id and e.turn > next_month - turns
    ]


def candidates(
    state: GameState, hits: list[TriggerHit], balance: Balance, data: GameData
) -> list[Candidate]:
    """Every (template, hit) with its severity and 16.1 weight, in template-file order, then
    hit order. Zero weights are kept out."""
    ev = balance.events
    cid = state.player.id
    next_month = state.turn + 1
    no_staff = not any(
        e.person_id != (state.founder_of(cid).id if state.founder_of(cid) else None)  # type: ignore[union-attr]
        for e in state.staff(cid)
    )
    recent_templates = {
        e.template_id for e in _recent(state, next_month, ev.template_cooldown_turns)
    }
    recent_people = {
        p for e in _recent(state, next_month, ev.person_cooldown_turns) for p in e.person_ids
    }
    last_month = {e.category for e in state.events if e.company_id == cid and e.turn == state.turn}
    critical_ok = not any(
        e.severity == "critical" for e in _recent(state, next_month, ev.critical_gap_turns)
    )
    active = [s for s in state.storylines if s.company_id == cid and s.status == "active"]
    out: list[Candidate] = []
    for template in data.event_templates:
        if template.trigger not in TRIGGERS:
            continue
        if no_staff and template.category not in NO_STAFF_CATEGORIES:
            continue
        story = template.storyline
        if story is not None and (
            len(active) >= ev.max_storylines or any(s.key == story.key for s in active)
        ):
            continue
        for hit in hits:
            if hit.trigger != template.trigger:
                continue
            severity = severity_for(
                hit.strength,
                template.severities,
                critical_ok=hit.critical_ok and critical_ok,
                events=ev,
            )
            if severity is None:
                continue
            targets = resolve(
                state,
                template,
                Targets(
                    hit.person_ids,
                    hit.unit_id,
                    hit.product_id,
                    hit.segment,
                    hit.rival_id,
                    hit.months,
                ),
            )
            if targets is None:
                continue
            blocked = template.id in recent_templates or bool(set(hit.person_ids) & recent_people)
            weight = candidate_weight(
                template.weight,
                hit.strength,
                category_used_last_month=template.category in last_month,
                blocked=blocked,
                events=ev,
            )
            if weight > 0:
                out.append(Candidate(template, hit, targets, severity, weight))
    return out


def draw_count(gen: np.random.Generator, balance: Balance) -> int:
    u = float(gen.random())
    total = 0.0
    for n, w in enumerate(balance.events.count_weights):
        total += w
        if u < total:
            return n
    return len(balance.events.count_weights) - 1


def pick(gen: np.random.Generator, pool: list[Candidate], slots: int) -> list[Candidate]:
    """Draw without replacement by weight; a pick removes its template, anyone it names,
    other starts of its storyline and, if critical, every other critical candidate."""
    chosen: list[Candidate] = []
    for _ in range(slots):
        total = sum(c.weight for c in pool)
        if total <= 0:
            break
        u = float(gen.random()) * total
        acc = 0.0
        choice = pool[-1]
        for c in pool:
            acc += c.weight
            if u < acc:
                choice = c
                break
        chosen.append(choice)
        story = choice.template.storyline
        people = set(choice.hit.person_ids)
        pool = [
            c
            for c in pool
            if c.template.id != choice.template.id
            and not (people & set(c.hit.person_ids))
            and not (story and c.template.storyline and c.template.storyline.key == story.key)
            and not (choice.severity == "critical" and c.severity == "critical")
        ]
    return chosen


def _forced_severity(template: EventTemplate) -> Severity:
    usable = [s for s in template.severities if s != "critical"]
    return usable[-1] if usable else template.severities[0]


def direct(
    state: GameState,
    start: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    cash: Cents,
    revenue: Cents,
    rival_moves: tuple[RivalMove, ...],
) -> tuple[GameState, tuple[EventRequest, ...]]:
    """Phase 12: next month's events for the player (16.1), as pending GameEvents."""
    if state.ended or not data.event_templates:
        return state, ()
    ev = balance.events
    cid = state.player.id
    next_month = state.turn + 1
    staff_ids = {e.person_id for e in state.staff(cid)}
    # Storylines end when their people leave (16.6).
    for story in state.storylines:
        if story.status == "active" and any(p not in staff_ids for p in story.person_ids):
            state = with_storyline(state, replace(story, status="ended", ended_turn=state.turn))

    queue: list[
        tuple[EventTemplate, Targets, Severity, float, str, Storyline | None, QueuedEvent | None]
    ] = []
    for q in state.queued:
        if q.company_id == cid and not q.done and q.due_turn <= next_month:
            template = data.event_template(q.template_id)
            queue.append(
                (
                    template,
                    Targets(q.person_ids, q.unit_id, q.product_id, q.segment, q.rival_id),
                    _forced_severity(template),
                    1.0,
                    "follow_up",
                    None,
                    q,
                )
            )
    for story in state.storylines:
        if (
            story.company_id == cid
            and story.status == "active"
            and story.next_template
            and story.next_turn is not None
            and story.next_turn <= next_month
        ):
            template = data.event_template(story.next_template)
            queue.append(
                (
                    template,
                    Targets(
                        story.person_ids,
                        story.unit_id,
                        story.product_id,
                        story.segment,
                        story.rival_id,
                    ),
                    _forced_severity(template),
                    1.0,
                    "storyline",
                    story,
                    None,
                )
            )

    gen = rng.stream(state.turn, "events")
    count = draw_count(gen, balance)
    pool = candidates(
        state, triggers(state, start, balance, data, cash, rival_moves), balance, data
    )
    for c in pick(gen, pool, max(0, count - len(queue))):
        queue.append((c.template, c.targets, c.severity, c.hit.strength, c.hit.trigger, None, None))

    base = cash_base_cents(cash, revenue, ev)
    requests: list[EventRequest] = []
    for template, targets, severity, strength, trigger, thread, queued in queue:
        tone: Tone = "light" if int(gen.integers(0, BP)) < ev.light_tone_chance_bp else "grounded"
        event_id, ids = state.next_ids.take("event")
        state = replace(state, next_ids=ids)
        names = placeholder_names(
            state,
            data,
            cid,
            person_ids=targets.person_ids,
            unit_id=targets.unit_id,
            product_id=targets.product_id,
            segment=targets.segment,
            rival_id=targets.rival_id,
            months=targets.months,
        )
        storyline_id = None
        spec = template.storyline
        if spec is not None and thread is None:  # step 1 opens a storyline
            storyline_id, ids = state.next_ids.take("storyline")
            state = replace(state, next_ids=ids)
            thread = Storyline(
                id=storyline_id,
                company_id=cid,
                key=spec.key,
                title=render(spec.title or spec.key, names),
                step=spec.step,
                started_turn=next_month,
                summary=render(spec.summary, names),
                person_ids=targets.person_ids,
                product_id=targets.product_id,
                rival_id=targets.rival_id,
                unit_id=targets.unit_id,
                segment=targets.segment,
            )
        if spec is not None and thread is not None:
            storyline_id = thread.id
            last = spec.next_template is None
            state = with_storyline(
                state,
                replace(
                    thread,
                    step=spec.step,
                    summary=render(spec.summary, names),
                    next_turn=None if last else next_month + (spec.next_after_turns or 0),
                    next_template=spec.next_template,
                ),
            )
        if queued is not None:
            state = with_queued(state, replace(queued, done=True))
        event = GameEvent(
            id=event_id,
            company_id=cid,
            turn=next_month,
            template_id=template.id,
            category=template.category,
            severity=severity,
            trigger=trigger,
            strength=strength,
            person_ids=targets.person_ids,
            unit_id=targets.unit_id,
            product_id=targets.product_id,
            segment=targets.segment,
            rival_id=targets.rival_id,
            months=targets.months,
            cash_base_cents=base,
            tone=tone,
            storyline_id=storyline_id,
        )
        state = with_event(state, event)
        requests.append(
            EventRequest(
                event_id=event_id,
                company_id=cid,
                turn=next_month,
                template_id=template.id,
                severity=severity,
                tone=tone,
                targets=eligible_targets(state, event),
                storyline_id=storyline_id,
            )
        )
    return state, tuple(requests)
