"""Stress and burnout (docs/formulas.md 32.1, M24). Each month's stress comes from the share
of the month's energy budget the founder spent; burnout at stress.burnout_at cuts next
month's budget by stress.burnout_cut until stress falls below stress.recover_below."""

from __future__ import annotations

import math
from dataclasses import replace

from tst.sim.data_models import Balance
from tst.sim.founder.config import StressBalance
from tst.sim.founder.models import FounderLife

STRESS_MAX = 100.0  # tunable-exempt: stress is 0-100


def new_life(person_id: int, balance: Balance) -> FounderLife:
    pb = balance.persona
    return FounderLife(
        person_id=person_id,
        stress=balance.stress.start,
        visionary=pb.start,
        ruthless=pb.start,
        beloved=pb.start,
        reckless=pb.start,
    )


def used_share(budget: int | None, remaining: int | None, default_budget: int) -> float:
    """The share of the month's energy budget spent, 0-1. A month with no budget (a month
    off) used nothing; energy above the budget (an event's bonus) is not use."""
    cap = default_budget if budget is None else budget
    if cap <= 0:
        return 0.0
    left = cap if remaining is None else remaining
    return max(0.0, min(1.0, (cap - left) / cap))


def stress_terms(
    used: float, holiday: bool, critical: int, sb: StressBalance
) -> list[tuple[float, str]]:
    """The month's stress changes with their causes (32.1), in the order shown."""
    out: list[tuple[float, str]] = []
    strain = sb.load * max(0.0, used - sb.comfort)
    if strain:
        out.append((strain, f"spent {used:.0%} of your energy"))
    if used <= sb.comfort:
        out.append((-sb.recover, "a lighter month"))
    if holiday:
        out.append((-sb.holiday, "a month away"))
    if critical:
        out.append((sb.critical * critical, f"{critical} critical decision{'s' * (critical > 1)}"))
    return out


def step(
    life: FounderLife, turn: int, used: float, holiday: bool, critical: int, sb: StressBalance
) -> tuple[FounderLife, bool]:
    """One month of stress (32.1). Returns the life and whether a burnout began."""
    terms = stress_terms(used, holiday, critical, sb)
    stress = life.stress + sum(v for v, _ in terms)
    stress = max(0.0, min(STRESS_MAX, stress))
    causes = (*life.causes, *((turn, v, why) for v, why in terms))
    causes = tuple(c for c in causes if c[0] > turn - sb.history)
    began = False
    burnout = life.burnout
    if burnout and stress < sb.recover_below:
        burnout = False
    elif not burnout and stress >= sb.burnout_at:
        burnout, began = True, True
    life = replace(
        life,
        stress=stress,
        causes=causes,
        burnout=burnout,
        burnout_turn=turn if began else life.burnout_turn,
        burnouts=life.burnouts + began,
        holiday_months=life.holiday_months + holiday,
    )
    return life, began


def add_stress(
    life: FounderLife, turn: int, value: float, why: str, sb: StressBalance
) -> FounderLife:
    """Stress from a choice (pushing on, apologizing), shown with its cause."""
    stress = max(0.0, min(STRESS_MAX, life.stress + value))
    causes = tuple(c for c in (*life.causes, (turn, value, why)) if c[0] > turn - sb.history)
    return replace(life, stress=stress, causes=causes)


def budget_after_cut(energy: int, life: FounderLife | None, sb: StressBalance) -> int:
    """Next month's energy (32.1): x (1 - burnout_cut) while burnt out."""
    if life is None:
        return energy
    if life.burnout:
        return math.floor(energy * (1 - sb.burnout_cut))
    return energy
