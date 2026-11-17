"""Purchase subsidies and their sourcing rules (docs/formulas.md 49.5).

A scheme pays the buyer `amount` (2010 dollars) for an eligible car in its country, from each of
its steps' months to the next, so a region's average subsidy a buyer is the sum over its schemes
of `amount x the country's demand share of the region` (countries.yaml). A car is eligible when
its price in the region is at most the scheme's cap, it is made where a `made_in` rule asks, and
no running rule excludes its cells' country (or bloc). The data's schemes run to their ends (the
US credit ended 30 September 2025); after the history no new scheme is drawn (a follow-up).

A car's **cell origin** is its cell maker's country; a design on the group's own cells takes the
group's cell plants' countries (any one excluded excludes it), and the market's (China) if the
group has none. Its **assembly origin** is its live vehicle plants' countries, else its running
contracts' cities' countries, else its design's `origin`.
"""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.config import month_to_turn
from tst.sim.geopolitics import world
from tst.sim.products.models import Product
from tst.sim.state import GameState, group_companies
from tst.sim.vehicles.config import OWN, SubsidyDef
from tst.sim.vehicles.data import file, rival_def

MARKET_ORIGIN: Final = "china"  # tunable-exempt: where market cells come from when unnamed (49.2)


def country_share(country: str, data: GameData) -> float:
    place = data.places.place(country) if data.places is not None else None
    return place.demand_share if place is not None else 0.0


def _matches(country: str, names: tuple[str, ...], data: GameData) -> bool:
    if country in names:
        return True
    if data.countries is None:
        return False
    c = next((x for x in data.countries.countries if x.key == country), None)
    return c is not None and c.bloc in names


def cell_countries(state: GameState, product: Product, data: GameData) -> tuple[str, ...]:
    rival = rival_def(state, product, data)
    v = file(data)
    if rival is not None:
        return (v.cell_maker(rival.cells).country,)
    spec = state.vehicle_spec(product.id)
    cells = spec.cells if spec is not None else v.cell_makers[0].key
    if cells != OWN:
        return (v.cell_maker(cells).country,)
    group = {c.id for c in group_companies(state, product.company_id)}
    out = sorted(
        {
            world.facility_country(state, f, data)
            for cp in state.cell_plants
            if cp.company_id in group and (f := state.facility(cp.facility_id)) is not None
        }
    )
    return tuple(out) or (MARKET_ORIGIN,)


def made_countries(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> tuple[str, ...]:
    rival = rival_def(state, product, data)
    if rival is not None:
        return (rival.origin,)
    kind = balance.vehicles.plant.kind
    plants = sorted(
        {
            world.facility_country(state, f, data)
            for f in state.company_facilities(product.company_id)
            if f.kind == kind and f.live_capacity(state.turn) > 0
        }
    )
    if plants:
        return tuple(plants)
    contracts = sorted(
        {
            world.city_country(data, c.city)
            for c in state.production_contracts
            if c.product_id == product.id
            and c.kind == "assembly"
            and c.running(state.turn)
            and c.city
        }
    )
    if contracts:
        return tuple(contracts)
    spec = state.vehicle_spec(product.id)
    return (spec.origin,) if spec is not None and spec.origin else ()


def rules_failed(
    state: GameState,
    product: Product,
    scheme: SubsidyDef,
    price_cents: int,
    balance: Balance,
    data: GameData,
) -> tuple[str, ...]:
    """The labels of the scheme's rules (and its price cap) the car fails this month."""
    out: list[str] = []
    cap = scheme.cap_at(state.turn)
    if cap > 0 and price_cents > cap:
        out.append("Price above the cap")
    for rule in scheme.rules:
        if month_to_turn(rule.start) > state.turn:
            continue
        if rule.cells_not_from and any(
            _matches(c, rule.cells_not_from, data) for c in cell_countries(state, product, data)
        ):
            out.append(rule.label)
        if rule.made_in and not any(
            c in rule.made_in for c in made_countries(state, product, balance, data)
        ):
            out.append(rule.label)
    return tuple(out)


def schemes_in(state: GameState, region: str, data: GameData) -> list[SubsidyDef]:
    return [s for s in file(data).subsidies if s.region == region and s.amount_at(state.turn) > 0]


def region_amount(state: GameState, region: str, data: GameData) -> float:
    """The region's average subsidy a buyer for a car eligible everywhere (cents)."""
    return sum(
        s.amount_at(state.turn) * country_share(s.country, data)
        for s in schemes_in(state, region, data)
    )


def product_cut(
    state: GameState,
    product: Product,
    region: str,
    price_cents: int,
    balance: Balance,
    data: GameData,
) -> float:
    """What the region's subsidies take off a buyer's price for the product, on average over the
    region's buyers (cents)."""
    total = 0.0
    for s in schemes_in(state, region, data):
        if not rules_failed(state, product, s, price_cents, balance, data):
            total += s.amount_at(state.turn) * country_share(s.country, data)
    return total


def eligibility(
    state: GameState,
    product: Product,
    region: str,
    price_cents: int,
    balance: Balance,
    data: GameData,
) -> list[tuple[str, int, tuple[str, ...]]]:
    """(scheme title, amount cents, failed rules) for each running scheme in the region: what the
    product page shows."""
    return [
        (
            s.title,
            round(s.amount_at(state.turn)),
            rules_failed(state, product, s, price_cents, balance, data),
        )
        for s in schemes_in(state, region, data)
    ]
