"""Compute units, spot prices and serving products from your own capacity (formulas.md 22.1-22.3).

- One CU is the compute a product buys for $1,000 a month at index 1.0. A product's need in
  CU is its hosting at index 1.0 (11.8, 18.6) / $1,000: **general** CU for every category but
  AI, **GPU** CU for AI (`compute_indexed`). The GPU spot price is $1,000 x M10's AI index.
- A company with no live data centre buys everything on spot: nothing here changes its costs.
- With data centres, its own products are served first: product by product (by id), the home
  region and then other regions in regions.yaml order, each from live capacity of the right
  good in the product's region or its neighbour (19.5), cheapest first. Their spot hosting falls
  by the share served.
- What is left is spare. The company's Cloud hosting product sells it (22.3): its customers'
  CU are capped by the spare in each region and its neighbour, GPU CU counting at their spot
  value in general CU. Sold CU count as used.

Every function takes a `company_id`; nothing assumes one player company (ADR-0020 1).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from fractions import Fraction

from tst.sim.data_models import Balance, CategoryDef, GameData
from tst.sim.facilities.models import Facility
from tst.sim.finance import macro
from tst.sim.geo.cities import home_region
from tst.sim.geo.models import RegionalSegment
from tst.sim.products.models import SELLING, Product, ProductSegment
from tst.sim.state import GameState

EPS = 1e-9  # tunable-exempt: float tolerance on CU


def home_region_of(state: GameState, balance: Balance, data: GameData) -> str:
    """The region of the save's home markets (`GameState.markets`): the player's HQ region
    (19.5), or the default region before M9's cities."""
    if data.cities:
        return home_region(state, balance, data)
    return balance.founder.default_region


def neighbours(data: GameData) -> dict[str, str]:
    return {m.region: m.neighbour for m in data.region_markets}


def serves(region: str, facility_region: str, data: GameData) -> bool:
    """A data centre serves its own region and the region whose neighbour it is (19.5)."""
    return facility_region == region or neighbours(data).get(region) == facility_region


def good_of(category: CategoryDef, balance: Balance) -> str:
    """The compute good a category's products need (22.1)."""
    c = balance.compute
    return c.indexed_good if category.compute_indexed else c.plain_good


def spot_unit_cents(state: GameState, good: str, balance: Balance, data: GameData) -> float:
    """One unit of a compute good a month on spot: $1,000, x the AI index for GPU (22.1)."""
    spec = balance.compute.goods[good]
    index = macro.ai_index(state, data) if spec.spot_index == "ai" else 1.0
    return spec.spot_cents * index


def is_capacity_product(product: Product, data: GameData) -> bool:
    return data.category(product.category).capacity_market


def capacity_product(state: GameState, company_id: int, data: GameData) -> Product | None:
    """The company's Cloud hosting product, if it sells capacity (one per company)."""
    for product in state.company_products(company_id):
        if product.status != "retired" and is_capacity_product(product, data):
            return product
    return None


# --- Needs ------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Need:
    """One product's compute in one region this month."""

    product_id: int
    region: str
    good: str
    units: float  # CU


def _rows(
    state: GameState, product: Product, home: str
) -> list[tuple[str, Iterable[ProductSegment | RegionalSegment]]]:
    rows: list[tuple[str, Iterable[ProductSegment | RegionalSegment]]] = [
        (home, state.segments_of(product.id))
    ]
    regions = sorted({s.region for s in state.regional_segments_of(product.id)})
    rows += [(r, state.regional_segments_of(product.id, r)) for r in regions]
    return rows


def needs(state: GameState, company_id: int, balance: Balance, data: GameData) -> list[Need]:
    """Every selling product's CU by region (22.1), by product id, home region first then
    regions.yaml order. The Cloud hosting product is not a need: what it sells is spare."""
    home = home_region_of(state, balance, data)
    order = {r: i for i, r in enumerate(data.region_keys)}
    out: list[Need] = []
    for product in state.company_products(company_id):
        if product.status not in SELLING or is_capacity_product(product, data):
            continue
        category = data.category(product.category)
        good = good_of(category, balance)
        spot = balance.compute.goods[good].spot_cents
        rows = sorted(_rows(state, product, home), key=lambda r: (r[0] != home, order.get(r[0], 0)))
        for region, segments in rows:
            units = sum(
                s.customers * category.market(s.segment).hosting_cents / spot for s in segments
            )
            if units > EPS:
                out.append(Need(product.id, region, good, units))
    return out


# --- Allocation -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Allocation:
    """Who uses a company's live capacity this month."""

    served: dict[tuple[int, str], float] = field(default_factory=dict)  # (product, region) CU
    needed: dict[tuple[int, str], float] = field(default_factory=dict)  # (product, region) CU
    own: dict[int, float] = field(default_factory=dict)  # facility id -> CU for own products
    sold: dict[int, float] = field(default_factory=dict)  # facility id -> CU sold as cloud
    capacity: dict[int, int] = field(default_factory=dict)  # facility id -> live CU
    hosted: dict[int, set[int]] = field(default_factory=dict)  # facility id -> own product ids
    sold_wanted: list[float] = field(default_factory=lambda: [0.0])  # general-CU equivalents
    sold_placed: list[float] = field(default_factory=lambda: [0.0])

    @property
    def sold_share(self) -> float:
        """The share of the Cloud hosting product's CU its own data centres serve."""
        wanted = self.sold_wanted[0]
        return min(1.0, self.sold_placed[0] / wanted) if wanted > EPS else 1.0

    def served_share(self, product_id: int, region: str) -> float:
        need = self.needed.get((product_id, region), 0.0)
        return min(1.0, self.served.get((product_id, region), 0.0) / need) if need > 0 else 0.0

    def free(self, facility_id: int) -> float:
        return max(
            0.0,
            self.capacity.get(facility_id, 0)
            - self.own.get(facility_id, 0.0)
            - self.sold.get(facility_id, 0.0),
        )

    def used(self, facility_id: int) -> float:
        return self.own.get(facility_id, 0.0) + self.sold.get(facility_id, 0.0)


