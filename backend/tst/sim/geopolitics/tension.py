"""US-China tension, 0-100 (docs/formulas.md 39.1-39.2).

To December 2025 (export_controls.yaml `last_month`) tension is countries.yaml's history, the
same on every seed. Each later month, drawn in phase 12 of the month before (so a month's
tension, rules and suspensions exist in the state from the month they are announced, and
nothing ahead of it does):

- `t' = mean + phi x (t - mean) + sd x z`, held to 0-100;
- unless an escalation or détente came within `gap_months`, an **escalation** starts with
  chance `base + slope x (t - pivot)` (at least 0): tension rises by `jump` and one seeded rule
  not in force is added, drawn uniformly; else a **détente** with chance `base - slope x (t -
  pivot)`: tension falls by `jump` and one biting rule in force is suspended for
  `suspend_months`, drawn uniformly.

Stream `geopolitics` (id 55), key (0,) at the new month: a standard normal, then three
uniforms (escalation, détente, the pick), every month in that order whether used or not.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics.draws import TENSION, geo_draws
from tst.sim.geopolitics.models import SeededRule, ShockKind, Suspension, TensionMonth
from tst.sim.geopolitics.world import countries_of
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

UNIFORMS: Final = 3  # tunable-exempt: escalation, détente and pick
LO, HI = 0.0, 100.0  # tunable-exempt: tension's scale


def last_history_turn(data: GameData) -> int:
    return gr.controls_of(data).last_turn


def history_value(data: GameData, turn: int) -> float:
    value = 0.0
    for month, v in countries_of(data).tension_history:
        if month_to_turn(month) <= turn:
            value = v
    return value


def tension_at(state: GameState, data: GameData, turn: int | None = None) -> float:
    """Tension in `turn` (default: the state's): history, else the seeded month (the latest
    one at or before it)."""
    t = state.turn if turn is None else turn
    if t <= last_history_turn(data):
        return history_value(data, t)
    value = history_value(data, last_history_turn(data))
    for m in state.tension:
        if m.turn <= t:
            value = m.value
    return value


def last_shock_turn(state: GameState) -> int | None:
    shocks = [m.turn for m in state.tension if m.shock != "none"]
    return max(shocks) if shocks else None


def shock_chances(prev: float, balance: Balance) -> tuple[float, float]:
    """(escalation, détente) chances this month at tension `prev` (module docstring)."""
    g = balance.geopolitics
    esc = max(0.0, g.escalation.base + g.escalation.slope * (prev - g.escalation.pivot))
    det = max(0.0, g.detente.base - g.detente.slope * (prev - g.detente.pivot))
    return esc, det


def step(
    prev: float, z: float, u_esc: float, u_det: float, gap_ok: bool, balance: Balance
) -> tuple[float, ShockKind]:
    """The AR(1) step and which shock (if any) starts: the pure core of `next_month`."""
    t = balance.geopolitics.tension
    value = t.mean + t.phi * (prev - t.mean) + t.sd * z
    kind: ShockKind = "none"
    if gap_ok:
        esc, det = shock_chances(prev, balance)
        if u_esc < esc:
            kind = "escalation"
            value += balance.geopolitics.escalation.jump
        elif u_det < det:
            kind = "detente"
            value -= balance.geopolitics.detente.jump
    return min(HI, max(LO, value)), kind


def next_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, ShockKind, str | None]:
    """Draw tension for the month after the state's (phase 12): the new state, the shock and
    the rule key it added or suspended."""
    turn = state.turn + 1
    if turn <= last_history_turn(data) or any(m.turn == turn for m in state.tension):
        return state, "none", None
    gen = geo_draws(rng, turn, TENSION)
    z = float(gen.standard_normal())
    u_esc, u_det, u_pick = (float(x) for x in gen.random(UNIFORMS))
    prev = tension_at(state, data, state.turn)
    last = last_shock_turn(state)
    gap = max(balance.geopolitics.escalation.gap_months, balance.geopolitics.detente.gap_months)
    value, kind = step(prev, z, u_esc, u_det, last is None or turn - last > gap, balance)
    rule_key: str | None = None
    if kind == "escalation":
        active = {a.key for a in gr.in_force(state, data, turn)}
        pool = [r.key for r in gr.controls_of(data).seeded if r.key not in active]
        if pool:
            rule_key = pool[min(len(pool) - 1, int(u_pick * len(pool)))]
            state = replace(state, seeded_rules=(*state.seeded_rules, SeededRule(rule_key, turn)))
    elif kind == "detente":
        pool = [a.key for a in gr.biting(state, data, turn)]
        if pool:
            rule_key = pool[min(len(pool) - 1, int(u_pick * len(pool)))]
            months = balance.geopolitics.detente.suspend_months
            sus = Suspension(rule_key, turn, turn + months - 1)
            state = replace(state, suspensions=(*state.suspensions, sus))
    month = TensionMonth(turn, value, kind)
    return replace(state, tension=(*state.tension, month)), kind, rule_key
