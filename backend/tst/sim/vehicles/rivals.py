"""Rival car makers (docs/formulas.md 49.1, 49.5).

- **History holds:** before `vehicles.start` the incumbent car makers do not decide (rivals'
  month skips them, `holds`); their customers follow the data (`demand.pin`).
- **From `vehicles.start`** they decide by 15.3's rules and personality like every incumbent, and
  each December a maker refreshes its line with `rival_refresh` (stream vehicles (3, *rival key)):
  quality and its held feature score rise `rival_refresh_points` (at most 95 and 100).
- **Tariffs bite:** a car maker does not enter a region where a vehicles tariff on its origin into
  the region's largest market is at least `tariff_block` (`blocked_region`).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.rng import RngFactory
from tst.sim.state import CompanyState, GameState, with_product
from tst.sim.vehicles import draws
from tst.sim.vehicles.data import file, is_vehicle

DECEMBER: Final = 12  # tunable-exempt: calendar
QUALITY_CAP: Final = 95.0  # tunable-exempt: a refresh's ceilings
FEATURE_CAP: Final = 100.0  # tunable-exempt


def is_car_maker(company: CompanyState, data: GameData) -> bool:
    return data.vehicles is not None and file(data).rival(company.name) is not None


def holds(state: GameState, company: CompanyState, balance: Balance, data: GameData) -> bool:
    """Before vehicles.start a car maker does not decide (history holds)."""
    return state.turn < balance.vehicles.start_turn and is_car_maker(company, data)


def blocked_region(
    state: GameState, company: CompanyState, region: str, balance: Balance, data: GameData
) -> bool:
    """A car maker stays out of a region whose vehicles tariff on its origin is high (49.6 target
    5)."""
    if data.vehicles is None or data.tariffs is None or data.countries is None:
        return False
    rival = file(data).rival(company.name)
    if rival is None:
        return False
    markets = [c for c in data.countries.countries if c.region == region]
    if not markets:
        return False
    top = max(markets, key=lambda c: c.demand_share)
    for s in data.tariffs.schedules:
        if (
            "vehicles" in s.goods
            and s.origin == rival.origin
            and s.market == top.key
            and s.rate_at(state.turn) >= balance.vehicles.tariff_block
        ):
            return True
    return False


def december_refresh(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> GameState:
    vb = balance.vehicles
    if state.turn < vb.start_turn or turn_to_ym(state.turn)[1] != DECEMBER:
        return state
    for company in state.rivals():
        if not is_car_maker(company, data) or not company.rival_key:
            continue
        u = float(draws.gen(rng, state.turn, draws.RIVAL, *company.rival_key).random())
        if u >= vb.rival_refresh:
            continue
        for p in state.company_products(company.id):
            if not is_vehicle(p, balance) or p.status != "live":
                continue
            held = p.held_feature
            new = replace(
                p,
                quality=min(QUALITY_CAP, p.quality + vb.rival_refresh_points),
                held_feature=min(FEATURE_CAP, held + vb.rival_refresh_points)
                if held is not None
                else None,
            )
            state = with_product(state, new)
    return state
