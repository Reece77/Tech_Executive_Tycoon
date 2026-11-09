"""The one place M18 reads M17 (formulas.md 33): the price deck (`commodity.deck`) a
feasibility study uses, and the suppliers (33.4, suppliers.yaml) who hold licences and buy
projects. Until M17 merged this module held a stub with the same signatures (the dossier's
2015-2025 medians); it now reads M17 directly."""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.commodities.commodity import PriceDeck, deck
from tst.sim.data_models import GameData

KG_PER_TONNE = 1000.0  # tunable-exempt: unit conversion


def usd_per_tonne(d: PriceDeck, which: str = "long_run") -> float:
    """Dollars a tonne of product from a deck (kilogram goods x 1,000)."""
    per = d.long_run_usd if which == "long_run" else d.current_usd
    return per * (KG_PER_TONNE if d.volume_unit == "kg" else 1.0)


@dataclass(frozen=True, slots=True)
class Buyer:
    key: str
    name: str
    goods: tuple[str, ...]
    region: str


def suppliers(data: GameData, turn: int | None = None) -> tuple[Buyer, ...]:
    """M17's suppliers (suppliers.yaml order) with the goods they sell; with `turn`, only the
    goods they can sell that month (a supplier's `from` and `until`)."""
    if data.suppliers is None:
        return ()
    out = []
    for s in data.suppliers.suppliers:
        goods = tuple(g for g in s.goods if turn is None or s.sells(g, turn))
        out.append(Buyer(s.key, s.name, goods, s.region))
    return tuple(out)


def buyers_of(data: GameData, commodity: str, turn: int | None = None) -> tuple[Buyer, ...]:
    """Who buys a project in a commodity (34.2): its suppliers; where none supplies it (tin,
    tantalum, high-purity quartz in M17's list), the diversified copper miners (M18 decision)."""
    every = suppliers(data, turn)
    own = tuple(s for s in every if commodity in s.goods)
    return own or tuple(s for s in every if "copper" in s.goods)


__all__ = ["Buyer", "PriceDeck", "buyers_of", "deck", "suppliers", "usd_per_tonne"]
