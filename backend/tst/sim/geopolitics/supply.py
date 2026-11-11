"""Buying controlled inputs (docs/formulas.md 39.3).

**Commodities.** A biting rule on a `commodity` good restricts a buyer company whose country is
one of the rule's destinations. The buyer's **exposed share** of its use of the commodity is
what comes from the actor: offtakes with suppliers sitting in the actor's jurisdiction, plus
spot volume x the actor's share of world supply (commodities.yaml `top_share` when its
`top_country` is in the actor's jurisdiction, else 0). Offtakes with suppliers elsewhere and
the group's own refined supply (M20) are not exposed. Under the strongest restricting rule:

- **allocation**: x (1 - exposed x (1 - allowed)), allowed 0 for a ban, the quota's share, or
  geopolitics.buy.licence_allowed for a licence regime (39.3: "allocation 0 (ban) or the
  quota's share");
- **price**: the exposed volume pays geopolitics.buy.premium[regime] over spot (39.3: "M17's
  prices take the shock"): a unit's cost carries `surcharge_cents`, the premium on its
  commodity lines (33.2) x exposure.

**Chip inputs.** A chip product's wafer starts are cut (`wafer_share`) by:
- an `input` good (HBM for accelerators) whose rule restricts the chip maker's country: x (1 -
  weight x (1 - allowed));
- the entity list: a company listed by an actor gets no wafers from foundries in the actor's
  jurisdiction for its controlled chips (us_components covers every chip type).

Without M22's data, or for rivals, nothing changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.data_models import Balance, GameData
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics import world
from tst.sim.geopolitics.rules import ActiveRule
from tst.sim.state import GameState

EPS = 1e-9  # tunable-exempt: float tolerance


@dataclass(frozen=True, slots=True)
class Exposure:
    good: str  # the commodity
    share: float  # exposed share of the company's use
    allowed: float  # share of the exposed volume still delivered
    premium: float  # price premium on the exposed volume
    rule_key: str | None = None

    @property
    def allocation_factor(self) -> float:
        return 1 - self.share * (1 - self.allowed)

    @property
    def price_factor(self) -> float:
        return 1 + self.share * self.premium


NONE_EXPOSED = Exposure("", 0.0, 1.0, 0.0)


def _allowed(active: ActiveRule, balance: Balance) -> float:
    regime = active.rule.regime
    if regime == "ban":
        return 0.0
    if regime == "quota":
        return active.rule.quota
    return balance.geopolitics.buy.licence_allowed


def commodity_rules(
    state: GameState, company_id: int, commodity: str, balance: Balance, data: GameData
) -> list[ActiveRule]:
    """Biting rules restricting the company's purchases of `commodity`."""
    company = state.company(company_id)
    if not world.enabled(data) or not world.in_group(state, company_id):
        return []
    country = world.company_country(state, company, balance, data)
    out = []
    for a in gr.biting(state, data):
        goods = balance.geopolitics.goods
        if not any(
            goods[g].kind == "commodity" and goods[g].commodity == commodity for g in a.rule.goods
        ):
            continue
        if country in world.destination_countries(data, a.rule, state.turn):
            out.append(a)
    return out


def actor_supply_share(data: GameData, commodity: str, actor: str, turn: int) -> float:
    """The actor's share of world supply of `commodity` (module docstring)."""
    assert data.commodities is not None
    good = data.commodities.good(commodity)
    top = world.countries_of(data).by_name(good.top_country)
    if top is not None and world.in_actor(data, actor, top.key, turn):
        return good.top_share
    return 0.0


