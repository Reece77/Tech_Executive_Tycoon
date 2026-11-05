"""Public promises (docs/formulas.md 29.2, M14b): made in a press moment, judged on displayed
values only (press.shares), kept or broken at the deadline or when broken earlier, with
brand, credibility, sentiment, morale and trust effects, and a "you said ..." reminder."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.log import LogItem, inbox_item
from tst.sim.people.relationships import clamp_relationship
from tst.sim.press import moments
from tst.sim.press.config import PROMISE_KINDS, REMINDER
from tst.sim.press.draws import press_gen
from tst.sim.press.models import Promise
from tst.sim.press.shares import shown_lead, shown_prices, shown_quality
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    public_of,
    with_person_state,
    with_promise,
    with_public,
    with_relationship,
)

MORALE_MAX = 100  # tunable-exempt: the morale scale
TIMED = ("ship", "beat", "research")
HALF = 0.5  # tunable-exempt: ambition is half the target's distance, half the deadline's


def open_promises(state: GameState, company_id: int) -> tuple[Promise, ...]:
    return tuple(p for p in state.promises if p.company_id == company_id and p.open)


def promise_words(state: GameState, p: Promise, data: GameData) -> str:
    """'ship Forge by Jun 2016', in the words the player said them."""
    from tst.sim.calendar import format_turn

    by = format_turn(p.deadline_turn)
    product = state.product(p.product_id) if p.product_id is not None else None
    name = product.name if product is not None else "the product"
    match p.kind:
        case "ship":
            return f"ship {name} by {by}"
        case "beat":
            rival = state.product(p.rival_product_id) if p.rival_product_id is not None else None
            return f"have {name} beat {rival.name if rival else 'the rival'} on quality by {by}"
        case "research":
            return f"reach a lead of {p.level} in {p.domain} by {by}"
        case "no_layoffs":
            return f"make no layoffs until {by}"
    return f"not raise {name}'s price until {by}"


def _time_ambition(months: int, balance: Balance) -> float:
    lo, hi = balance.promise.months
    return max(0.0, min(1.0, (hi - months) / (hi - lo)))


def make(
    state: GameState,
    company_id: int,
    kind: str,
    balance: Balance,
    data: GameData,
    *,
    product_id: int | None = None,
    rival_product_id: int | None = None,
    domain: str | None = None,
    level: int | None = None,
    months: int | None = None,
) -> tuple[GameState, Promise]:
    """The rules of making a promise (29.2); energy is spent by the action."""
    pb = balance.promise
    if kind not in PROMISE_KINDS:
        raise InvalidActionError(f"unknown promise {kind!r}")
    moment = next(
        (
            m
            for m in state.press_moments
            if m.company_id == company_id
            and m.answered_turn == state.turn
            and m.tone in ("bold", "measured")
        ),
        None,
    )
    if moment is None:
        raise InvalidActionError("a promise is made in a press moment answered this month")
    if any(p.moment_id == moment.id for p in state.promises):
        raise InvalidActionError("one promise a press moment")
    if len(open_promises(state, company_id)) >= pb.max_open:
        raise InvalidActionError(f"at most {pb.max_open} promises open at once")
    lo, hi = pb.months
    if kind in TIMED:
        if months is None or not lo <= months <= hi:
            raise InvalidActionError(f"a {kind} promise is due {lo} to {hi} months out")
    else:
        months = pb.fixed_months
    product = state.product(product_id) if product_id is not None else None
    if kind in ("ship", "beat", "no_price_rise") and (
        product is None or product.company_id != company_id
    ):
        raise InvalidActionError("the promise needs one of your products")
    baseline = 0
    ambition = pb.fixed_ambition
    if kind == "ship":
        assert product is not None
        if product.status != "in_development":
            raise InvalidActionError("a ship promise is about a product in development")
        ambition = _time_ambition(months, balance)
    elif kind == "beat":
        assert product is not None
        rival = state.product(rival_product_id) if rival_product_id is not None else None
        if rival is None or rival.company_id == company_id or rival.category != product.category:
            raise InvalidActionError("a beat promise names a rival's product in the category")
        baseline = shown_quality(state, product.id)
        gap = shown_quality(state, rival.id) - baseline
        ambition = HALF * max(0.0, min(1.0, gap / pb.beat_span)) + HALF * _time_ambition(
            months, balance
        )
    elif kind == "research":
        if domain is None or level is None:
            raise InvalidActionError("a research promise names a domain and a level")
        baseline = shown_lead(state, company_id, domain)
        if level <= baseline:
            raise InvalidActionError("the level must be above today's lead")
        ambition = HALF * min(1.0, (level - baseline) / pb.research_span) + HALF * _time_ambition(
            months, balance
        )
    elif kind == "no_price_rise":
        assert product is not None
        if not shown_prices(state, product.id):
            raise InvalidActionError("the product has no prices yet")
    pid, ids = state.next_ids.take("promise")
    promise = Promise(
        id=pid,
        company_id=company_id,
        kind=kind,
        made_turn=state.turn,
        deadline_turn=state.turn + months,
        moment_id=moment.id,
        product_id=product_id,
        rival_product_id=rival_product_id,
        domain=domain,
        level=level,
        baseline=baseline,
        ambition=ambition,
        audience=moments.audience(state, company_id, balance),
        prices=tuple(sorted(shown_prices(state, product.id).items()))
        if kind == "no_price_rise" and product is not None
        else (),
    )
    return with_promise(replace(state, next_ids=ids), promise), promise


# --- Judging (29.2): displayed values only -------------------------------------------------------


def verdict(state: GameState, p: Promise) -> str | None:
    """'kept', 'broken' or None (still open), from displayed values only."""
    due = state.turn >= p.deadline_turn
    product = state.product(p.product_id) if p.product_id is not None else None
    match p.kind:
        case "ship":
            if product is not None and product.status in ("live", "sunset"):
                return "kept"
            if product is None or product.status == "retired" or due:
                return "broken"
        case "beat":
            if due:
                rival = state.product(p.rival_product_id) if p.rival_product_id else None
                ours = shown_quality(state, product.id) if product is not None else 0
                theirs = shown_quality(state, rival.id) if rival is not None else 0
                return "kept" if ours > theirs else "broken"
        case "research":
            assert p.domain is not None and p.level is not None
            caused = any(
                e.company_id == p.company_id and p.made_turn <= e.turn <= state.turn
                for e in state.era_arrivals
            )
            if shown_lead(state, p.company_id, p.domain) >= p.level or caused:
                return "kept"
            if due:
                return "broken"
        case "no_layoffs":
            if due:
                return "kept"
        case "no_price_rise":
            if product is not None:
                now = shown_prices(state, product.id)
                if any(now.get(seg, cents) > cents for seg, cents in p.prices):
                    return "broken"
            if due:
                return "kept"
    return None


def break_no_layoffs(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """A firing breaks every open no-layoffs promise at once (29.2)."""
    logs: list[LogItem] = []
    for p in open_promises(state, company_id):
        if p.kind == "no_layoffs":
            state, logged = resolve(state, p, "broken", balance, data)
            logs += logged
    return state, logs


def check(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Phase 12: every open promise is judged; a broken one schedules its reminder."""
    logs: list[LogItem] = []
    gens: dict[int, np.random.Generator] = {}
    for p in sorted(state.promises, key=lambda x: x.id):
        if not p.open:
            continue
        result = verdict(state, p)
        if result is None:
            continue
        if p.company_id not in gens:  # stream press, key (company_id,): one a month (29.4)
            gens[p.company_id] = press_gen(rng, state.turn, p.company_id)
        lo, hi = balance.press.reminder_months
        months = int(gens[p.company_id].integers(lo, hi + 1))
        state, logged = resolve(state, p, result, balance, data, months)
        logs += logged
    return state, logs


