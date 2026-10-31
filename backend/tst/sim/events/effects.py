"""Applying an event's choice (docs/formulas.md 16.3; ADR-0005, ADR-0014): the engine
disposes. Every effect was validated and clamped when the event was written; here it is
clamped again against the stored severity and cash base, and anything whose target is gone
(someone left, a pair ended, a product retired) is skipped.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.events.formulas import clamp_effect
from tst.sim.events.models import EventChoice, GameEvent, QueuedEvent
from tst.sim.ledger import CASH, GENERAL_ADMIN, OTHER_INCOME, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.org.rules import org_view
from tst.sim.people.relationships import clamp_relationship, pair_key
from tst.sim.state import (
    GameState,
    with_employment,
    with_event,
    with_person,
    with_person_state,
    with_product,
    with_product_segment,
    with_queued,
    with_relationship,
    with_reveal,
    with_seat,
    with_storyline,
)

MORALE_MAX = 100.0  # tunable-exempt: morale scale 0-100
SCORE_MAX = 100.0  # tunable-exempt: brand and quality scale 0-100
PCT = 100.0  # tunable-exempt: percent
PERCENT = 100  # tunable-exempt: percent, as an integer for exact money


def parse_target(target: str) -> tuple[str, tuple[int, ...]]:
    """Split a target: "person:12" is ("person", (12,)), "pair:3-9" is ("pair", (3, 9)),
    "board" is ("board", ())."""
    kind, _, rest = target.partition(":")
    if not rest:
        return kind, ()
    try:
        return kind, tuple(int(x) for x in rest.split("-"))
    except ValueError:
        return kind, ()


def _employees(state: GameState, company_id: int) -> list[int]:
    founder = state.founder_of(company_id)
    return [
        e.person_id
        for e in sorted(state.staff(company_id), key=lambda e: e.person_id)
        if founder is None or e.person_id != founder.id
    ]


def _morale(state: GameState, person_ids: list[int], value: float) -> GameState:
    for pid in person_ids:
        ps = state.person_state(pid)
        if ps.morale is not None:
            new = max(0.0, min(MORALE_MAX, ps.morale + value))
            state = with_person_state(state, replace(ps, morale=new))
    return state


def energy_next_month(state: GameState, person_id: int) -> int:
    """The founder's energy change for next month from events answered this month."""
    total = 0.0
    for event in state.events:
        if event.resolved_turn != state.turn or event.chosen is None:
            continue
        choice = event.choice(event.chosen)
        for effect in choice.effects if choice else ():
            if effect.type == "energy_delta" and parse_target(effect.target)[1] == (person_id,):
                total += effect.value
    return round(total)


