"""The robot markets' demand and their history (docs/formulas.md 53.1-53.2).

**Industrial robots.** For a region and buyer industry, each month (phase 9, and at a new game):

    D = installations a year (robotics.yaml, real) x the segment's share x robotics.scale
        x replacement_months / 12 / units_per_customer

so a month's replacements (`D / replacement_months` customers) are about a month's
installations at the game's scale. Installations are the data's to 2025; from `robotics.start`
a region's grow each year by a rate drawn in `growth_after` (stream robotics (0, region_index,
year)), drawn a year ahead so the mid-year interpolation always has its next point.

**Humanoids** (53.2). Closed (D = 0) until the humanoid era arrives. Then for a region:

    D = workers in the segment x cap x sigmoid(logit) x robotics.scale x replacement_months / 12

with the adoption logit starting at logit(seed / cap) and rising `k_eff / 12` a month,
`k_eff = max(floor_k, adoption_k x (value - 1))`, where value = the best humanoid's capability
/ 100 x a worker's labour cost a year in the region / a humanoid's cost a year (its price over
its life plus service): adoption is fastest where labour is dear. Homes (the consumer segment)
open at a seeded month `home_window` years after the arrival (stream robotics (0, n_regions)).

**History holds** (53.4 target 1). Before `robotics.start` every industrial robot maker's
customers in a region's segment are its data share of the market not held by other companies'
lines (`D - others`), set each month after demand (`pin`); robot makers do not decide
(`rivals.holds`). Humanoid makers have no price before the era arrives.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.geo.formulas import regional_price_cents
from tst.sim.geo.models import RegionalSegment
from tst.sim.products.models import MarketSegment, Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.robotics import draws
from tst.sim.robotics.data import (
    MILLION,
    MONTHS,
    THOUSAND,
    TINY,
    era_turn,
    file,
    in_history,
    is_humanoid,
    is_industrial,
    year_at,
)
from tst.sim.robotics.models import RoboticsWorld
from tst.sim.state import GameState, with_all_markets, with_segments
from tst.sim.vehicles.data import logit, sigmoid

LAST_YEAR = 2025  # tunable-exempt: robotics.yaml's last data year
HOME = "consumer"  # tunable-exempt: the humanoid market's home segment


def _start_year(balance: Balance) -> int:
    return turn_to_ym(balance.robotics.start_turn)[0]


def installations(state: GameState, region: str, balance: Balance, data: GameData) -> float:
    """Industrial robots installed a year in the region this month, real world."""
    r = file(data).region(region)
    t = year_at(state.turn)
    if in_history(state.turn, balance) or t <= LAST_YEAR:
        return r.installed_at(t) * THOUSAND
    level = {LAST_YEAR: r.installed_at(LAST_YEAR)}
    year = LAST_YEAR
    while year < t:
        g = state.robotics_world.growth_of(region, year + 1)
        level[year + 1] = level[year] * (1 + (g if g is not None else 0.0))
        year += 1
    lo = int(t)
    frac = t - lo
    a = level.get(lo, level[year])
    b = level.get(lo + 1, a)
    return (a + (b - a) * frac) * THOUSAND


def industrial_addressable(
    state: GameState, region: str, segment: str, balance: Balance, data: GameData
) -> float:
    rb = balance.robotics
    market = data.category(rb.industrial).market(segment)
    months = market.replacement_months or MONTHS
    share = file(data).region(region).segments[segment]
    yearly = installations(state, region, balance, data) * share * rb.scale
    return yearly * months / MONTHS / market.units_per_customer


def adoption_share(state: GameState, region: str, balance: Balance) -> float:
    """The share of a region's worker pool humanoids serve this month (0 before the era)."""
    lg = state.robotics_world.adoption_of(region)
    if lg is None:
        return 0.0
    return balance.robotics.humanoids.adoption_cap * sigmoid(lg)


def humanoid_addressable(
    state: GameState, region: str, segment: str, balance: Balance, data: GameData
) -> float:
    rb = balance.robotics
    share = adoption_share(state, region, balance)
    if share <= 0:
        return 0.0
    market = data.category(rb.humanoid).market(segment)
    months = market.replacement_months or MONTHS
    workers = file(data).humanoids.workers[region]
    if segment == HOME:
        home = state.robotics_world.home_turn
        if home is None or state.turn < home:
            return 0.0
        pool = sum(workers.values()) * rb.humanoids.home_share
    else:
        pool = workers.get(segment, 0.0)
    return pool * MILLION * share * rb.scale * months / MONTHS / market.units_per_customer


def addressable(
    state: GameState, category: str, region: str, segment: str, balance: Balance, data: GameData
) -> float:
    if category == balance.robotics.industrial:
        return industrial_addressable(state, region, segment, balance, data)
    return humanoid_addressable(state, region, segment, balance, data)


