"""Reading space.yaml for the engine (docs/formulas.md 56): whether the space markets run, the
history's lookups and the categories' keys."""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.products.models import Product
from tst.sim.space.config import SpaceFile
from tst.sim.state import CompanyState, GameState
from tst.sim.vehicles.data import year_at

MONTHS: Final = 12  # tunable-exempt: calendar
THOUSAND: Final = 1_000  # tunable-exempt: subscribers are thousands
TINY: Final = 1e-9  # tunable-exempt: float tolerance
LAST_YEAR: Final = 2025  # tunable-exempt: space.yaml's last data year

__all__ = ["year_at"]


def file(data: GameData) -> SpaceFile:
    assert data.space is not None
    return data.space


def enabled(state: GameState, balance: Balance, data: GameData) -> bool:
    """The space markets run in this save: the data has them and the save has the launch market
    (a save made before M40 has none, like M38's vehicles and M39's robots)."""
    if data.space is None:
        return False
    cat = balance.space.launch
    return any(m.category == cat for m in state.markets) or any(
        m.category == cat for m in state.regional_markets
    )


def in_history(turn: int, balance: Balance) -> bool:
    return turn < balance.space.start_turn


def is_launch(product: Product, balance: Balance) -> bool:
    return product.category == balance.space.launch


def is_broadband(product: Product, balance: Balance) -> bool:
    return product.category == balance.space.broadband


def is_eo(product: Product, balance: Balance) -> bool:
    return product.category == balance.space.eo


def is_space(product: Product, balance: Balance) -> bool:
    return product.category in (balance.space.launch, balance.space.broadband, balance.space.eo)


def space_categories(balance: Balance) -> tuple[str, str, str]:
    sb = balance.space
    return (sb.launch, sb.broadband, sb.eo)


def is_space_rival(company: CompanyState, data: GameData) -> bool:
    """A space incumbent (a launch provider or a constellation's operator in space.yaml)."""
    if data.space is None:
        return False
    f = file(data)
    return f.launch.provider(company.name) is not None or any(
        c.company == company.name for c in f.constellations
    )