def unit_cost_cents(facility: Facility, balance: Balance) -> Fraction:
    """A unit's monthly cost at full use: depreciation plus operating cost (22.2); orders
    'cheapest first'."""
    kind = balance.facility.kinds[facility.kind]
    return Fraction(facility.capex_cents, max(1, facility.capacity) * kind.life_months) + (
        kind.opex_per_unit_cents
    )


def live_facilities(state: GameState, company_id: int) -> list[Facility]:
    return [f for f in state.company_facilities(company_id) if f.live_capacity(state.turn) > 0]


def _ranked(
    facilities: list[Facility], region: str, good: str | None, balance: Balance, data: GameData
) -> list[Facility]:
    kinds = balance.facility.kinds
    eligible = [
        f
        for f in facilities
        if (good is None or kinds[f.kind].output_good == good) and serves(region, f.region, data)
    ]
    return sorted(eligible, key=lambda f: (unit_cost_cents(f, balance), f.id))


def allocate(
    state: GameState, company_id: int, balance: Balance, data: GameData, *, sold: bool = True
) -> Allocation:
    """Own products first, then the Cloud hosting product's customers (22.2, 22.3). A
    company with no live capacity gets an empty allocation."""
    facilities = live_facilities(state, company_id)
    if not facilities:
        return Allocation()
    alloc = Allocation(capacity={f.id: f.live_capacity(state.turn) for f in facilities})
    for need in needs(state, company_id, balance, data):
        key = (need.product_id, need.region)
        alloc.needed[key] = alloc.needed.get(key, 0.0) + need.units
        left = need.units
        for f in _ranked(facilities, need.region, need.good, balance, data):
            take = min(left, alloc.free(f.id))
            if take > EPS:
                alloc.own[f.id] = alloc.own.get(f.id, 0.0) + take
                alloc.served[key] = alloc.served.get(key, 0.0) + take
                alloc.hosted.setdefault(f.id, set()).add(need.product_id)
                left -= take
            if left <= EPS:
                break
    if sold:
        for region, units in sold_units(state, company_id, balance, data):
            left = _place_sold(state, alloc, facilities, region, units, balance, data)
            alloc.sold_wanted[0] += units
            alloc.sold_placed[0] += units - left
    return alloc


def equivalent(state: GameState, facility: Facility, balance: Balance, data: GameData) -> float:
    """General CU one unit of this facility's output is worth on spot (GPU at the AI index)."""
    good = balance.facility.kinds[facility.kind].output_good
    return spot_unit_cents(state, good, balance, data) / spot_unit_cents(
        state, balance.compute.plain_good, balance, data
    )


def _place_sold(
    state: GameState,
    alloc: Allocation,
    facilities: list[Facility],
    region: str,
    units: float,
    balance: Balance,
    data: GameData,
) -> float:
    """Place `units` general-CU equivalents sold in `region`; returns what did not fit."""
    left = units
    for f in _ranked(facilities, region, None, balance, data):
        worth = equivalent(state, f, balance, data)
        if worth <= 0:
            continue
        take = min(left / worth, alloc.free(f.id))
        if take > EPS:
            alloc.sold[f.id] = alloc.sold.get(f.id, 0.0) + take
            left -= take * worth
        if left <= EPS:
            break
    return max(0.0, left)


def sold_units(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> list[tuple[str, float]]:
    """(region, CU sold) of the company's Cloud hosting product, home region first."""
    product = capacity_product(state, company_id, data)
    if product is None or product.status not in SELLING:
        return []
    category = data.category(product.category)
    home = home_region_of(state, balance, data)
    order = {r: i for i, r in enumerate(data.region_keys)}
    rows = sorted(_rows(state, product, home), key=lambda r: (r[0] != home, order.get(r[0], 0)))
    return [
        (region, sum(s.customers * category.market(s.segment).units_per_customer for s in segs))
        for region, segs in rows
    ]


def spare_by_region(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> dict[str, float]:
    """The general-CU equivalents the company can sell in each region after its own products:
    regions take their turn (home first, then regions.yaml order), each capped by what its
    data centres and its neighbour's still have free, so no CU counts twice (22.3)."""
    facilities = live_facilities(state, company_id)
    alloc = allocate(state, company_id, balance, data, sold=False)
    home = home_region_of(state, balance, data)
    sold = dict(sold_units(state, company_id, balance, data))
    out: dict[str, float] = {}
    for region in [home, *(r for r in data.region_keys if r != home)]:
        out[region] = sum(
            alloc.free(f.id) * equivalent(state, f, balance, data)
            for f in _ranked(facilities, region, None, balance, data)
        )
        _place_sold(state, alloc, facilities, region, sold.get(region, 0.0), balance, data)
    return out
