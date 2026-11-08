"""Applying an event's choice (docs/formulas.md 16.3; ADR-0005, ADR-0014): the engine
disposes. Every effect was validated and clamped when the event was written; here it is
clamped again against the stored severity and cash base, and anything whose target is gone
(someone left, a pair ended, a product retired) is skipped.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.events.data import LOAN_EFFECTS
from tst.sim.events.formulas import cash_cap, clamp_effect
from tst.sim.events.models import EventChoice, GameEvent, QueuedEvent
from tst.sim.events.modifiers import start as start_modifier
from tst.sim.finance.debt import repay as repay_loan
from tst.sim.ledger import (
    CASH,
    GENERAL_ADMIN,
    INTEREST,
    OTHER_INCOME,
    LedgerBalances,
    LedgerEntry,
    apply_entries,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.markets_public.ipo import apply_ipo_step
from tst.sim.markets_public.public import apply_public_step
from tst.sim.money import BP_DENOMINATOR, exact
from tst.sim.org.rules import org_view
from tst.sim.people.relationships import clamp_relationship, pair_key
from tst.sim.press.moments import apply_tone
from tst.sim.state import (
    GameState,
    listed_id,
    public_of,
    with_approach,
    with_employment,
    with_event,
    with_loan,
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


def _loan_effect(
    state: GameState, kind: str, loan_id: int, share: float, event: GameEvent, balance: Balance
) -> tuple[GameState, list[LedgerEntry]]:
    """A lender event's choice (M10, 20.3), `share` of debt.breach's size: the waiver fee
    (1% of the balance, held to the event's cash cap) to 7000_interest; the rate rise for the
    rest of the term; or repaying part of the balance from cash at once."""
    loan = state.loan(loan_id)
    if loan is None or not loan.active or loan.company_id != event.company_id or share <= 0:
        return state, []
    bb = balance.debt.breach
    memo = f"Event: {event.title or event.template_id}"
    if kind == "loan_rate":
        bump = round(exact(share) * bb.rate_up_bp)
        return with_loan(state, replace(loan, rate_bp=loan.rate_bp + bump)), []
    if kind == "loan_repay":
        amount = round(exact(share) * loan.balance_cents * bb.repay_bp / BP_DENOMINATOR)
        state, _, posted = repay_loan(state, loan, amount, memo)
        return state, list(posted)
    fee = exact(share) * loan.balance_cents * bb.waiver_fee_bp / BP_DENOMINATOR
    cap = cash_cap(event.severity, balance.events, event.cash_base_cents, gain=False)
    cents = round(min(fee, cap))
    if cents <= 0:
        return state, []
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=event.company_id,
        memo=memo,
        debit=INTEREST,
        credit=CASH,
        amount=cents,
    )
    return state, [entry]


def _retain(state: GameState, person_id: int) -> tuple[GameState, list[LogItem]]:
    """Someone serving notice after resigning or accepting a rival stays (23.3): the notice
    is withdrawn and an accepted approach lapses."""
    employment = state.employment_of(person_id)
    if employment is None or employment.status != "notice":
        return state, []
    if employment.end_reason not in ("resigned", "poached"):
        return state, []
    state = with_employment(
        state, replace(employment, status="active", end_turn=None, end_reason=None)
    )
    for approach in state.approaches:
        if approach.person_id == person_id and approach.status == "accepted":
            state = with_approach(
                state, replace(approach, status="lapsed", resolved_turn=state.turn)
            )
    person = state.person(person_id)
    log = inbox_item(
        state.turn,
        employment.company_id,
        "retained",
        link_kind="person",
        link_id=person_id,
        name=f"{person.first_name} {person.last_name}",
    )
    return state, [log]


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
    balances: LedgerBalances | None = None,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Apply one choice of an open event and close it. An event whose words were never
    written (no choices) closes with nothing applied. `balances` (the ledger so far) is
    needed only by a choice that settles money against a balance: accepting a takeover."""
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
        elif t in LOAN_EFFECTS and kind == "loan" and ids:
            state, posted = _loan_effect(state, t, ids[0], value, event, balance)
            entries += posted
        elif t == "retain" and kind == "person" and ids:  # a counter-offer (M10b, 23.3)
            state, kept = _retain(state, ids[0])
            logs += kept
        elif t == "modifier":  # runs for its months from this one (M10b, 23.2)
            state = start_modifier(state, cid, event.id, effect, event.severity, balance.events)
        elif t == "press_step" and effect.stat:  # M14b (29.1): a press moment's tone
            state, logged = apply_tone(state, event, effect.stat, balance, data)
            logs += logged
        elif t == "group_step" and effect.stat:  # M16 (31.6): a minority complaint's answer
            from tst.sim.group.transfer import group_step

            state, logged = group_step(state, event, effect.stat)
            logs += logged
        elif t == "founder_step" and effect.stat:  # M24 (32.1, 32.5)
            from tst.sim.founder.phase import founder_step

            state, logged = founder_step(state, event, effect.stat, balance, data)
            logs += logged
        elif t == "public_step" and effect.stat:  # M13 (25): the IPO chain and public life
            state, posted, logged = public_step(
                state,
                cid,
                effect.stat,
                balance,
                data,
                None if balances is None else apply_entries(balances, entries),
            )
            entries += posted
            logs += logged
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


BLOCKING_SEVERITIES = ("major", "critical")  # 23.1 (M10b)


def blocking_events(state: GameState) -> tuple[GameEvent, ...]:
    """The player's written major and critical events still to answer: they block Continue
    while the player is at the controls (23.1, M10b)."""
    return tuple(
        e
        for e in state.open_events(state.player.id)
        if e.severity in BLOCKING_SEVERITIES and e.status == "open"
    )


def auto_resolve(
    state: GameState, balance: Balance, data: GameData, balances: LedgerBalances | None = None
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
        state, posted, logged = apply_choice(
            state,
            event,
            first,
            balance,
            data,
            auto=True,
            balances=None if balances is None else apply_entries(balances, entries),
        )
        entries += posted
        logs += logged
    return state, tuple(entries), tuple(logs)


def public_step(
    state: GameState,
    company_id: int,
    step: str,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances | None = None,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """M13 (25): IPO steps go to the chain; activist, takeover and CEO-vote steps to the
    public company."""
    if step.startswith(("activist_", "takeover_")) and public_of(state, company_id) is None:
        company_id = listed_id(state)  # M16 (31.2): the holding company holds the listing
    if step.startswith(("activist_", "takeover_", "ceo_")):
        return apply_public_step(state, company_id, step, balance, data, balances)
    return apply_ipo_step(state, company_id, step, balance, data)
