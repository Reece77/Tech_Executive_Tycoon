"""What commodities cost the player (docs/formulas.md 33.2).

- A cost good with a mix in `commodity.mixes` (device and server bills of materials, foundry
  wafers) is priced with its commodities at spot: a **blend** index `(1 - w) x its own index +
  w x the mix's index` (BOMs), or a **scale** `its price x ((1 - v) + v x the mix's index)`
  (wafers). The mix's index is the weighted sum of its commodities' indexes.
- **Use.** A unit's commodity spend at index 1.0 is its base cost x the share x the weight; its
  use of a commodity is that spend over the commodity's 2010-2019 mean price in dollars a
  volume unit. A device or server uses its BOM's mix; a chip its wafer's (one wafer for
  `per_wafer x yield` chips). Contracts and offtakes settle against this use (offtake.py).
- **Allocation.** In a shortage spot buyers get the good's allocation; volume covered by a
  contract signed before the shortage, or a prepaid offtake, gets 100%. A product's units are
  capped at its mix's weighted allocation (partial substitution and stocks, M17 decision).

A company without unit-sale products never reaches this module: nothing changes for software.
"""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.commodities import commodity
from tst.sim.commodities.config import CommodityMix
from tst.sim.commodities.models import CommodityDeal
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities import goods
from tst.sim.state import GameState

CENTS = 100  # tunable-exempt: cents a dollar
EPS = 1e-9  # tunable-exempt: float tolerance on wafers


def mix_of(good: str, balance: Balance) -> CommodityMix | None:
    return balance.commodity.mixes.get(good)


def mix_index(state: GameState, mix: CommodityMix, data: GameData) -> float:
    """The mix's index: its commodities' spot indexes, weighted (33.2)."""
    return sum(w * commodity.index_now(state, g, data) for g, w in mix.weights.items())


def apply_mix(own_index: float, mix: CommodityMix, mix_value: float) -> float:
    """33.2: blend for BOMs, scale for wafers."""
    if mix.mode == "scale":
        return own_index * ((1 - mix.share) + mix.share * mix_value)
    return (1 - mix.share) * own_index + mix.share * mix_value


def cost_index(state: GameState, good: str, data: GameData, balance: Balance) -> float:
    """A cost good's index with its commodities at spot (33.2); M12a's index for a good
    without a mix (or when M17's data is not loaded)."""
    own = goods.index_now(state, good, data)
    mix = mix_of(good, balance)
    if mix is None or data.commodity_history is None:
        return own
    return apply_mix(own, mix, mix_index(state, mix, data))


@dataclass(frozen=True, slots=True)
class CostLine:
    """One commodity's part of a unit's cost (33.2: the product cost breakdown)."""

    good: str
    weight: float
    index: float
    cents: float  # this commodity's cost in one unit at spot


def unit_lines(
    state: GameState, good: str, base_cents: float, data: GameData, balance: Balance
) -> tuple[float, list[CostLine]]:
    """A unit's cost of `good` at `base_cents` (index 1.0) split into its own part and each
    commodity's line, at spot. For a blend, the own part is `(1 - w) x index x base`; for a
    scale, `index x base x (1 - v)`, each commodity's line its weighted share of the rest."""
    own = goods.index_now(state, good, data)
    mix = mix_of(good, balance)
    if mix is None or data.commodity_history is None:
        return own * base_cents, []
    lead = own if mix.mode == "scale" else 1.0
    lines = []
    for g, w in mix.weights.items():
        idx = commodity.index_now(state, g, data)
        lines.append(CostLine(g, w, idx, base_cents * lead * mix.share * w * idx))
    return own * base_cents * (1 - mix.share), lines


def use_per_unit(base_cents: float, mix: CommodityMix, data: GameData) -> dict[str, float]:
    """Volume units of each commodity one unit of the cost good uses (module docstring)."""
    assert data.commodities is not None
    out: dict[str, float] = {}
    for g, w in mix.weights.items():
        usd_mean = commodity.mean_of(data, g) * data.commodities.good(g).usd_per_unit
        out[g] = base_cents * mix.share * w / (usd_mean * CENTS)
    return out


def company_use(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> dict[str, float]:
    """The company's commodity use in the state's production month (volume units)."""
    from tst.sim.chips import chips  # local: chips imports the cost index

    use: dict[str, float] = {}
    hw, ch = balance.hardware, balance.chips
    for row in state.production:
        if row.company_id != company_id:
            continue
        product = state.product(row.product_id)
        if product is None:
            continue
        if chips.is_chip(product, data):
            mix = mix_of(ch.good, balance)
            if mix is None:
                continue
            t = chips.type_of(product, data, balance)
            y = chips.chip_yield(state, company_id, balance, data)
            wafers = (row.units + row.internal_units) / max(EPS, t.per_wafer * y)
            per = use_per_unit(t.wafer_cents, mix, data)
            for g, q in per.items():
                use[g] = use.get(g, 0.0) + wafers * q
            continue
        bom = hw.bom.get(product.category)
        mix = mix_of(bom.good, balance) if bom else None
        if bom is None or mix is None:
            continue
        for g, q in use_per_unit(bom.base_cents, mix, data).items():
            use[g] = use.get(g, 0.0) + row.units * q
    return use


def protected(deal: CommodityDeal, start: int | None) -> bool:
    """A deal's volume keeps 100% allocation: a prepaid offtake, or one signed before the
    running shortage began (33.3, as M12a's contracts)."""
    if deal.kind == "offtake" and deal.prepaid_cents > 0:
        return True
    return start is not None and deal.signed_turn < start


def shortage_start(state: GameState, good: str, data: GameData) -> int | None:
    month = commodity.current(state, good, data)
    if month.allocation >= 1:
        return None
    return month.shock_turn


def allocation_for(
    state: GameState, company_id: int, good: str, used: float, data: GameData
) -> float:
    """The company's allocation of a commodity this month: protected deals' share of its use
    (`used`: last month's, volume units) at 100%, the rest at the good's allocation (33.1,
    33.3)."""
    month = commodity.current(state, good, data)
    if month.allocation >= 1:
        return 1.0
    start = month.shock_turn
    covered = sum(
        d.monthly_volume
        for d in state.commodity_deals
        if d.company_id == company_id
        and d.good == good
        and d.running(state.turn)
        and protected(d, start)
    ) + sum(  # M20 (36.1): the group's own refined supply this month is protected
        s.volume
        for s in state.own_supply
        if s.buyer_id == company_id
        and s.good == good
        and s.turn == state.turn
        and s.product_id is None
    )
    share = min(1.0, covered / used) if covered and used > 0 else (1.0 if covered else 0.0)
    return share + (1 - share) * month.allocation


def product_allocation(
    state: GameState,
    company_id: int,
    cost_good: str,
    use: dict[str, float],
    balance: Balance,
    data: GameData,
) -> float:
    """A product's units are capped at its mix's weighted allocation (module docstring);
    `use` is the company's last month's use (`company_use` before this month's production)."""
    mix = mix_of(cost_good, balance)
    if mix is None or data.commodity_history is None:
        return 1.0
    return sum(
        w * allocation_for(state, company_id, g, use.get(g, 0.0), data)
        for g, w in mix.weights.items()
    )
