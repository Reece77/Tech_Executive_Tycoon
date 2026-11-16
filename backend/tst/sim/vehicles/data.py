"""Reading vehicles.yaml for the engine (docs/formulas.md 49): whether the vehicles market runs,
the fractional year a month reads its annual points at, and the history's lookups."""

from __future__ import annotations

import math
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.products.models import Product
from tst.sim.state import GameState
from tst.sim.vehicles.config import RivalCarsDef, VehiclesFile

MONTHS: Final = 12  # tunable-exempt: calendar
MILLION: Final = 1_000_000  # tunable-exempt: car_sales are millions
HALF: Final = 0.5  # tunable-exempt: an annual value sits at the middle of its year
TINY: Final = 1e-9  # tunable-exempt: float tolerance
SHARE_EPS: Final = 1e-6  # tunable-exempt: a share's logit stays finite


def file(data: GameData) -> VehiclesFile:
    assert data.vehicles is not None
    return data.vehicles


def enabled(state: GameState, balance: Balance, data: GameData) -> bool:
    """The vehicles market runs in this save: the data has it and the save has its markets (a
    save made before M38 has none, like M12a's and M12b's markets)."""
    if data.vehicles is None:
        return False
    cat = balance.vehicles.category
    return any(m.category == cat for m in state.markets) or any(
        m.category == cat for m in state.regional_markets
    )


def in_history(turn: int, balance: Balance) -> bool:
    return turn < balance.vehicles.start_turn


def year_at(turn: int) -> float:
    """The fractional year an annual point is read at: a year's value sits at its middle, so
    January reads mostly the year before's and July its own."""
    year, month = turn_to_ym(turn)
    return year + (month - HALF) / MONTHS - HALF


def is_vehicle(product: Product, balance: Balance) -> bool:
    return product.category == balance.vehicles.category


def rival_def(state: GameState, product: Product, data: GameData) -> RivalCarsDef | None:
    """The vehicles.yaml history of an incumbent's car line (None for the player's and rivals'
    own new lines)."""
    company = state.company(product.company_id)
    if company is None or company.is_player or company.is_startup:
        return None
    return file(data).rival(company.name)


def logit(share: float) -> float:
    s = min(max(share, SHARE_EPS), 1 - SHARE_EPS)
    return math.log(s / (1 - s))


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))
