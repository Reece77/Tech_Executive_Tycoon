"""Tariffs and local partners' shares (docs/formulas.md 39.3).

**Tariffs.** After the month's production is booked (phase 5), each of the player group's
unit-sale products pays, for every tariffs.yaml schedule covering its good (devices, servers,
chips: geopolitics.tariff_goods), `rate x cost per unit x units made in the schedule's origin
and sold in its market`:

- **made in**: assembled units in their contract's city's country (contract manufacturing)
  or the company's plants' countries (by units run); chips in their foundries' countries (by
  wafer starts);
- **sold in**: the product's customers by region, each region's split by its countries'
  demand shares.

The tax posts to 5100 tariffs (cost of revenue) against cash. Inside a group the transfer
price carries it (M16): it stays in the seller's cost of goods.

**Local partners** (39.3: cloud in China, 50% local): a company with a local partner pays it
`local_partner.share` of its revenue from the partner market each month (5110 against cash).
"""

from __future__ import annotations

from tst.sim.data_models import Balance, GameData
from tst.sim.geo.cities import home_region
from tst.sim.geopolitics import world
from tst.sim.ledger import CASH, LOCAL_PARTNER_SHARE, TARIFFS, LedgerEntry, LedgerLine
from tst.sim.products.models import Product
from tst.sim.state import GameState

EPS = 1e-9  # tunable-exempt: float tolerance on units


def good_of(product: Product, balance: Balance) -> str | None:
    for good, cats in balance.geopolitics.tariff_goods.items():
        if product.category in cats:
            return good
    return None


def sold_in(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> dict[str, float]:
    """country -> the share of the product's customers there."""
    by_region: dict[str, float] = {}
    if data.cities:
        home = home_region(state, balance, data)
        by_region[home] = sum(s.customers for s in state.segments_of(product.id))
    for r in state.regional_segments_of(product.id):
        by_region[r.region] = by_region.get(r.region, 0.0) + r.customers
    total = sum(by_region.values())
    out: dict[str, float] = {}
    if total <= EPS:
        return out
    for region, n in by_region.items():
        for c in world.countries_of(data).of_region(region):
            out[c.key] = out.get(c.key, 0.0) + n / total * c.demand_share
    return out


def made_in(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> dict[str, float]:
    """country -> the share of the month's units made there."""
    row = next((r for r in state.production if r.product_id == product.id), None)
    if row is None or row.units <= EPS:
        return {}
    out: dict[str, float] = {}
    turn = state.turn
    if data.category(product.category).chip_type is not None:
        wafers = [
            c
            for c in state.production_contracts
            if c.product_id == product.id and c.kind == "wafer" and c.running(turn)
        ]
        total = sum(c.units for c in wafers)
        for c in wafers:
            country = world.supplier_country(data, c.supplier) or ""
            out[country] = out.get(country, 0.0) + c.units / max(EPS, total)
        return out
    units = row.plant_units + row.contract_units
    if units <= EPS:
        return {}
    contracts = [
        c
        for c in state.production_contracts
        if c.product_id == product.id and c.kind == "assembly" and c.running(turn)
    ]
    used = sum(c.used for c in contracts)
    for c in contracts:
        country = (
            world.city_country(data, c.city)
            if c.city
            else world.supplier_country(data, c.supplier) or ""
        )
        weight = c.used / used if used > EPS else 1 / len(contracts)
        out[country] = out.get(country, 0.0) + row.contract_units / units * weight
    plants = [
        f
        for f in state.facilities
        if f.company_id == product.company_id and f.kind == balance.hardware.plant_kind
    ]
    run = sum(f.run_units for f in plants)
    for f in plants:
        weight = f.run_units / run if run > EPS else 1 / len(plants)
        country = world.facility_country(state, f, data)
        out[country] = out.get(country, 0.0) + row.plant_units / units * weight
    return out


def rate(data: GameData, origin: str, market: str, good: str, turn: int) -> float:
    """The summed tariff rate on `good` made in `origin` and sold in `market` this month."""
    assert data.tariffs is not None
    total = 0.0
    for t in data.tariffs.schedules:
        if good not in t.goods:
            continue
        if world.in_actor(data, t.origin, origin, turn) and world.in_actor(
            data, t.market, market, turn
        ):
            total += t.rate_at(turn)
    return total


def product_tariff_cents(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> int:
    good = good_of(product, balance)
    row = next((r for r in state.production if r.product_id == product.id), None)
    if good is None or row is None or row.units <= EPS or row.cogs_cents <= 0:
        return 0
    made = made_in(state, product, balance, data)
    sold = sold_in(state, product, balance, data)
    share = sum(
        m * s * rate(data, origin, market, good, state.turn)
        for origin, m in made.items()
        if origin
        for market, s in sold.items()
    )
    return round(share * row.cogs_cents)


def tariffs_month(state: GameState, balance: Balance, data: GameData) -> list[LedgerEntry]:
    if not world.enabled(data) or data.tariffs is None or not state.production:
        return []
    entries = []
    for company in world.group(state):
        for product in state.company_products(company.id):
            cents = product_tariff_cents(state, product, balance, data)
            if cents > 0:
                d = product.division_id
                entries.append(
                    LedgerEntry(
                        turn=state.turn,
                        company_id=company.id,
                        memo=f"Tariffs: {product.name}",
                        lines=(LedgerLine(TARIFFS, cents, d), LedgerLine(CASH, -cents, d)),
                    )
                )
    return entries


def region_revenue_cents(state: GameState, product: Product, region: str, home: str | None) -> int:
    """The product's monthly revenue in a region: customers x price, its segments summed."""
    rows: list[tuple[float, int | None]] = [
        (r.customers, r.price_cents) for r in state.regional_segments_of(product.id, region)
    ]
    if region == home:
        rows += [(s.customers, s.price_cents) for s in state.segments_of(product.id)]
    return round(sum(n * (p or 0) for n, p in rows))


def partner_month(state: GameState, balance: Balance, data: GameData) -> list[LedgerEntry]:
    """The local partner's share (module docstring), after the month's markets."""
    if not world.enabled(data):
        return []
    lp = balance.geopolitics.local_partner
    entries = []
    for site in state.sites:
        if site.kind != "company" or not site.local_partner or site.country not in lp.countries:
            continue
        region = world.countries_of(data).country(site.country).region
        share = world.countries_of(data).country(site.country).demand_share
        company = state.company(site.id)
        home = home_region(state, balance, data) if data.cities else None
        total = sum(
            region_revenue_cents(state, p, region, home)
            for p in state.company_products(company.id)
            if p.category in lp.categories
        )
        cents = round(total * share * lp.share)
        if cents > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company.id,
                    memo="Local partner's share",
                    debit=LOCAL_PARTNER_SHARE,
                    credit=CASH,
                    amount=cents,
                )
            )
    return entries
