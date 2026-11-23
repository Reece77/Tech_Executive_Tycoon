"""Disclosure (docs/formulas.md 46.4), each December from `power.start`: every player company's
emissions for the year, scope 1 (its own plants) and scope 2 (bought energy: the grid at its
intensity, PPAs at their producer's fleet), filed in its year-end emissions report, with its
intensity in tonnes a $1M of revenue (revenue accounts' change since last December).

Above `power.carbon.green_brand_tonnes` a $1M its consumer products' brand target falls for a year
by `brand_hit` (from its low end at the threshold to its high end at twice it), and the founder's
Beloved trait by `beloved_hit`; with own plants and PPAs at or above `clean_share` of its energy
and the intensity under the threshold, the brand target rises 1 point instead. Pure functions; no
draws.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.ledger import AccountCode
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import Cents
from tst.sim.state import GameState, life_of, with_life

DECEMBER: Final = 12  # tunable-exempt: calendar
MILLION_CENTS: Final = 100_000_000  # tunable-exempt: $1M in cents
CLEAN_BONUS: Final = 1.0  # tunable-exempt: 46.4's +1 brand
MONTHS: Final = 12  # tunable-exempt: calendar


def revenue_balance(
    company_id: int, balances: Mapping[tuple[int, AccountCode], Cents], data: GameData
) -> int:
    """The company's revenue accounts' running total (credits are negative: sign flipped)."""
    codes = {a.code for a in data.accounts if a.type == "revenue"}
    return -sum(v for (c, code), v in balances.items() if c == company_id and code in codes)


def brand_points(state: GameState, company_id: int) -> float:
    """The consumer brand-target points the last disclosure left (0 when lapsed)."""
    for c, points, until in state.power_world.brand:
        if c == company_id and state.turn <= until:
            return points
    return 0.0


def disclose(
    state: GameState,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, list[LogItem]]:
    if data.power is None or state.turn < month_to_turn(balance.power.start):
        return state, []
    if turn_to_ym(state.turn)[1] != DECEMBER:
        return state, []
    cb = balance.power.carbon
    marks = dict(state.power_world.revenue_marks)
    brand = {c: (p, u) for c, p, u in state.power_world.brand}
    logs: list[LogItem] = []
    for company in [c for c in state.companies if c.is_player]:
        cid = company.id
        year = [
            m for m in state.power_months if m.company_id == cid and m.turn > state.turn - MONTHS
        ]
        rev_now = revenue_balance(cid, balances, data)
        revenue = max(0, rev_now - marks.get(cid, 0))
        marks[cid] = rev_now
        if not year:
            continue
        s1 = sum(m.scope1_tonnes for m in year)
        s2 = sum(m.scope2_tonnes for m in year)
        energy = sum(m.demand_mwh for m in year)
        clean = sum(m.plant_mwh + m.ppa_mwh for m in year) / energy if energy else 0.0
        # money-exact: ratio: tonnes per million of revenue, an intensity, not money
        per_m = (s1 + s2) / (revenue / MILLION_CENTS) if revenue > 0 else 0.0
        points = 0.0
        if cb.green_brand_tonnes and per_m > cb.green_brand_tonnes:
            over = min(1.0, per_m / cb.green_brand_tonnes - 1)
            points = -(cb.brand_hit.lo + (cb.brand_hit.hi - cb.brand_hit.lo) * over)
            founder = state.founder_of(cid)
            life = life_of(state, founder.id) if founder is not None else None
            if life is not None:
                from tst.sim.founder.persona import raise_trait

                state = with_life(
                    state,
                    raise_trait(life, "beloved", -cb.beloved_hit, "emissions", state.turn, balance),
                )
        elif clean >= cb.clean_share:
            points = CLEAN_BONUS
        brand[cid] = (points, state.turn + MONTHS)
        logs.append(
            inbox_item(
                state.turn,
                cid,
                "emissions_report",
                scope1=f"{s1:,.0f}",
                scope2=f"{s2:,.0f}",
                intensity=f"{per_m:,.0f}",
                clean=f"{clean:.0%}",
                effect=(
                    f"Consumer brands fall {-points:.1f} points for a year."
                    if points < 0
                    else "Clean energy lifts consumer brands 1 point."
                    if points > 0
                    else "No brand effect."
                ),
            )
        )
    world = replace(
        state.power_world,
        revenue_marks=tuple(sorted(marks.items())),
        brand=tuple(sorted((c, p, u) for c, (p, u) in brand.items())),
    )
    return replace(state, power_world=world), logs
