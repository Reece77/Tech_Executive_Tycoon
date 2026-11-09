"""The one place M18 reads M17 (lane A): the price deck (formulas.md 33, `commodity.deck`) and
the suppliers who hold licences and buy projects (33.4).

**Stub until M17 merges** (M18 brief, Lane): `deck` has M17's signature and returns the
dossier's 2015-2025 medians (dossier 1.1) as both the current price and the long-run level;
`suppliers` lists M17's suppliers.yaml miners by key, name and goods. At the merge both are
replaced by M17's `commodity.deck` and `data.suppliers`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.state import GameState


@dataclass(frozen=True, slots=True)
class PriceDeck:
    """M17's PriceDeck (tst.sim.commodities.commodity): the current price and the long-run
    level, in the good's unit and in dollars a volume unit."""

    key: str
    unit: str
    volume_unit: str
    current: float
    long_run: float
    current_usd: float
    long_run_usd: float


# Dossier 1.1, the median of 2015-2025 (D: the median of the table's eleven values), in the
# unit M17 uses, with dollars a volume unit. High-purity quartz has no series: M17's USGS
# midpoint ($8,250/t, dossier 1.2).
_MEDIANS: Final[dict[str, tuple[str, str, float, float]]] = {
    "copper": ("¢/lb", "t", 296.0, 22.046),
    "tin": ("$/t", "t", 20145.0, 1.0),
    "tantalum": ("$/kg Ta2O5", "kg", 180.0, 1.0),
    "cobalt": ("$/lb", "t", 17.2, 2204.6),
    "lithium_carbonate": ("$/t", "t", 11800.0, 1.0),
    "ndpr_oxide": ("$/kg", "kg", 50.0, 1.0),
    "quartz_hp": ("$/t", "t", 8250.0, 1.0),
}


def deck(state: GameState, key: str, data: GameData, balance: Balance) -> PriceDeck:
    """M17's `commodity.deck(state, key, data, balance)` (stub: dossier medians)."""
    unit, volume, price, usd = _MEDIANS[key]
    return PriceDeck(key, unit, volume, price, price, price * usd, price * usd)


def usd_per_tonne(d: PriceDeck, which: str = "long_run") -> float:
    """Dollars a tonne of product from a deck (kilogram goods x 1,000)."""
    per = d.long_run_usd if which == "long_run" else d.current_usd
    return per * (1000.0 if d.volume_unit == "kg" else 1.0)


@dataclass(frozen=True, slots=True)
class Buyer:
    key: str
    name: str
    goods: tuple[str, ...]


# M17's suppliers.yaml (branch m17-commodities): the miners and their goods, in file order.
_SUPPLIERS: Final = (
    Buyer("freeport", "Freeport-McMoRan", ("copper", "cobalt")),
    Buyer("bhp", "BHP Billiton", ("copper",)),
    Buyer("rio_tinto", "Rio Tinto", ("copper", "lithium_carbonate")),
    Buyer("glencore", "Glencore", ("copper", "cobalt")),
    Buyer("codelco", "Codelco", ("copper",)),
    Buyer("albemarle", "Albemarle", ("lithium_carbonate",)),
    Buyer("sqm", "SQM", ("lithium_carbonate",)),
    Buyer("lynas", "Lynas", ("ndpr_oxide",)),
    Buyer("molycorp", "Molycorp", ("ndpr_oxide",)),
    Buyer("mp_materials", "MP Materials", ("ndpr_oxide",)),
    Buyer("umicore", "Umicore", ("cobalt", "germanium")),
    Buyer("china_northern_re", "China Northern Rare Earth", ("ndpr_oxide",)),
)


def suppliers(data: GameData) -> tuple[Buyer, ...]:
    """Every supplier with its goods (stub: M17's list)."""
    return _SUPPLIERS


def buyers_of(data: GameData, commodity: str) -> tuple[Buyer, ...]:
    """Who buys a project in a commodity (34.2): its suppliers; where none supplies it (tin,
    tantalum, high-purity quartz in M17's list), the diversified copper miners (M18 decision)."""
    own = tuple(s for s in suppliers(data) if commodity in s.goods)
    return own or tuple(s for s in suppliers(data) if "copper" in s.goods)