def set_demand(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Every robot market's addressable customers this month (module docstring)."""
    rb = balance.robotics
    cats = (rb.industrial, rb.humanoid)
    home = home_region_of(state, balance, data)
    markets: list[MarketSegment] = []
    for m in state.markets:
        if m.category in cats:
            m = replace(
                m, addressable=addressable(state, m.category, home, m.segment, balance, data)
            )
        markets.append(m)
    regional = []
    for rm in state.regional_markets:
        if rm.category in cats:
            rm = replace(
                rm,
                addressable=addressable(state, rm.category, rm.region, rm.segment, balance, data),
            )
        regional.append(rm)
    state = with_all_markets(state, markets, regional)
    return _fit(state, cats, home)


def _fit(state: GameState, cats: tuple[str, str], home: str) -> GameState:
    """A market that shrank below the customers its lines hold (installations falling, homes not
    yet open) loses them in proportion: a segment's customers never exceed its demand."""
    by_id = {p.id: p.category for p in state.products if p.category in cats}
    held: dict[tuple[str, str, str], float] = {}
    for s in state.product_segments:
        if s.product_id in by_id:
            key = (by_id[s.product_id], s.segment, home)
            held[key] = held.get(key, 0.0) + s.customers
    for rs in state.regional_segments:
        if rs.product_id in by_id:
            key = (by_id[rs.product_id], rs.segment, rs.region)
            held[key] = held.get(key, 0.0) + rs.customers
    demand = {(m.category, m.segment, home): m.addressable for m in state.markets}
    demand.update(
        {(m.category, m.segment, m.region): m.addressable for m in state.regional_markets}
    )
    over = {k: demand.get(k, 0.0) / v for k, v in held.items() if v > demand.get(k, 0.0) + TINY}
    if not over:
        return state
    rows = [
        replace(s, customers=s.customers * over[k])
        for s in state.product_segments
        if s.product_id in by_id and (k := (by_id[s.product_id], s.segment, home)) in over
    ]
    regional_rows = [
        replace(rs, customers=rs.customers * over[k])
        for rs in state.regional_segments
        if rs.product_id in by_id and (k := (by_id[rs.product_id], rs.segment, rs.region)) in over
    ]
    return with_segments(state, rows, regional_rows)


# --- History: makers' shares and prices ----------------------------------------------------------


def maker_price(
    state: GameState, product: Product, segment: str, region: str, balance: Balance, data: GameData
) -> int | None:
    """An incumbent robot line's price in a region (incumbents.yaml's at home, x the region's
    price index elsewhere, as M9's incumbents); a humanoid line's is None before the era."""
    company = state.company(product.company_id)
    spec = next((c for c in data.incumbents if c.name == company.name), None) if company else None
    if spec is None:
        return None
    if is_humanoid(product, balance) and era_turn(state, data) is None:
        return None
    line = next((p for p in spec.products if p.category == product.category), None)
    if line is None or segment not in line.segments:
        return None
    home = home_region_of(state, balance, data)
    base = line.segments[segment].price_cents
    if region == home:
        return base
    return regional_price_cents(base, region, home, data)  # x the region's index (19.5)


def _maker_lines(state: GameState, balance: Balance, data: GameData) -> list[Product]:
    out = []
    for p in state.products:
        if p.status == "retired" or not (is_industrial(p, balance) or is_humanoid(p, balance)):
            continue
        company = state.company(p.company_id)
        if company is None or company.is_player or company.is_startup:
            continue
        f = file(data)
        if f.maker(company.name) is not None or f.humanoid_maker(company.name) is not None:
            out.append(p)
    return out


def pin(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Before `robotics.start`: each industrial robot maker's customers are its data share of the
    market not held by other companies' lines. Humanoid makers' prices are None until the era
    arrives, and set once it has. Nothing else changes from `robotics.start`."""
    history = in_history(state.turn, balance)
    era = era_turn(state, data)
    makers = _maker_lines(state, balance, data)
    humanoids = [p for p in makers if is_humanoid(p, balance)]
    if not history and (era is None or era != state.turn):
        if era is None:
            return _clear_prices(state, humanoids)
        return state
    year = year_at(state.turn)
    home = home_region_of(state, balance, data)
    rows: list[ProductSegment] = []
    regional_rows: list[RegionalSegment] = []
    if history:
        cat = balance.robotics.industrial
        others: dict[tuple[str, str], float] = {}
        mine = {p.id for p in makers}
        for p in state.products:
            if p.category != cat or p.id in mine or p.status == "retired":
                continue
            for s in state.segments_of(p.id):
                others[(home, s.segment)] = others.get((home, s.segment), 0.0) + s.customers
            for rs in state.regional_segments_of(p.id):
                key = (rs.region, rs.segment)
                others[key] = others.get(key, 0.0) + rs.customers
        demand = {(home, m.segment): m.addressable for m in state.markets if m.category == cat}
        demand.update(
            {
                (m.region, m.segment): m.addressable
                for m in state.regional_markets
                if m.category == cat
            }
        )
        for product in sorted(makers, key=lambda p: p.id):
            if not is_industrial(product, balance):
                continue
            company = state.company(product.company_id)
            assert company is not None
            maker = file(data).maker(company.name)
            assert maker is not None
            for s in state.segments_of(product.id):
                free = max(
                    0.0, demand.get((home, s.segment), 0.0) - others.get((home, s.segment), 0)
                )
                price = maker_price(state, product, s.segment, home, balance, data)
                rows.append(
                    replace(s, customers=maker.share_at(home, year) * free, price_cents=price)
                )
            for rs in state.regional_segments_of(product.id):
                key = (rs.region, rs.segment)
                free = max(0.0, demand.get(key, 0.0) - others.get(key, 0.0))
                price = maker_price(state, product, rs.segment, rs.region, balance, data)
                regional_rows.append(
                    replace(rs, customers=maker.share_at(rs.region, year) * free, price_cents=price)
                )
    for product in humanoids:  # None before the era; the incumbents' prices from its arrival
        for s in state.segments_of(product.id):
            price = maker_price(state, product, s.segment, home, balance, data)
            if s.price_cents != price:
                rows.append(
                    replace(s, price_cents=price, customers=0.0 if price is None else s.customers)
                )
        for rs in state.regional_segments_of(product.id):
            price = maker_price(state, product, rs.segment, rs.region, balance, data)
            if rs.price_cents != price:
                regional_rows.append(
                    replace(rs, price_cents=price, customers=0.0 if price is None else rs.customers)
                )
    return with_segments(state, rows, regional_rows)


def _clear_prices(state: GameState, humanoids: list[Product]) -> GameState:
    rows = [
        replace(s, price_cents=None, customers=0.0)
        for p in humanoids
        for s in state.segments_of(p.id)
        if s.price_cents is not None or s.customers
    ]
    regional = [
        replace(rs, price_cents=None, customers=0.0)
        for p in humanoids
        for rs in state.regional_segments_of(p.id)
        if rs.price_cents is not None or rs.customers
    ]
    if not rows and not regional:
        return state
    return with_segments(state, rows, regional)


# --- After the history: installations' growth and humanoid adoption ------------------------------


def world_month(state: GameState, rng: RngFactory, balance: Balance, data: GameData) -> GameState:
    """Phase 9 from December 2025: draw each region's installations growth a year ahead (keyed by
    year, drawn at `robotics.start`'s turn so the draw does not depend on when it is made); from
    the humanoid era's arrival, adoption's logit by region and the home window."""
    rb = balance.robotics
    if state.turn < rb.start_turn - 1:
        return state
    world = state.robotics_world
    year = turn_to_ym(state.turn)[0]
    growth = list(world.growth)
    have = {(r, y) for r, y, _ in growth}
    for i, region in enumerate(data.region_keys):
        for y in range(_start_year(balance), year + 2):
            if (region, y) in have:
                continue
            u = float(draws.gen(rng, rb.start_turn, draws.WORLD, i, y).random())
            growth.append(
                (region, y, rb.growth_after.lo + (rb.growth_after.hi - rb.growth_after.lo) * u)
            )
    world = replace(world, growth=tuple(growth))
    era = era_turn(state, data)
    if era is not None and state.turn >= era:
        world = _adoption(state, world, rng, era, balance, data)
    if world != state.robotics_world:
        state = replace(state, robotics_world=world)
    return state


def _adoption(
    state: GameState,
    world: RoboticsWorld,
    rng: RngFactory,
    era: int,
    balance: Balance,
    data: GameData,
) -> RoboticsWorld:
    from tst.sim.robotics import humanoids

    hb = balance.robotics.humanoids
    if not world.adoption:
        start = logit(hb.adoption_seed / hb.adoption_cap)
        u = float(draws.gen(rng, era, draws.WORLD, len(data.region_keys)).random())
        years = hb.home_window.lo + (hb.home_window.hi - hb.home_window.lo) * u
        return replace(
            world,
            adoption=tuple((r, start) for r in data.region_keys),
            home_turn=era + round(years * MONTHS),
        )
    best = humanoids.best_capability(state, balance, data)
    cost = humanoids.annual_cost_cents(balance, data)
    out = []
    for region, lg in world.adoption:
        labour = humanoids.labour_year_cents(state, region, balance, data)
        value = best / 100 * labour / cost if cost > TINY else 0.0
        k = max(hb.adoption_floor_k, hb.adoption_k * (value - 1))
        out.append((region, lg + k / MONTHS))
    return replace(world, adoption=tuple(out))