def resolve(
    state: GameState,
    p: Promise,
    result: str,
    balance: Balance,
    data: GameData,
    reminder_in: int | None = None,
) -> tuple[GameState, list[LogItem]]:
    """Kept: brand target +4 x a x (1 + ambition) x the credibility factor for 12 months and
    credibility +5 x a; morale +2 for no layoffs. Broken: brand target -8 x a, credibility
    -10 x a, sentiment -0.05 x a once listed; no layoffs: morale -5 and trust in the founder
    -10; then a reminder (29.2)."""
    pb = balance.promise
    cid = p.company_id
    a = p.audience
    words = promise_words(state, p, data)
    if result == "kept":
        cf = moments.cred_factor(state, cid, balance)
        state = moments.brand_modifier(
            state, cid, pb.kept_brand * a * (1 + p.ambition) * cf, pb.kept_months
        )
        state = moments.adjust_credibility(state, cid, pb.kept_cred * a, f"kept: {words}", balance)
        if p.kind == "no_layoffs":
            state = _morale_all(state, cid, pb.kept_morale)
        state = with_promise(state, replace(p, status="kept", resolved_turn=state.turn))
        return state, [inbox_item(state.turn, cid, "promise_kept", promise=words)]
    state = moments.brand_modifier(state, cid, -pb.broken_brand * a, pb.broken_months)
    state = moments.adjust_credibility(state, cid, -pb.broken_cred * a, f"broken: {words}", balance)
    public = public_of(state, cid)
    if public is not None:
        bounds = balance.public.sentiment.bounds
        state = with_public(
            state,
            replace(public, sentiment=bounds.clamp(public.sentiment - pb.broken_sentiment * a)),
        )
    if p.kind == "no_layoffs":
        state = _morale_all(state, cid, -pb.broken_morale)
        state = _trust(state, cid, -pb.broken_trust, balance)
    # broken by an action between turns: the reminder comes after the shortest wait
    months = reminder_in if reminder_in is not None else balance.press.reminder_months[0]
    state = moments.queue_moment(
        state, cid, REMINDER, {"promise": words, "due_turn": state.turn + months}
    )
    state = with_promise(
        state,
        replace(p, status="broken", resolved_turn=state.turn, reminder_turn=state.turn + months),
    )
    return state, [inbox_item(state.turn, cid, "promise_broken", promise=words)]


def _morale_all(state: GameState, company_id: int, delta: float) -> GameState:
    founder = state.founder_of(company_id)
    for e in state.staff(company_id):
        if founder is not None and e.person_id == founder.id:
            continue
        ps = state.person_state(e.person_id)
        if ps.morale is not None:
            morale = max(0.0, min(float(MORALE_MAX), ps.morale + delta))
            state = with_person_state(state, replace(ps, morale=morale))
    return state


def _trust(state: GameState, company_id: int, delta: float, balance: Balance) -> GameState:
    founder = state.founder_of(company_id)
    if founder is None:
        return state
    for rel in state.relationships_of(founder.id):
        value = clamp_relationship(rel.value + delta, balance.relationships)
        state = with_relationship(state, replace(rel, value=value))
    return state
