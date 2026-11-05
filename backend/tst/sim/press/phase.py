"""Phase 12 for the press (docs/formulas.md 29, M14b), before the event director, and the
firing hook. Order: feuds and rivals' statements, promises, bold claims' backfires,
credibility's drift, then the month's moments are kept or skipped."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.log import LogItem
from tst.sim.press import moments, promises
from tst.sim.press.models import Credibility
from tst.sim.rivals import characters
from tst.sim.rivals.models import RivalMove
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, credibility_of, player_companies, with_credibility


def press_month(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    rival_moves: Iterable[RivalMove],
) -> tuple[GameState, tuple[LogItem, ...]]:
    if state.ended:
        return state, ()
    for company in player_companies(state):
        if credibility_of(state, company.id) is None:  # 29.3: every company starts at 50
            state = with_credibility(state, Credibility(company.id, balance.press.cred_start))
    state, feud_logs = characters.feud_month(state, rng, balance, data, rival_moves)
    state, promise_logs = promises.check(state, rng, balance, data)
    state = moments.backfires(state, balance)
    state = moments.drift_credibility(state, balance)
    state = moments.schedule(state, balance)
    return state, (*feud_logs, *promise_logs)


def on_fire(
    state: GameState, company_id: int, staff_before: int, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """A firing (29.1, 29.2): it breaks any open no-layoffs promise, and once the month's
    firings reach press.layoff_share of the staff at its first firing, a layoffs moment."""
    company = state.company(company_id)
    if not company.is_player:
        return state, []
    state, logs = promises.break_no_layoffs(state, company_id, balance, data)
    record = credibility_of(state, company_id) or Credibility(company_id, balance.press.cred_start)
    if record.fired_turn != state.turn:
        record = replace(record, fired_turn=state.turn, fired=0, staff_start=staff_before)
    record = replace(record, fired=record.fired + 1)
    state = with_credibility(state, record)
    share = record.fired / record.staff_start if record.staff_start else 0.0
    already = any(
        m.company_id == company_id and m.trigger == "layoffs" and m.turn == state.turn
        for m in state.press_moments
    )
    if share >= balance.press.layoff_share and not already:
        state = moments.queue_moment(state, company_id, "layoffs", {"result": str(record.fired)})
    return state, logs
