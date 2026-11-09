"""What a plant would cost to run (docs/formulas.md 36.1), for the Build dialog, `tst recipe` and
the Refineries screen: a unit's cost at full output with this month's input price and the
region's power index, against the output's market price. Staff salaries are left out (they
depend on whom the player hires); depreciation is the quoted capex over the kind's life.
"""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities import lifecycle
from tst.sim.refining import formulas as rf
from tst.sim.refining import goods as rg
from tst.sim.refining.plants import power_index, process_level
from tst.sim.state import GameState

MONTHS = 12  # tunable-exempt: calendar


@dataclass(frozen=True, slots=True)
class UnitEstimate:
    recipe: str
    region: str
    power_index: float
    yield_: float  # the effective yield for the company (36.3)
    input_cents: float  # a unit's input
    power_cents: float
    other_cents: float
    fixed_cents: float
    depreciation_cents: float
    unit_cost_cents: float
    market_cents: float

    @property
    def margin(self) -> float:
        return rf.margin(self.market_cents, self.unit_cost_cents)


def estimate(
    state: GameState,
    company_id: int,
    recipe: str,
    region: str,
    balance: Balance,
    data: GameData,
    capacity: int | None = None,
) -> UnitEstimate:
    rb = balance.refining
    r = rb.recipes[recipe]
    kind = balance.facility.kinds[r.kind]
    size = capacity or (kind.sizes or balance.facility.sizes)[0]
    q = lifecycle.quote(state, company_id, r.kind, region, size, balance, data)
    level = process_level(state, company_id, balance, data) if r.semi_grade else 0.0
    eff = rf.effective_yield(r.yield_, r.semi_grade, level, rb.semi_min_level, rb.semi_low_yield)
    per_in = rf.input_per_output(r.input_per_output, r.yield_, eff)
    input_cents = (
        rg.price_cents(state, r.input_good, balance, data) * per_in if r.input_good else 0.0
    )
    index = power_index(state, region, data)
    power = rf.power_cents(r.mwh_per_unit, rb.power_cents_per_mwh, index)
    out_year = size * r.per_capacity_unit * eff / r.yield_
    fixed = size * r.fixed_cents / out_year if out_year else 0.0
    dep = q.capex_cents / (kind.life_months / MONTHS) / out_year if out_year else 0.0
    unit = input_cents + power + r.other_cents + fixed + dep
    return UnitEstimate(
        recipe=recipe,
        region=region,
        power_index=index,
        yield_=eff,
        input_cents=input_cents,
        power_cents=power,
        other_cents=float(r.other_cents),
        fixed_cents=fixed,
        depreciation_cents=dep,
        unit_cost_cents=unit,
        market_cents=rg.price_cents(state, r.output_good, balance, data),
    )
