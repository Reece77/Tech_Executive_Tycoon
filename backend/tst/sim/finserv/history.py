"""The finance markets' history to 2025 (docs/formulas.md 64.6 target 1), set after demand each
month before `finserv.start` (phase 9, and at a new game):

- **Banks, acquirers, insurers:** a line's customers in its region's segment are its company's
  share of that market (finance_services.yaml rivals, interpolated by year) x the market, at most
  the market not held by other companies' lines; none from its `last` month (Silicon Valley Bank,
  March 2023).
- **Card networks:** a line's card programmes in each region are its network's share of the
  region's card volume x the market.

From `finserv.start` nothing here runs: rivals decide like every incumbent.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.finserv.config import FinRivalDef, NetworkDef
from tst.sim.finserv.data import TINY, in_history, rival_def, year_at
from tst.sim.geo.models import RegionalSegment
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import GameState, with_segments


def lines(
    state: GameState, balance: Balance, data: GameData
) -> list[tuple[Product, FinRivalDef | NetworkDef]]:
    """Every incumbent finance line with its rival or network row."""
    cats = balance.finserv.categories
    out: list[tuple[Product, FinRivalDef | NetworkDef]] = []
    for p in state.products:
        if p.category not in cats or p.status == "retired":
            continue
        company = state.company(p.company_id)
        if company is None or company.is_player or company.is_startup:
            continue
        spec = rival_def(company, data)
        if spec is not None:
            out.append((p, spec))
    return out


def _base_price(state: GameState, product: Product, segment: str, data: GameData) -> int | None:
    company = state.company(product.company_id)
    spec = next((c for c in data.incumbents if company and c.name == company.name), None)
    if spec is None:
        return None
    line = next((x for x in spec.products if x.name == product.name), None)
    if line is None or segment not in line.segments:
        return None
    return line.segments[segment].price_cents


def _target(source: FinRivalDef | NetworkDef, region: str, segment: str, year: float) -> float:
    if isinstance(source, NetworkDef):
        return source.share_at(region, year)
    if source.region != region:
        return 0.0
    if source.segments is not None and segment not in source.segments:
        return 0.0
    return source.share_at(year)


def pin(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Module docstring: before `finserv.start` only."""
    if not in_history(state.turn, balance):
        return state
    found = lines(state, balance, data)
    if not found:
        return state
    cats = balance.finserv.categories
    year = year_at(state.turn)
    home = home_region_of(state, balance, data)
    demand: dict[tuple[str, str, str], float] = {}
    for m in state.markets:
        if m.category in cats:
            demand[(m.category, home, m.segment)] = m.addressable
    for rm in state.regional_markets:
        if rm.category in cats:
            demand[(rm.category, rm.region, rm.segment)] = rm.addressable
    mine = {p.id for p, _ in found}
    others: dict[tuple[str, str, str], float] = {}
    for p in state.products:
        if p.category not in cats or p.id in mine or p.status == "retired":
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
        last = source.last_turn if isinstance(source, FinRivalDef) else None
        active = last is None or state.turn < last
        pairs: list[tuple[ProductSegment | RegionalSegment, str]] = [
            *((s, home) for s in state.segments_of(product.id)),
            *((rs, rs.region) for rs in state.regional_segments_of(product.id)),
        ]
        for seg_row, region in pairs:
            price = _base_price(state, product, seg_row.segment, data) if active else None
            k = (product.category, region, seg_row.segment)
            free = max(0.0, demand.get(k, 0.0) - others.get(k, 0.0))
            share = _target(source, region, seg_row.segment, year)
            customers = 0.0 if price is None else min(free, share * demand.get(k, 0.0))
            if price != seg_row.price_cents or abs(customers - seg_row.customers) > TINY:
                if isinstance(seg_row, RegionalSegment):
                    regional.append(replace(seg_row, price_cents=price, customers=customers))
                else:
                    rows.append(replace(seg_row, price_cents=price, customers=customers))
    if not rows and not regional:
        return state
    return with_segments(state, rows, regional)
