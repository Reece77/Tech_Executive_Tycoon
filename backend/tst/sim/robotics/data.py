"""Reading robotics.yaml for the engine (docs/formulas.md 53): whether the robotics markets run,
the history's lookups and the categories' keys."""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.products.models import Product
from tst.sim.robotics.config import RoboticsFile
from tst.sim.state import CompanyState, GameState
from tst.sim.vehicles.data import year_at

THOUSAND: Final = 1_000  # tunable-exempt: installations are thousands
MILLION: Final = 1_000_000  # tunable-exempt: workers and trips are millions
MONTHS: Final = 12  # tunable-exempt: calendar
WEEKS_PER_MONTH: Final = 52 / 12  # tunable-exempt: calendar
TINY: Final = 1e-9  # tunable-exempt: float tolerance

__all__ = ["year_at"]


def file(data: GameData) -> RoboticsFile:
    assert data.robotics is not None
    return data.robotics


def enabled(state: GameState, balance: Balance, data: GameData) -> bool:
    """The robotics markets run in this save: the data has them and the save has the industrial
    robots market (a save made before M39 has none, like M38's vehicles)."""
    if data.robotics is None:
        return False
    cat = balance.robotics.industrial
    return any(m.category == cat for m in state.markets) or any(
        m.category == cat for m in state.regional_markets
    )


def in_history(turn: int, balance: Balance) -> bool:
    return turn < balance.robotics.start_turn


def is_industrial(product: Product, balance: Balance) -> bool:
    return product.category == balance.robotics.industrial


def is_humanoid(product: Product, balance: Balance) -> bool:
    return product.category == balance.robotics.humanoid


def is_mobility(product: Product, balance: Balance) -> bool:
    return product.category == balance.robotics.mobility


def is_robot(product: Product, balance: Balance) -> bool:
    return is_industrial(product, balance) or is_humanoid(product, balance)


def is_robot_maker(company: CompanyState, data: GameData) -> bool:
    if data.robotics is None:
        return False
    f = file(data)
    return f.maker(company.name) is not None or f.humanoid_maker(company.name) is not None


def era_turn(state: GameState, data: GameData) -> int | None:
    """The month the humanoid era arrived (None before)."""
    if data.robotics is None:
        return None
    arrival = state.era_arrival(file(data).humanoids.era)
    return None if arrival is None else arrival.turn
