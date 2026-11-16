"""Power-purchase agreements (docs/formulas.md 46.2): a fixed price for a fixed volume a month
for 5-20 years from a named generator in the region (power.yaml's producers, or the region's other
generators), at the forward price less a term discount. Take-or-pay on the untaken volume
(`power.ppa.take_or_pay`, 33.3's 70%), settled each month (tst.sim.power.settle). Termination is
M23a's (tst.sim.contracts.termination, kind `ppa`): the remaining months' minimum discounted, plus
the break penalty.

The forward price is half this month's grid price and half the region's long-run grid price (its
2010-2019 mean index x the reference), as M18's and M28's outlooks blend spot and the long run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.power import formulas as pf
from tst.sim.power import grid
from tst.sim.power.models import Ppa
from tst.sim.state import GameState

MONTHS: Final = 12  # tunable-exempt: calendar
SPOT_WEIGHT: Final = 0.5  # tunable-exempt: the forward's blend, as world.outlook_spot_weight
OTHER_PREFIX: Final = "other_"  # tunable-exempt: the region's other generators: other_<region>


@dataclass(frozen=True, slots=True)
class Seller:
    key: str
    name: str


def sellers(data: GameData, region: str) -> list[Seller]:
    """The generators a company can sign with in `region`: the named producers whose country is
    in the region, then the region's other generators."""
    assert data.power is not None and data.countries is not None
    out = [
        Seller(p.key, p.name)
        for p in data.power.producers
        if data.countries.country(p.country).region == region
    ]
    out.append(Seller(f"{OTHER_PREFIX}{region}", f"{data.region(region).label} generators"))
    return out


def seller(data: GameData, region: str, key: str) -> Seller | None:
    return next((s for s in sellers(data, region) if s.key == key), None)


def long_run_cents(region: str, balance: Balance, data: GameData) -> float:
    ref = balance.refining.power_cents_per_mwh
    if data.power_history is None:
        return float(ref)
    return ref * data.power_history.region(region).mean_2010_2019


def forward_cents(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """The forward price a MWh (module docstring)."""
    spot = grid.price_cents(state, region, balance, data)
    return SPOT_WEIGHT * spot + (1 - SPOT_WEIGHT) * long_run_cents(region, balance, data)


@dataclass(frozen=True, slots=True)
class PpaQuote:
    region: str
    producer: str
    producer_name: str
    mwh_month: float
    years: int
    price_cents: float  # a MWh
    forward_cents: float
    start_turn: int
    end_turn: int
    monthly_cents: int  # the full volume a month at the price
    minimum_cents: int  # the take-or-pay minimum a month


def quote(
    state: GameState,
    region: str,
    producer: str,
    mwh_month: float,
    years: int,
    balance: Balance,
    data: GameData,
) -> PpaQuote:
    pb = balance.power.ppa
    s = seller(data, region, producer)
    fwd = forward_cents(state, region, balance, data)
    price = pf.ppa_price(fwd, years, pb.discount_per_year, pb.max_discount)
    start = state.turn + 1
    return PpaQuote(
        region=region,
        producer=producer,
        producer_name=s.name if s else producer,
        mwh_month=mwh_month,
        years=years,
        price_cents=price,
        forward_cents=fwd,
        start_turn=start,
        end_turn=start + years * MONTHS - 1,
        monthly_cents=round(mwh_month * price),
        minimum_cents=round(mwh_month * price * pb.take_or_pay),
    )


def regional_demand(
    state: GameState, company_id: int, region: str, balance: Balance, data: GameData
) -> float:
    """The company's energy in `region` a month, MWh: its latest power month, or its live data
    centres' and fabs' draw at full capacity if that is more (a save before its first metered
    month)."""
    from tst.sim.power import demand

    months = [m for m in state.power_months if m.company_id == company_id and m.region == region]
    metered = max(months, key=lambda m: m.turn).demand_mwh if months else 0.0
    draw = sum(
        demand.facility_mw(state, f, balance, data)
        for f in state.facilities
        if f.company_id == company_id and f.region == region and f.status == "live"
    )
    return max(metered, draw * balance.power.hours_a_month)


def next_id(state: GameState) -> int:
    return max((p.id for p in state.ppas), default=0) + 1


def from_quote(state: GameState, company_id: int, q: PpaQuote) -> Ppa:
    return Ppa(
        id=next_id(state),
        company_id=company_id,
        region=q.region,
        producer=q.producer,
        mwh_month=q.mwh_month,
        price_cents=q.price_cents,
        signed_turn=state.turn,
        start_turn=q.start_turn,
        end_turn=q.end_turn,
    )


def end_month(state: GameState) -> GameState:
    """PPAs past their last month end (status `ended`)."""
    from dataclasses import replace

    changed = tuple(
        replace(p, status="ended") if p.status == "active" and state.turn > p.end_turn else p
        for p in state.ppas
    )
    return state if changed == state.ppas else replace(state, ppas=changed)
