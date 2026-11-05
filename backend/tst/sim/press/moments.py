"""Press moments and credibility (docs/formulas.md 29.1, 29.3, M14b).

Engine code raises a moment with `queue_moment` (M14 adds the acquisition trigger through the
same hook). Phase 12 (`press_month`) keeps at most `press.max_per_quarter` a quarter and one
a month, highest stakes first, and queues each kept moment's `press_<trigger>` template for
next month; the rest are skipped. The answer's `press_step` effect applies its tone here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import GameEvent, Modifier, QueuedEvent
from tst.sim.log import LogItem
from tst.sim.press.config import MOMENT_TRIGGERS, REMINDER
from tst.sim.press.models import Credibility, Fact, PressMoment
from tst.sim.state import (
    GameState,
    credibility_of,
    public_of,
    with_credibility,
    with_modifier,
    with_press_moment,
    with_queued,
)

PCT = 100
QUARTER = 3  # tunable-exempt: calendar
LISTED_STAGE = 4  # tunable-exempt: the spec's stage 4
SCALEUP_STAGE = 3  # tunable-exempt: the spec's stage 3
BRAND_TARGET = "brand_target"
MEMORY = 12  # tunable-exempt: months of answered moments kept in the live state


def template_for(trigger: str) -> str:
    return f"press_{trigger}"


# --- Audience and credibility (29.1, 29.3) -------------------------------------------------------


def audience(state: GameState, company_id: int, balance: Balance) -> float:
    """a: 0.5 at stages 1-2, 1.0 at stage 3, 1.5 once listed (29.1)."""
    ab = balance.press.audience
    company = state.company(company_id)
    if public_of(state, company_id) is not None or company.stage >= LISTED_STAGE:
        return ab.listed
    return ab.scaleup if company.stage >= SCALEUP_STAGE else ab.early


def credibility(state: GameState, company_id: int, balance: Balance) -> float:
    record = credibility_of(state, company_id)
    return record.value if record is not None else balance.press.cred_start


def cred_factor(state: GameState, company_id: int, balance: Balance) -> float:
    """Brand gains from press x (0.5 + credibility / 100) (29.3)."""
    return 1 / 2 + credibility(state, company_id, balance) / PCT


def hiring_appeal(state: GameState, company_id: int, balance: Balance) -> float:
    """+cred_hiring x (credibility - 50) / 50, at most cred_hiring_cap either way (29.3)."""
    pb = balance.press
    record = credibility_of(state, company_id)
    if record is None:
        return 0.0
    raw = pb.cred_hiring * (record.value - pb.cred_start) / (PCT - pb.cred_start)
    return max(-pb.cred_hiring_cap, min(pb.cred_hiring_cap, raw))


def adjust_credibility(
    state: GameState, company_id: int, delta: float, cause: str, balance: Balance
) -> GameState:
    """Credibility moves by `delta`, clamped to 0-100, remembering the cause (29.3)."""
    if not delta:
        return state
    pb = balance.press
    record = credibility_of(state, company_id) or Credibility(company_id, pb.cred_start)
    value = max(0.0, min(float(PCT), record.value + delta))
    history = (*record.history, (state.turn, value - record.value, cause))[-pb.cred_history :]
    return with_credibility(state, replace(record, value=value, history=history))


def drift_credibility(state: GameState, balance: Balance) -> GameState:
    """1 a month toward 50 (29.3); not a cause the panel lists."""
    pb = balance.press
    for record in state.credibility:
        gap = pb.cred_start - record.value
        if gap:
            step = max(-pb.cred_drift, min(pb.cred_drift, gap))
            state = with_credibility(state, replace(record, value=record.value + step))
    return state


def brand_modifier(
    state: GameState,
    company_id: int,
    value_pct: float,
    months: int,
    event_id: int | None = None,
) -> GameState:
    """A press effect on every product's brand target for `months` (29.1, 29.2)."""
    if not value_pct:
        return state
    mid, ids = state.next_ids.take("modifier")
    return with_modifier(
        replace(state, next_ids=ids),
        Modifier(
            id=mid,
            company_id=company_id,
            event_id=event_id,
            target=f"company:{company_id}",
            stat=BRAND_TARGET,
            value_pct=value_pct,
            start_turn=state.turn,
            end_turn=state.turn + months,
        ),
    )


# --- Raising and keeping moments (29.1) ------------------------------------------------------


def queue_moment(
    state: GameState,
    company_id: int,
    trigger: str,
    facts: Mapping[str, int | str] | None = None,
) -> GameState:
    """Raise a press moment for `company_id` (29.1). `facts` may carry `product_id`,
    `rival_id` and `segment`, and displayed words for the template (`era`, `result`,
    `promise`). The hook M14 uses for the acquisition trigger. Only the player's companies
    have press moments; others are ignored."""
    company = state.company(company_id)
    if not company.is_player or trigger not in (*MOMENT_TRIGGERS, REMINDER):
        return state
    facts = dict(facts or {})
    product_id = facts.pop("product_id", None)
    rival_id = facts.pop("rival_id", None)
    mid, ids = state.next_ids.take("press_moment")
    moment = PressMoment(
        id=mid,
        company_id=company_id,
        trigger=trigger,
        turn=state.turn,
        product_id=int(product_id) if product_id is not None else None,
        rival_id=int(rival_id) if rival_id is not None else None,
        facts=tuple(sorted(facts.items())),
    )
    return with_press_moment(replace(state, next_ids=ids), moment)


def moment_for_event(state: GameState, event: GameEvent) -> PressMoment | None:
    """The press moment an event shows (one a month at most)."""
    return next(
        (
            m
            for m in state.press_moments
            if m.company_id == event.company_id
            and m.event_turn == event.turn
            and m.status in ("queued", "answered")
        ),
        None,
    )


