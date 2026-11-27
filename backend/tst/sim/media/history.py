"""The media markets' history to 2025 (docs/formulas.md 65.7, 65.8 target 1), set after demand each
month before `media.start` (phase 9, and at a new game); a dated opening (Disney+, Peacock) is also
pinned before phase 5's markets, so a line sells in its opening month (M43r):

- **Customers:** a line's customers in a region are its worldwide customers (media.yaml, millions)
  x 10^6 x `media.scale` x its split there; a games line's are its revenue there / (12 x its price
  there) x scale; at most the market not held by other companies' lines.
- **Prices:** the line's North American price (incumbents.yaml) x the category's price index in
  the region; a social line's is media.yaml's ad revenue a user there (`arpu_usd`, a year / 12) x
  its `arpu_mult`. No price before its `first` month or from its `last`.

Rivals do not decide before `media.start` (`rivals.holds`). From it nothing here runs but the
openings and closings of lines dated after 2025; a social line's price is the ad market's (65.1).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.geo.models import RegionalSegment
from tst.sim.media.config import BILLION, MILLION, LineDef
from tst.sim.media.data import MONTHS, TINY, end_year_at, file, in_history
from tst.sim.media.demand import price_index
from tst.sim.products.models import Product, ProductSegment
from tst.sim.state import GameState, with_segments
from tst.sim.vehicles.config import interp


def _spec_price(state: GameState, product: Product, data: GameData) -> int | None:
    company = state.company(product.company_id)
    spec = next((c for c in data.incumbents if company and c.name == company.name), None)
    if spec is None:
        return None
    line = next((x for x in spec.products if x.name == product.name), None)
    if line is None or not line.segments:
        return None
    return next(iter(line.segments.values())).price_cents


def lines(state: GameState, balance: Balance, data: GameData) -> list[tuple[Product, LineDef]]:
    """Every incumbent media line with its media.yaml row."""
    f = file(data)
    cats = balance.media.categories
    out: list[tuple[Product, LineDef]] = []
    for p in state.products:
        if p.category not in cats or p.status == "retired":
            continue
        company = state.company(p.company_id)
        if company is None or company.is_player or company.is_startup:
            continue
        row = f.line(company.name, p.name)
        if row is not None:
            out.append((p, row))
    return out


def social_history_price(row: LineDef, region: str, year: float, data: GameData) -> int:
    """A social line's price in the history: the region's ad revenue a user a month (media.yaml
    arpu_usd / 12) x the line's arpu_mult."""
    arpu = interp(file(data).arpu_cents[region], year)
    return max(1, round(arpu / MONTHS * row.arpu_mult))  # money-exact: rate


def line_price(
    product: Product,
    row: LineDef,
    region: str,
    year: float,
    state: GameState,
    balance: Balance,
    data: GameData,
) -> int | None:
    """The line's price in a region (module docstring), or None when it is not on sale."""
    if not row.active(state.turn):
        return None
    if row.category == balance.media.social:
        return social_history_price(row, region, year, data)
    base = _spec_price(state, product, data)
    if base is None:
        return None
    return max(1, round(base * price_index(row.category, region, data)))  # money-exact: rate


def target(row: LineDef, region: str, price: int, year: float, balance: Balance) -> float:
    """The line's customers in a region from the data (module docstring)."""
    share = row.share(year, region)
    if row.revenue_cents:
        revenue = interp(row.revenue_cents, year) * BILLION * share
        # money-exact: ratio (customers: revenue over a customer's spend)
        return revenue / (MONTHS * price) * balance.media.scale
    return interp(row.customers, year) * MILLION * balance.media.scale * share


def pin(
    state: GameState, balance: Balance, data: GameData, *, openings_only: bool = False
) -> GameState:
    """Module docstring. Before `media.start` every rule; from it only the openings' and
    closings' prices. `openings_only` (phase 5, before the markets): only the rows whose price
    this month's date opens."""
    history = in_history(state.turn, balance)
    found = lines(state, balance, data)
    if not found:
        return state
    cats = balance.media.categories
    year = end_year_at(state.turn)
    home = home_region_of(state, balance, data)
    demand: dict[tuple[str, str], float] = {}
    for m in state.markets:
        if m.category in cats:
            demand[(m.category, home)] = m.addressable
    for rm in state.regional_markets:
        if rm.category in cats:
            demand[(rm.category, rm.region)] = rm.addressable
    mine = {p.id for p, _ in found}
    others: dict[tuple[str, str], float] = {}
    if history:
        for p in state.products:
            if p.category not in cats or p.id in mine or p.status == "retired":
                continue
            for s in state.segments_of(p.id):
                k = (p.category, home)
                others[k] = others.get(k, 0.0) + s.customers
            for rs in state.regional_segments_of(p.id):
                k = (p.category, rs.region)
                others[k] = others.get(k, 0.0) + rs.customers
    rows: list[ProductSegment] = []
    regional: list[RegionalSegment] = []
    for product, row in sorted(found, key=lambda x: x[0].id):
        pairs: list[tuple[ProductSegment | RegionalSegment, str]] = [
            *((s, home) for s in state.segments_of(product.id)),
            *((rs, rs.region) for rs in state.regional_segments_of(product.id)),
        ]
        for seg_row, region in pairs:
            price = line_price(product, row, region, year, state, balance, data)
            if openings_only and (price is None or seg_row.price_cents is not None):
                continue
            customers = seg_row.customers
            if history:
                free = max(
                    0.0,
                    demand.get((product.category, region), 0.0)
                    - others.get((product.category, region), 0.0),
                )
                customers = (
                    0.0 if price is None else min(free, target(row, region, price, year, balance))
                )
            elif price is None:
                customers = 0.0
            elif seg_row.price_cents is not None:
                continue  # open and priced: the rival's own decisions (and the ad market's)
            if price != seg_row.price_cents or abs(customers - seg_row.customers) > TINY:
                if isinstance(seg_row, RegionalSegment):
                    regional.append(replace(seg_row, price_cents=price, customers=customers))
                else:
                    rows.append(replace(seg_row, price_cents=price, customers=customers))
    if not rows and not regional:
        return state
    return with_segments(state, rows, regional)
