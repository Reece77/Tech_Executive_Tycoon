"""The telecom markets' history to 2025 (docs/formulas.md 62.5 target 1), set after demand each
month before `telecom.start` (phase 9, and at a new game); a dated opening (Jio's launch, Vodafone
Idea's merger) is also pinned before phase 5's markets, so a line sells in its opening month (M43r):

- **Operators:** a line's customers in a region's segment are its operator's subscribers there
  (telecom.yaml, millions, real) x 10^6 x `telecom.scale` x the segment's split (mobile and fixed),
  or its wholesale share x the market (wholesale), at most the market not held by other companies'
  lines; no price before its `first` month or from its `last`.
- **Vendors:** a network-equipment line's customers are its vendor's share of the RAN market that
  year (x its `region_mult`) x the market not held by others, less the share bans exclude it from.

Rivals do not decide before `telecom.start` (`rivals.holds`). From it nothing here runs but the
openings and closings of lines whose dates fall after 2025.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.geo.models import RegionalSegment
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import GameState, with_segments
from tst.sim.telecom.config import OperatorDef, VendorDef
from tst.sim.telecom.data import MILLION, TINY, end_year_at, file, in_history


def _regions(product: Product, state: GameState, data: GameData) -> tuple[str, ...]:
    company = state.company(product.company_id)
    spec = next((c for c in data.incumbents if company and c.name == company.name), None)
    if spec is None:
        return ()
    line = next((x for x in spec.products if x.name == product.name), None)
    return line.regions or () if line is not None else ()


def _base_price(state: GameState, product: Product, segment: str, data: GameData) -> int | None:
    company = state.company(product.company_id)
    spec = next((c for c in data.incumbents if company and c.name == company.name), None)
    if spec is None:
        return None
    line = next((x for x in spec.products if x.name == product.name), None)
    if line is None or segment not in line.segments:
        return None
    return line.segments[segment].price_cents


def lines(
    state: GameState, balance: Balance, data: GameData
) -> list[tuple[Product, OperatorDef | VendorDef]]:
    """Every incumbent telecom line with its operator (by its listed region) or vendor."""
    f = file(data)
    cats = balance.telecom.categories
    out: list[tuple[Product, OperatorDef | VendorDef]] = []
    for p in state.products:
        if p.category not in cats or p.status == "retired":
            continue
        company = state.company(p.company_id)
        if company is None or company.is_player or company.is_startup:
            continue
        if p.category == balance.telecom.equipment:
            v = f.vendor_of(company.name)
            if v is not None:
                out.append((p, v))
            continue
        regions = _regions(p, state, data)
        op = f.operator(company.name, regions[0]) if regions else None
        if op is not None:
            out.append((p, op))
    return out


def _share(
    source: OperatorDef | VendorDef,
    product: Product,
    region: str,
    segment: str,
    free: float,
    year: float,
    state: GameState,
    balance: Balance,
    data: GameData,
) -> float:
    tb = balance.telecom
    if isinstance(source, VendorDef):
        from tst.sim.telecom.equipment import banned_new_share

        share = source.share_at(year, region)
        return share * (1.0 - banned_new_share(state, region, source.key, data)) * free
    if product.category == tb.wholesale:
        return source.wholesale_at(year) * free
    if product.category == tb.mobile:
        subs = source.mobile_at(year) * tb.mobile_split.get(segment, 0.0)
    else:
        subs = source.fixed_at(year) * tb.fixed_split.get(segment, 0.0)
    return min(free, subs * MILLION * tb.scale)


def pin(
    state: GameState, balance: Balance, data: GameData, *, openings_only: bool = False
) -> GameState:
    """Module docstring. Before `telecom.start` every rule; from it only the openings' and
    closings' prices. `openings_only` (phase 5, before the markets): only the rows whose price
    this month's date opens, pinned as phase 9 would pin them."""
    history = in_history(state.turn, balance)
    found = lines(state, balance, data)
    if not found:
        return state
    tb = balance.telecom
    year = end_year_at(state.turn)
    home = home_region_of(state, balance, data)
    demand: dict[tuple[str, str, str], float] = {}
    for m in state.markets:
        demand[(m.category, home, m.segment)] = m.addressable
    for rm in state.regional_markets:
        demand[(rm.category, rm.region, rm.segment)] = rm.addressable
    mine = {p.id for p, _ in found}
    others: dict[tuple[str, str, str], float] = {}
    if history:
        for p in state.products:
            if p.category not in tb.categories or p.id in mine or p.status == "retired":
                continue
            for s in state.segments_of(p.id):
                k = (p.category, home, s.segment)
                others[k] = others.get(k, 0.0) + s.customers
            for rs in state.regional_segments_of(p.id):
                k = (p.category, rs.region, rs.segment)
                others[k] = others.get(k, 0.0) + rs.customers
    rows: list[ProductSegment] = []
    regional: list[RegionalSegment] = []
    for product, source in sorted(found, key=lambda x: x[0].id):
        active = source.active(state.turn) if isinstance(source, OperatorDef) else True
        pairs: list[tuple[ProductSegment | RegionalSegment, str]] = [
            *((s, home) for s in state.segments_of(product.id)),
            *((rs, rs.region) for rs in state.regional_segments_of(product.id)),
        ]
        for seg_row, region in pairs:
            price = _base_price(state, product, seg_row.segment, data) if active else None
            if openings_only and (price is None or seg_row.price_cents is not None):
                continue
            customers = seg_row.customers
            if history:
                k = (product.category, region, seg_row.segment)
                free = max(0.0, demand.get(k, 0.0) - others.get(k, 0.0))
                target = _share(
                    source, product, region, seg_row.segment, free, year, state, balance, data
                )
                customers = 0.0 if price is None else target
            elif price is None:
                customers = 0.0
            elif seg_row.price_cents is not None:
                continue  # open and priced: the rival's own decisions from telecom.start
            if price != seg_row.price_cents or abs(customers - seg_row.customers) > TINY:
                if isinstance(seg_row, RegionalSegment):
                    regional.append(replace(seg_row, price_cents=price, customers=customers))
                else:
                    rows.append(replace(seg_row, price_cents=price, customers=customers))
    if not rows and not regional:
        return state
    return with_segments(state, rows, regional)