def exposure(
    state: GameState,
    company_id: int,
    commodity: str,
    balance: Balance,
    data: GameData,
    used: float | None = None,
) -> Exposure:
    """The company's exposure on `commodity` under the strongest restricting rule."""
    restrict = commodity_rules(state, company_id, commodity, balance, data)
    if not restrict:
        return NONE_EXPOSED
    if used is None:
        from tst.sim.commodities import costs  # local: costs imports this module

        used = costs.company_use(state, company_id, balance, data).get(commodity, 0.0)
    best: Exposure | None = None
    for a in restrict:
        share = exposed_share(state, company_id, commodity, a.rule.actor, used, data)
        x = Exposure(
            commodity,
            share,
            _allowed(a, balance),
            balance.geopolitics.buy.premium[a.rule.regime],
            a.key,
        )
        if (
            best is None
            or x.allocation_factor < best.allocation_factor
            or (
                x.allocation_factor == best.allocation_factor and x.price_factor > best.price_factor
            )
        ):
            best = x
    assert best is not None
    return best


def exposed_share(
    state: GameState, company_id: int, commodity: str, actor: str, used: float, data: GameData
) -> float:
    """Volume from the actor over the company's use (module docstring)."""
    turn = state.turn
    actor_share = actor_supply_share(data, commodity, actor, turn)
    suppliers = data.suppliers
    from_actor = covered = 0.0
    for d in state.commodity_deals:
        if d.company_id != company_id or d.good != commodity or not d.running(turn):
            continue
        covered += d.monthly_volume
        if d.supplier is None:  # a contract: bought on the market
            from_actor += d.monthly_volume * actor_share
            continue
        region = next(
            (s.region for s in (suppliers.suppliers if suppliers else ()) if s.key == d.supplier),
            None,
        )
        country = world.supplier_country(data, d.supplier, region)
        if country is not None and world.in_actor(data, actor, country, turn):
            from_actor += d.monthly_volume
    covered += sum(
        s.volume
        for s in state.own_supply
        if s.buyer_id == company_id and s.good == commodity and s.turn == turn and s.fab_id is None
    )
    if used <= EPS:
        return actor_share if covered <= EPS else min(1.0, from_actor / covered)
    spot = max(0.0, used - covered)
    return min(1.0, (from_actor + spot * actor_share) / used)


def allocation_factor(
    state: GameState, company_id: int, commodity: str, used: float, balance: Balance, data: GameData
) -> float:
    return exposure(state, company_id, commodity, balance, data, used).allocation_factor


def surcharge_cents(
    state: GameState,
    company_id: int,
    cost_good: str,
    base_cents: float,
    balance: Balance,
    data: GameData,
) -> float:
    """The premium a unit of `cost_good` pays on its exposed commodities (module docstring)."""
    if not world.enabled(data) or data.commodity_history is None:
        return 0.0
    if not world.in_group(state, company_id):
        return 0.0
    from tst.sim.commodities import costs  # local: costs imports this module

    _, lines = costs.unit_lines(state, cost_good, base_cents, data, balance)
    total = 0.0
    use: dict[str, float] | None = None
    for line in lines:
        if not commodity_rules(state, company_id, line.good, balance, data):
            continue
        if use is None:
            use = costs.company_use(state, company_id, balance, data)
        x = exposure(state, company_id, line.good, balance, data, use.get(line.good, 0.0))
        total += line.cents * x.share * x.premium
    return total


def listed_by(state: GameState, company_id: int) -> tuple[str, ...]:
    return tuple(x.actor for x in state.entity_listings if x.company_id == company_id)


def wafer_share(
    state: GameState,
    company_id: int,
    chip_type: str,
    foundry: str,
    balance: Balance,
    data: GameData,
) -> float:
    """The share of a chip product's wafer starts still delivered (module docstring)."""
    if not world.enabled(data) or not world.in_group(state, company_id):
        return 1.0
    company = state.company(company_id)
    turn = state.turn
    goods = balance.geopolitics.goods
    share = 1.0
    foundry_country = world.supplier_country(data, foundry)
    for actor in listed_by(state, company_id):
        if foundry_country is not None and world.in_actor(data, actor, foundry_country, turn):
            return 0.0
    country = world.company_country(state, company, balance, data)
    for a in gr.biting(state, data):
        if country not in world.destination_countries(data, a.rule, turn):
            continue
        for g in a.rule.goods:
            spec = goods[g]
            if spec.kind == "input" and chip_type in spec.chip_types:
                share *= 1 - spec.weight * (1 - _allowed(a, balance))
    return max(0.0, share)
