"""Phase 12 for the founder's life (docs/formulas.md 32, M24), after the press and before the
event director. Order: the persona drifts, then this month's sources raise it; stress from
the month's energy use (a burnout queues its critical event); burnt-out bold claims that
backfired this month cost more; December's foundation grants; lobbying, influence and
scandals; the founder's salary reaches the personal book.

The founder's energy budget for the next month is set in `next_budget`, after energy resets."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import GameEvent
from tst.sim.founder import foundation, influence, persona, personal, stress
from tst.sim.founder.events import queue
from tst.sim.founder.models import FounderLife
from tst.sim.ledger import LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.press.moments import adjust_credibility, audience, brand_modifier
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    credibility_of,
    life_of,
    with_life,
    with_person_state,
)

BURNOUT_TEMPLATE: Final = "founder_burnout"
MONTHS_A_YEAR: Final = 12  # tunable-exempt: calendar
DECEMBER: Final = 11  # tunable-exempt: calendar (turn % 12)
FOUNDER_STEPS: Final = (  # events.data's founder_step stats
    "rest",
    "delegate",
    "push_on",
    "apologize",
    "drop_lobbyists",
    "fight",
)


def ensure_life(state: GameState, balance: Balance) -> tuple[GameState, FounderLife | None]:
    founder = state.founder_of(state.player.id)
    if founder is None:
        return state, None
    life = life_of(state, founder.id)
    if life is None:  # headcount_doubled's first year counts from the founding headcount
        heads = len(state.staff(state.player.id))
        life = replace(stress.new_life(founder.id, balance), headcount_mark=heads)
        state = with_life(state, life)
    return state, life


def founder_month(
    state: GameState,
    start: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    *,
    holiday: bool,
    cash_cents: int = 0,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    if state.ended:
        return state, (), ()
    state, life = ensure_life(state, balance)
    if life is None:
        return state, (), ()
    logs: list[LogItem] = []
    turn = state.turn
    cid = state.player.id
    life = persona.drift(life, balance)
    life = _sources(state, start, life, balance, cash_cents)
    state = with_life(state, life)
    state = _bold_effects(state, life, balance)
    # 32.1: stress from the month's energy use.
    ps = state.person_state(life.person_id)
    used = stress.used_share(life.budget, ps.energy, balance.founder.energy_per_month)
    away = holiday or life.rest_turn == turn
    if away:
        used = 0.0
    critical = sum(
        1
        for e in state.events
        if e.company_id == cid
        and e.severity == "critical"
        and e.resolved_turn == turn
        and e.status == "answered"
    )
    was_burnt = life.burnout
    life, began = stress.step(life, turn, used, away, critical, balance.stress)
    if was_burnt and not life.burnout:
        life = replace(life, recovered_turn=turn)
    state = with_life(state, life)
    if began:
        state = queue(state, cid, BURNOUT_TEMPLATE, turn + 1)
        logs.append(inbox_item(turn, cid, "burnout_started", stress=f"{life.stress:.0f}"))
    state = _burnt_backfires(state, start, life, balance)
    state, granted = foundation.grants_month(state, balance)
    logs += granted
    state, entries, lobbied = influence.lobbying_month(state, rng, balance, data)
    logs += lobbied
    state = personal.salary_month(state, balance)
    return state, tuple(entries), tuple(logs)


def _sources(
    state: GameState, start: GameState, life: FounderLife, balance: Balance, cash_cents: int
) -> FounderLife:
    """The month's persona sources (32.4) from records stamped with this month."""
    turn, cid = state.turn, state.player.id
    pb = balance.persona
    add = persona.apply_source
    eras = sum(1 for a in state.era_arrivals if a.turn == turn and a.company_id == cid)
    if eras:
        life = add(life, "era_caused", turn, balance, eras)
    bold = [
        m
        for m in state.press_moments
        if m.company_id == cid and m.answered_turn == turn and m.tone == "bold"
    ]
    if bold:
        life = add(life, "bold_answer", turn, balance, len(bold))
    products = state.company_products(cid)
    before = {
        p.category for p in products if p.launched_turn is not None and p.launched_turn < turn
    }
    new = {p.category for p in products if p.launched_turn == turn} - before
    if new:
        life = add(life, "new_category", turn, balance, len(new))
    for r in state.rankings:
        if r.turn == turn + 1 and r.company_id == cid and r.place <= balance.rank.effect_places:
            if r.kind == "innovative":
                life = add(life, "innovative_top", turn, balance)
            elif r.kind == "places":
                life = add(life, "places_top", turn, balance)
    record = credibility_of(state, cid)
    if (
        record is not None
        and record.fired_turn == turn
        and record.staff_start
        and record.fired / record.staff_start >= pb.layoff_share
    ):
        life = add(life, "layoffs", turn, balance)
    poached = 0
    for offer in state.offers:
        if offer.company_id != cid or offer.status != "accepted" or offer.resolved_turn != turn:
            continue
        candidate = start.candidate(offer.candidate_id)
        if candidate is not None and candidate.channel == "poach":
            poached += 1
    if poached:
        life = add(life, "poach", turn, balance, poached)
    for p in state.promises:
        if p.company_id != cid or p.resolved_turn != turn:
            continue
        if p.status == "kept":
            life = add(life, "kept_promise", turn, balance)
        elif p.status == "broken":
            life = add(life, "broken_promise", turn, balance)
            if p.kind == "no_layoffs":
                life = add(life, "broke_no_layoffs", turn, balance)
    staff = [e for e in state.staff(cid) if e.role != "founder"]
    raised = sum(1 for e in staff if e.last_raise_turn == turn)
    if staff and raised / len(staff) >= pb.raise_share:
        life = add(life, "raises", turn, balance)
    breaches = sum(1 for loan in state.loans if loan.company_id == cid and loan.breach_turn == turn)
    if breaches:
        life = add(life, "covenant_breach", turn, balance, breaches)
    return _reckless_growth(state, life, cash_cents, balance)