def _quarter(turn: int) -> int:
    return turn // QUARTER


def schedule(state: GameState, balance: Balance) -> GameState:
    """Phase 12: each company's pending moments are kept or skipped. A kept moment's event is
    shown next month; a quarter keeps at most press.max_per_quarter (reminders apart), a month
    at most one."""
    next_month = state.turn + 1
    for company_id in sorted({m.company_id for m in state.press_moments if m.status == "pending"}):
        mine = [m for m in state.press_moments if m.company_id == company_id]
        taken = {m.event_turn for m in mine if m.event_turn is not None}
        used = sum(
            1
            for m in mine
            if m.event_turn is not None
            and _quarter(m.event_turn) == _quarter(next_month)
            and m.trigger != REMINDER
        )
        pending = [m for m in mine if m.status == "pending"]
        due = [m for m in pending if m.trigger != REMINDER or _reminder_due(state, m)]
        due.sort(key=lambda m: (_stakes(m.trigger), m.id))
        for m in due:
            free = next_month not in taken
            fits = m.trigger == REMINDER or used < balance.press.max_per_quarter
            if free and fits:
                state = _queue_event(state, m, next_month)
                taken.add(next_month)
                used += m.trigger != REMINDER
            elif m.trigger != REMINDER:
                state = with_press_moment(state, replace(m, status="skipped"))
        keep = state.turn - MEMORY
        state = replace(
            state,
            press_moments=tuple(
                m for m in state.press_moments if m.status in ("pending", "queued") or m.turn > keep
            ),
        )
    return state


def _reminder_due(state: GameState, m: PressMoment) -> bool:
    facts = dict(m.facts)
    due = facts.get("due_turn")
    return due is None or int(due) <= state.turn + 1


def _stakes(trigger: str) -> int:
    order = (*MOMENT_TRIGGERS, REMINDER)
    return order.index(trigger) if trigger in order else len(order)


def _queue_event(state: GameState, m: PressMoment, due: int) -> GameState:
    qid, ids = state.next_ids.take("queued")
    facts = dict(m.facts)
    state = with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=m.company_id,
            template_id=template_for(m.trigger),
            due_turn=due,
            source_event_id=None,
            product_id=m.product_id,
            rival_id=m.rival_id,
            segment=str(facts["segment"]) if "segment" in facts else None,
        ),
    )
    return with_press_moment(state, replace(m, status="queued", event_turn=due))


def facts_of(m: PressMoment) -> dict[str, int | str]:
    return dict(m.facts)


def as_facts(**kw: int | str | None) -> tuple[Fact, ...]:
    return tuple(sorted((k, v) for k, v in kw.items() if v is not None))


# --- Tones (29.1) -----------------------------------------------------------------------------


def apply_tone(
    state: GameState, event: GameEvent, tone: str, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """The answer's tone: bold lifts the brand target and may draw the named rival; measured
    lifts it a little; deflect costs credibility (29.1). Effects x a; brand x the credibility
    factor."""
    from tst.sim.press.shares import product_share_bp
    from tst.sim.rivals import characters

    pb = balance.press
    cid = event.company_id
    moment = moment_for_event(state, event)
    a = audience(state, cid, balance)
    cf = cred_factor(state, cid, balance)
    logs: list[LogItem] = []
    share = None
    if tone == "bold":
        state = brand_modifier(state, cid, pb.bold_brand * a * cf, pb.bold_months, event.id)
        if moment is not None and moment.product_id is not None:
            share = product_share_bp(state, moment.product_id)
        if moment is not None and moment.rival_id is not None:
            state, logged = characters.bold_mention(state, cid, moment.rival_id, balance, data)
            logs += logged
    elif tone == "measured":
        state = brand_modifier(state, cid, pb.measured_brand * a * cf, pb.measured_months, event.id)
    elif tone == "deflect":
        state = adjust_credibility(
            state, cid, pb.deflect_cred * a, "no comment to the press", balance
        )
    if moment is not None:
        state = with_press_moment(
            state,
            replace(
                moment,
                status="answered",
                tone=tone,
                answered_turn=state.turn,
                share_bp=share if tone == "bold" else None,
            ),
        )
    return state, logs


def backfires(state: GameState, balance: Balance) -> GameState:
    """Phase 12: a bold claim made in the last press.backfire_months backfires once when
    results contradict it: its product's displayed share has fallen, or the last report was a
    miss once listed (29.1). Credibility -press.bold_backfire x a."""
    from tst.sim.press.shares import product_share_bp

    pb = balance.press
    for m in state.press_moments:
        if m.tone != "bold" or m.backfired or m.answered_turn is None:
            continue
        if state.turn - m.answered_turn > pb.backfire_months:
            continue
        fell = (
            m.product_id is not None
            and m.share_bp is not None
            and product_share_bp(state, m.product_id) < m.share_bp
        )
        public = public_of(state, m.company_id)
        missed = (
            public is not None
            and bool(public.results)
            and public.results[-1] == "miss"
            and _reported_since(state, m)
        )
        if fell or missed:
            a = audience(state, m.company_id, balance)
            cause = "results contradicted a bold claim"
            state = adjust_credibility(state, m.company_id, -pb.bold_backfire * a, cause, balance)
            state = with_press_moment(state, replace(m, backfired=True))
    return state


def _reported_since(state: GameState, m: PressMoment) -> bool:
    assert m.answered_turn is not None
    return any(
        g.company_id == m.company_id
        and g.reported
        and g.quarter_turn + QUARTER - 1 >= m.answered_turn
        and g.quarter_turn + QUARTER - 1 == state.turn
        for g in state.guidance
    )
