"""The vehicles market's demand and its history (docs/formulas.md 49.1).

**Addressable customers.** For a region and segment, each month (phase 9, and at a new game):

    D = new cars a year (vehicles.yaml, millions) x the segment's share x the EV share
        x vehicles.scale x replacement_months / 12 / units_per_customer

so that a month's replacements (`D / replacement_months` customers) are about a month's EV
sales at the game's scale. The EV share is the data's to December 2025; from `vehicles.start` a
region's share follows its logit, which rises `k_eff / 12` a month (`world_month`):

    k_eff = max(floor_k, k x (1 + battery x (1 - cell price / its 2025 price)
                               + charging x coverage + subsidy x subsidy / reference price))

with `k` drawn per region at `vehicles.start` (stream vehicles (0, region_index)), and the share
capped at `s_curve.cap`. New car sales hold at their last data point.

**History holds** (49.6 target 1). Before `vehicles.start` every incumbent car maker's customers in
a region's segment are its data share of the market not held by other companies' lines
(`D - others`), set each month after demand (`pin`); rivals do not decide (rivals' month skips
them) and their lines sell from their launch month (a line not yet launched has no price).
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.geo.formulas import regional_price_cents
from tst.sim.products.models import MarketSegment, Product
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_all_markets, with_segments
from tst.sim.vehicles import draws
from tst.sim.vehicles.data import (
    MILLION,
    MONTHS,
    TINY,
    file,
    in_history,
    is_vehicle,
    logit,
    rival_def,
    sigmoid,
    year_at,
)


def ev_share(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """The region's EV share of new car sales this month (49.1)."""
    turn = state.turn
    if in_history(turn, balance):
        return file(data).region(region).share_at(year_at(turn))
    lg = state.vehicle_world.logit_of(region)
    if lg is None:
        start = balance.vehicles.start_turn
        return file(data).region(region).share_at(year_at(start - 1))
    return min(balance.vehicles.s_curve.cap, sigmoid(lg))


def car_sales(region: str, turn: int, data: GameData) -> float:
    """New cars a year in the region, real world."""
    return file(data).region(region).sales_at(year_at(turn)) * MILLION


def addressable(
    state: GameState, region: str, segment: str, balance: Balance, data: GameData
) -> float:
    vb = balance.vehicles
    r = file(data).region(region)
    market = data.category(vb.category).market(segment)
    months = market.replacement_months or MONTHS
    yearly = car_sales(region, state.turn, data) * r.segments[segment] * vb.scale
    return (
        yearly
        * ev_share(state, region, balance, data)
        * months
        / MONTHS
        / (market.units_per_customer)
    )