def _reckless_growth(
    state: GameState, life: FounderLife, cash_cents: int, balance: Balance
) -> FounderLife:
    """The product manager's Reckless sources (2026-11-07, 32.7 target 3): a month burning
    cash with runway under persona.burn_runway_months (at most persona.burn_year_cap points a
    calendar year), a down round closed this month, and, each December, headcount up more
    than persona.headcount_growth over the year."""
    pb = balance.persona
    turn, company = state.turn, state.player
    year = turn // MONTHS_A_YEAR
    if life.burn_year != year:
        life = replace(life, burn_year=year, burn_points=0.0)
    burn = company.burn_history[-1] if company.burn_history else 0
    size = pb.sources["runway_burn"]
    if (
        burn > 0
        and cash_cents < pb.burn_runway_months * burn
        and life.burn_points + size <= pb.burn_year_cap
    ):
        life = persona.apply_source(life, "runway_burn", turn, balance)
        life = replace(life, burn_points=life.burn_points + size)
    downs = sum(
        1
        for r in state.company_rounds(company.id)
        if r.status == "closed" and r.closed_turn == turn and r.down_round
    )
    if downs:
        life = persona.apply_source(life, "down_round", turn, balance, downs)
    if turn % MONTHS_A_YEAR == DECEMBER:
        heads = len(state.staff(company.id)) + round(
            sum(p.headcount for p in state.company_pools(company.id))
        )
        mark = life.headcount_mark
        if mark and heads > mark * (1 + pb.headcount_growth):
            life = persona.apply_source(life, "headcount_doubled", turn, balance)
        life = replace(life, headcount_mark=heads)
    return life


def _bold_effects(state: GameState, life: FounderLife, balance: Balance) -> GameState:
    """Beloved (32.4): this month's bold answers add persona.bold_brand to the brand target."""
    pb = balance.persona
    if life.beloved < pb.effect_at:
        return state
    cid = state.player.id
    for m in state.press_moments:
        if m.company_id == cid and m.answered_turn == state.turn and m.tone == "bold":
            state = brand_modifier(state, cid, pb.bold_brand, pb.bold_months)
    return state


def _burnt_backfires(
    state: GameState, start: GameState, life: FounderLife, balance: Balance
) -> GameState:
    """32.1: a bold claim made while burnt out that backfired this month costs
    stress.backfire_mult backfires' credibility (the press's first is already taken)."""
    if life.burnout_turn is None:
        return state
    was = {m.id for m in start.press_moments if m.backfired}
    extra = balance.stress.backfire_mult - 1
    for m in state.press_moments:
        if not m.backfired or m.id in was or m.answered_turn is None or not extra:
            continue
        end = life.recovered_turn if life.recovered_turn is not None else None
        made_burnt = life.burnout_turn <= m.answered_turn and (
            life.burnout or (end is not None and m.answered_turn < end)
        )
        if made_burnt:
            a = audience(state, m.company_id, balance)
            cost = -balance.press.bold_backfire * a * extra
            state = adjust_credibility(
                state, m.company_id, cost, "a claim made while burnt out", balance
            )
    return state


def next_budget(state: GameState, balance: Balance) -> GameState:
    """After energy resets for the new month: the burnout cut, then the budget is remembered
    for the month's use (32.1)."""
    founder = state.founder_of(state.player.id)
    if founder is None:
        return state
    life = life_of(state, founder.id)
    if life is None:
        return state
    ps = state.person_state(founder.id)
    if ps.energy is None:
        return state
    energy = stress.budget_after_cut(ps.energy, life, balance.stress)
    if energy != ps.energy:
        state = with_person_state(state, replace(ps, energy=energy))
    return with_life(state, replace(life, budget=energy))


def founder_step(
    state: GameState, event: GameEvent, step: str, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """A founder event's answer (32.1, 32.5), applied by the engine."""
    founder = state.founder_of(event.company_id)
    life = life_of(state, founder.id) if founder is not None else None
    logs: list[LogItem] = []
    if step == "rest" and life is not None and founder is not None:  # this month off
        state = with_life(state, replace(life, rest_turn=state.turn))
        ps = state.person_state(founder.id)
        if ps.energy is not None:
            state = with_person_state(state, replace(ps, energy=0))
    elif step == "push_on" and life is not None:
        life = stress.add_stress(
            life, state.turn, balance.stress.push_on, "pushed on", balance.stress
        )
        life = persona.apply_source(life, "pushed_on", state.turn, balance)
        state = with_life(state, life)
    elif step in ("apologize", "drop_lobbyists", "fight"):
        state, logs = influence.answer_scandal(state, event.company_id, event.turn, step, balance)
    return state, logs