def apply_choice(
    state: GameState,
    event: GameEvent,
    key: str,
    balance: Balance,
    data: GameData,
    *,
    auto: bool,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Apply one choice of an open event and close it. An event whose words were never
    written (no choices) closes with nothing applied."""
    choice: EventChoice | None = event.choice(key)
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    cid = event.company_id
    staff = {e.person_id for e in state.staff(cid)}
    for effect in choice.effects if choice else ():
        kind, ids = parse_target(effect.target)
        value = clamp_effect(
            effect.type, effect.value, event.severity, balance.events, event.cash_base_cents
        )
        t = effect.type
        if t == "morale_delta":
            if kind == "person" and ids and ids[0] in staff:
                state = _morale(state, [ids[0]], value)
            elif kind == "unit" and ids:
                view = org_view(state, cid)
                founder = state.founder_of(cid)
                members = [
                    p for p in view.members.get(ids[0], ()) if founder is None or p != founder.id
                ]
                state = _morale(state, members, value)
            elif kind == "company":
                state = _morale(state, _employees(state, cid), value)
        elif (
            t == "relationship_delta" and kind == "pair" and len(ids) == 2
        ):  # tunable-exempt: a pair
            rel = state.relationship_map().get(pair_key(ids[0], ids[1]))
            if rel is not None:
                state = with_relationship(
                    state,
                    replace(
                        rel, value=clamp_relationship(rel.value + value, balance.relationships)
                    ),
                )
        elif t == "cash_delta" and kind == "company" and round(value):
            cents = round(value)
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=cid,
                    memo=f"Event: {event.title or event.template_id}",
                    debit=GENERAL_ADMIN if cents < 0 else CASH,
                    credit=CASH if cents < 0 else OTHER_INCOME,
                    amount=abs(cents),
                )
            )
        elif t in ("brand_delta", "quality_delta") and kind == "product" and ids:
            product = state.product(ids[0])
            if product is not None and product.company_id == cid and product.status != "retired":
                if t == "brand_delta":
                    product = replace(
                        product, brand=max(0.0, min(SCORE_MAX, product.brand + value))
                    )
                else:
                    product = replace(
                        product, quality=max(0.0, min(SCORE_MAX, product.quality + value))
                    )
                state = with_product(state, product)
        elif t == "customers_pct" and kind == "product" and ids:
            product = state.product(ids[0])
            if product is not None and product.company_id == cid:
                for seg in state.segments_of(product.id):
                    if event.segment is None or seg.segment == event.segment:
                        customers = max(0.0, seg.customers * (1 + value / PCT))
                        state = with_product_segment(state, replace(seg, customers=customers))
        elif t == "growth_boost" and kind in ("person", "founder") and ids and ids[0] in staff:
            person = state.person(ids[0])
            employment = state.employment_of(person.id)
            role = (
                data.role(employment.role) if employment and employment.role != "founder" else None
            )
            skill = role.primary[0] if role else max(person.skills.items, key=lambda kv: kv[1])[0]
            state = with_person(
                state,
                replace(
                    person, skills=person.skills.updated({skill: person.skills[skill] + value})
                ),
            )
        elif t == "reveal_tag" and kind == "person" and ids and ids[0] in staff:
            person = state.person(ids[0])
            reveal = state.reveal(cid, person.id)
            known = {tag for tag, _ in reveal.revealed_tags} if reveal else set()
            hidden = [tag for tag in person.tags if tag not in known]
            if reveal is not None and hidden:
                tag = hidden[0]
                state = with_reveal(
                    state, replace(reveal, revealed_tags=(*reveal.revealed_tags, (tag, state.turn)))
                )
                logs.append(
                    inbox_item(
                        state.turn,
                        cid,
                        "tag_revealed",
                        link_kind="person",
                        link_id=person.id,
                        name=f"{person.first_name} {person.last_name}",
                        reveal_text=next(x.reveal_text for x in data.tags if x.key == tag),
                    )
                )
        elif t == "board_confidence":
            for seat in state.board(cid):
                if seat.confidence is not None:
                    state = with_seat(
                        state,
                        replace(seat, confidence=max(0.0, min(SCORE_MAX, seat.confidence + value))),
                    )
        elif t == "salary_change" and kind == "person" and ids and ids[0] in staff:
            employment = state.employment_of(ids[0])
            if employment is not None and value > 0:
                # Exactly, rounded half-to-even once (ADR-0003; M8r, finding 6).
                salary = round(employment.salary_cents * (1 + exact(value) / PERCENT))
                state = with_employment(state, replace(employment, salary_cents=salary))
        elif t == "resign" and kind == "person" and ids and ids[0] in staff:
            employment = state.employment_of(ids[0])
            if employment is not None and employment.status == "active":
                person = state.person(ids[0])
                state = with_employment(
                    state,
                    replace(
                        employment, status="notice", end_turn=state.turn + 1, end_reason="resigned"
                    ),
                )
                logs.append(
                    inbox_item(
                        state.turn,
                        cid,
                        "resigned",
                        link_kind="person",
                        link_id=person.id,
                        name=f"{person.first_name} {person.last_name}",
                    )
                )
        elif t == "follow_up":
            template = data.event_template(event.template_id)
            if template.follow_up:
                queued_id, ids_ = state.next_ids.take("queued")
                state = replace(state, next_ids=ids_)
                state = with_queued(
                    state,
                    QueuedEvent(
                        id=queued_id,
                        company_id=cid,
                        template_id=template.follow_up,
                        due_turn=state.turn + 1,
                        source_event_id=event.id,
                        person_ids=event.person_ids,
                        product_id=event.product_id,
                        unit_id=event.unit_id,
                        rival_id=event.rival_id,
                        segment=event.segment,
                    ),
                )
        # energy_delta applies when energy resets for next month (energy_next_month).
    state = with_event(
        state,
        replace(
            event,
            status="auto" if auto else "answered",
            chosen=key if choice else None,
            resolved_turn=state.turn,
        ),
    )
    if event.storyline_id is not None:
        story = state.storyline(event.storyline_id)
        if story is not None and story.status == "active" and story.next_template is None:
            state = with_storyline(state, replace(story, status="ended", ended_turn=state.turn))
    return state, tuple(entries), tuple(logs)


def auto_resolve(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Phase 1: the player's unanswered minor and major events resolve to their first
    choice at Continue (16.3). A written critical event never reaches here (advance_turn
    refuses); an event whose words were never written closes with nothing applied (only
    in-memory tests run turns without the event service)."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for event in state.open_events(state.player.id):
        if event.severity == "critical" and event.status == "open":
            continue
        first = event.choices[0].key if event.choices else "A"
        state, posted, logged = apply_choice(state, event, first, balance, data, auto=True)
        entries += posted
        logs += logged
    return state, tuple(entries), tuple(logs)