def ev_sales_year(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """EV sales a year in the region at the game's scale, in cars (all segments)."""
    yearly = car_sales(region, state.turn, data) * balance.vehicles.scale
    return yearly * ev_share(state, region, balance, data)


def set_demand(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Every vehicles market's addressable customers this month (module docstring)."""
    cat = balance.vehicles.category
    home = home_region_of(state, balance, data)
    markets: list[MarketSegment] = []
    for m in state.markets:
        if m.category == cat:
            m = replace(m, addressable=addressable(state, home, m.segment, balance, data))
        markets.append(m)
    regional = []
    for rm in state.regional_markets:
        if rm.category == cat:
            rm = replace(rm, addressable=addressable(state, rm.region, rm.segment, balance, data))
        regional.append(rm)
    return with_all_markets(state, markets, regional)


# --- History: rivals' shares, prices and launches -------------------------------------------------


def rival_price(
    state: GameState,
    product: Product,
    segment: str,
    region: str,
    balance: Balance,
    data: GameData,
) -> int | None:
    """An incumbent car line's price in a region (incumbents.yaml's price at home, x the region's
    price index elsewhere, as M9's incumbents), or None before its launch."""
    company = state.company(product.company_id)
    spec = next((c for c in data.incumbents if c.name == company.name), None) if company else None
    rival = rival_def(state, product, data)
    if spec is None or rival is None or state.turn < rival.launch_turn:
        return None
    line = next((p for p in spec.products if p.category == product.category), None)
    if line is None or segment not in line.segments:
        return None
    home = home_region_of(state, balance, data)
    base = line.segments[segment].price_cents
    if region == home:
        return base
    return regional_price_cents(base, region, home, data)  # x the region's index (19.5)


def pin(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Before `vehicles.start`: each incumbent car line's customers are its data share of the
    market not held by other companies' lines, and its price is set from its launch (module
    docstring). Nothing changes from `vehicles.start`."""
    if not in_history(state.turn, balance):
        return state
    cat = balance.vehicles.category
    year = year_at(state.turn)
    home = home_region_of(state, balance, data)
    lines = [p for p in state.products if is_vehicle(p, balance) and p.status != "retired"]
    rivals = {p.id: d for p in lines if (d := rival_def(state, p, data)) is not None}
    # customers of everyone else's lines, by (region, segment)
    others: dict[tuple[str, str], float] = {}
    for p in lines:
        if p.id in rivals:
            continue
        for s in state.segments_of(p.id):
            others[(home, s.segment)] = others.get((home, s.segment), 0.0) + s.customers
        for rs in state.regional_segments_of(p.id):
            key = (rs.region, rs.segment)
            others[key] = others.get(key, 0.0) + rs.customers
    demand = {(home, m.segment): m.addressable for m in state.markets if m.category == cat}
    demand.update(
        {(m.region, m.segment): m.addressable for m in state.regional_markets if m.category == cat}
    )
    home_rows = []
    regional_rows = []
    for pid, rival in sorted(rivals.items()):
        product = state.product(pid)
        assert product is not None
        for s in state.segments_of(pid):
            free = max(0.0, demand.get((home, s.segment), 0.0) - others.get((home, s.segment), 0))
            price = rival_price(state, product, s.segment, home, balance, data)
            home_rows.append(
                replace(
                    s, customers=rival.share_at(home, year, state.turn) * free, price_cents=price
                )
            )
        for rs in state.regional_segments_of(pid):
            key = (rs.region, rs.segment)
            free = max(0.0, demand.get(key, 0.0) - others.get(key, 0.0))
            price = rival_price(state, product, rs.segment, rs.region, balance, data)
            regional_rows.append(
                replace(
                    rs,
                    customers=rival.share_at(rs.region, year, state.turn) * free,
                    price_cents=price,
                )
            )
    return with_segments(state, home_rows, regional_rows)


# --- After the history: the EV share's path -------------------------------------------------------


def world_month(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """From `vehicles.start` (phase 9): each region's logit moves `k_eff / 12`. In December 2025
    the logits begin at that month's shares and each region's `k` and the learning rate are
    drawn (keyed by `vehicles.start`)."""
    vb = balance.vehicles
    turn = state.turn
    if turn < vb.start_turn - 1:
        return state
    world = state.vehicle_world
    if not world.logit:  # December 2025's phase 9, so January's cell price has its curve
        from tst.sim.vehicles import cells

        logits = []
        ks = []
        for i, region in enumerate(data.region_keys):
            share = file(data).region(region).share_at(year_at(vb.start_turn - 1))
            logits.append((region, logit(share)))
            u = float(draws.gen(rng, vb.start_turn, draws.WORLD, i).random())
            ks.append((region, vb.s_curve.k.lo + (vb.s_curve.k.hi - vb.s_curve.k.lo) * u))
        u = float(draws.gen(rng, vb.start_turn, draws.WORLD, len(data.region_keys)).random())
        rate = vb.learning.rate.lo + (vb.learning.rate.hi - vb.learning.rate.lo) * u
        base = cells.history_cumulative_gwh(data)
        world = replace(
            world,
            logit=tuple(logits),
            k=tuple(ks),
            learning_rate=rate,
            cumulative_gwh=base,
            base_cumulative_gwh=base,
        )
        return replace(state, vehicle_world=world)
    if turn < vb.start_turn:
        return state
    sc = vb.s_curve
    out = []
    for region, lg in world.logit:
        k = world.k_of(region) or 0.0
        drive = 1 + sc.battery * battery_drop(state, balance, data)
        drive += sc.charging * coverage(state, region, balance, data)
        drive += sc.subsidy * subsidy_share(state, region, balance, data)
        k_eff = max(sc.floor_k, k * drive)
        out.append((region, min(logit(sc.cap), lg + k_eff / MONTHS)))
    # cumulative cells: the world's EV cell demand grows with EV sales after 2025
    from tst.sim.vehicles import cells

    gwh = cells.year_gwh(state, balance, data) / MONTHS
    world = replace(world, logit=tuple(out), cumulative_gwh=world.cumulative_gwh + gwh)
    return replace(state, vehicle_world=world)


def battery_drop(state: GameState, balance: Balance, data: GameData) -> float:
    """1 - this month's cell price over December 2025's (0 before)."""
    from tst.sim.vehicles import cells

    base = cells.history_cell_cents(balance.vehicles.start_turn - 1, data)
    now = cells.market_cents(state, balance, data)
    return max(0.0, 1 - now / base) if base > TINY else 0.0


def coverage(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """A region's charging coverage, 0-1: public chargers (the data's, then growing with the EV
    stock, plus the companies' own networks) per EV sold a year, over `charging.coverage_ref`."""
    from tst.sim.vehicles import charging

    sales = ev_sales_year(state, region, balance, data) / balance.vehicles.scale
    if sales <= TINY:
        return 0.0
    chargers = charging.public_chargers(state, region, balance, data)
    return min(1.0, chargers / sales / balance.vehicles.charging.coverage_ref)


def subsidy_share(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """The region's subsidies this month as a share of the consumer reference price (weighted by
    their countries' demand shares)."""
    from tst.sim.vehicles import subsidies

    ref = data.category(balance.vehicles.category).market("consumer").reference_price_cents
    return subsidies.region_amount(state, region, data) / ref if ref else 0.0
