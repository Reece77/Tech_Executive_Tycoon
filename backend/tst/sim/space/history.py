"""The space markets' history to 2025 (docs/formulas.md 56.4 target 1), set after demand each month
before `space.start` (phase 9, and at a new game); a dated opening (a first launch, a service,
D2D) is also pinned before phase 5's markets, so it sells in its opening month (M43r):

- **Launch:** each provider's customers in a region's segment are its share of the year's world
  launches (space.yaml) x the market not held by other companies' lines; no price before its
  first orbital launch.
- **Broadband and Earth observation:** an operator's subscribers are its constellation's
  (space.yaml, thousands, real) x `space.scale`, split over its segments by
  `space.history_split` and over regions by their addressable markets, at most the market not
  held by others; no price before its service opens. Direct-to-device has no price before
  `d2d.open`. EO operators hold `history_share` of the market.

Rivals do not decide before `space.start` (`rivals.holds`). Nothing here runs from it, but the
D2D and service openings, which can still fall after 2025 (Kuiper's service).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.geo.formulas import regional_price_cents
from tst.sim.geo.models import RegionalSegment
from tst.sim.products.models import Product, ProductSegment
from tst.sim.space.config import ConstellationDef
from tst.sim.space.data import THOUSAND, TINY, file, in_history, space_categories, year_at
from tst.sim.state import GameState, with_segments


def _lines(state: GameState, balance: Balance, data: GameData) -> list[tuple[Product, str]]:
    cats = space_categories(balance)
    out = []
    names = set()
    f = file(data)
    names = {p.company for p in f.launch.providers} | {c.company for c in f.constellations}
    for p in state.products:
        if p.category not in cats or p.status == "retired":
            continue
        company = state.company(p.company_id)
        if company is None or company.is_player or company.is_startup:
            continue
        if company.name in names:
            out.append((p, company.name))
    return out


def _base_price(state: GameState, product: Product, segment: str, data: GameData) -> int | None:
    company = state.company(product.company_id)
    spec = next((c for c in data.incumbents if company and c.name == company.name), None)
    if spec is None:
        return None
    line = next((x for x in spec.products if x.category == product.category), None)
    if line is None or segment not in line.segments:
        return None
    return line.segments[segment].price_cents


def _price(
    state: GameState,
    product: Product,
    segment: str,
    region: str,
    company: str,
    balance: Balance,
    data: GameData,
) -> int | None:
    """The line's data price, or None before it may sell (module docstring)."""
    f = file(data)
    turn = state.turn
    sb = balance.space
    if product.category == sb.launch:
        p = f.launch.provider(company)
        if p is not None and p.first_turn is not None and turn < p.first_turn:
            return None
    else:
        kind = "eo" if product.category == sb.eo else "broadband"
        c = f.constellation_of(company, kind)
        if c is not None and turn < c.service_turn:
            return None
        if (
            product.category == sb.broadband
            and segment == sb.d2d_segment
            and (turn < f.d2d.open_turn or c is None or not c.d2d)
        ):
            return None
    base = _base_price(state, product, segment, data)
    if base is None:
        return None
    home = home_region_of(state, balance, data)
    return base if region == home else regional_price_cents(base, region, home, data)


def _target(
    c: ConstellationDef | None,
    segment: str,
    region: str,
    weights: dict[str, float],
    year: float,
    balance: Balance,
) -> float | None:
    if c is None:
        return None
    split = balance.space.history_split.get(segment, 0.0)
    return (
        c.subscribers_at(year) * THOUSAND * balance.space.scale * split * weights.get(region, 0.0)
    )


def pin(
    state: GameState, balance: Balance, data: GameData, *, openings_only: bool = False
) -> GameState:
    """Module docstring. Before `space.start` every rule; from it only the openings' prices.
    `openings_only` (phase 5, before the markets; M43r, Codex review 9 finding 11): only the
    rows whose price this month's date opens, pinned as phase 9 would pin them, so a service
    sells in its opening month."""
    history = in_history(state.turn, balance)
    lines = _lines(state, balance, data)
    if not lines:
        return state
    f = file(data)
    sb = balance.space
    year = year_at(state.turn)
    home = home_region_of(state, balance, data)
    demand: dict[tuple[str, str, str], float] = {}
    for m in state.markets:
        demand[(m.category, home, m.segment)] = m.addressable
    for rm in state.regional_markets:
        demand[(rm.category, rm.region, rm.segment)] = rm.addressable
    others: dict[tuple[str, str, str], float] = {}
    mine = {p.id for p, _ in lines}
    cats = space_categories(balance)
    if history:
        for p in state.products:
            if p.category not in cats or p.id in mine or p.status == "retired":
                continue
            for s in state.segments_of(p.id):
                k = (p.category, home, s.segment)
                others[k] = others.get(k, 0.0) + s.customers
            for rs in state.regional_segments_of(p.id):
                k = (p.category, rs.region, rs.segment)
                others[k] = others.get(k, 0.0) + rs.customers
    world = f.launch.world_at(year)
    region_weights: dict[str, dict[str, float]] = {}

    def weights(category: str, segment: str) -> dict[str, float]:
        key = f"{category}/{segment}"
        if key not in region_weights:
            w = {r: v for (c, r, s), v in demand.items() if c == category and s == segment}
            total = sum(w.values())
            region_weights[key] = {r: v / total for r, v in w.items()} if total > TINY else {}
        return region_weights[key]

    rows: list[ProductSegment] = []
    regional: list[RegionalSegment] = []
    for product, company in sorted(lines, key=lambda x: x[0].id):
        kind = "eo" if product.category == sb.eo else "broadband"
        c = f.constellation_of(company, kind)
        provider = f.launch.provider(company)
        pairs: list[tuple[ProductSegment | RegionalSegment, str]] = [
            *((s, home) for s in state.segments_of(product.id)),
            *((rs, rs.region) for rs in state.regional_segments_of(product.id)),
        ]
        for seg_row, region in pairs:
            price = _price(state, product, seg_row.segment, region, company, balance, data)
            if openings_only and (price is None or seg_row.price_cents is not None):
                continue
            customers = seg_row.customers
            if history:
                k = (product.category, region, seg_row.segment)
                free = max(0.0, demand.get(k, 0.0) - others.get(k, 0.0))
                if product.category == sb.launch:
                    share = provider.launches_at(year) / world if provider and world > 0 else 0.0
                    target = share * free
                elif product.category == sb.eo:
                    target = sb.history_share.get(company, 0.0) * free
                else:
                    t = _target(
                        c,
                        seg_row.segment,
                        region,
                        weights(product.category, seg_row.segment),
                        year,
                        balance,
                    )
                    target = min(free, t) if t is not None else 0.0
                customers = 0.0 if price is None else target
            elif price is None:
                customers = 0.0
            elif seg_row.price_cents is not None:
                continue  # open and priced: the rival's own decisions from space.start
            if price != seg_row.price_cents or abs(customers - seg_row.customers) > TINY:
                if isinstance(seg_row, RegionalSegment):
                    regional.append(replace(seg_row, price_cents=price, customers=customers))
                else:
                    rows.append(replace(seg_row, price_cents=price, customers=customers))
    if not rows and not regional:
        return state
    return with_segments(state, rows, regional)
