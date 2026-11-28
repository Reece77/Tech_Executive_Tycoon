"""Connectivity and services (docs/formulas.md 56.3): where the player's space products can sell.

Read before the markets (`effects`, through M31's `Effects`), for the player's companies only
(rivals' lines follow the engine and, to 2025, the history):

- **Launch** (`launch`): a line sells only with a design (`set_launch_spec`) and while not
  grounded after a failure; its sales are capped by its launch sites (hardware production).
- **Satellite broadband**: a line sells in a region only where one of its constellations has a
  complete shell covering the region **and** the company holds a granted licence there (landing
  rights and spectrum). Its subscribers there are limited by capacity: the constellations' Gbps x
  `subs_per_gbps`, split over the served regions by their addressable markets; over it, appeal x
  `(capacity / subscribers) ** congestion_k` (congestion), and phase 9 trims subscribers to it.
  The user terminal's price, spread over `terminal.amortize_months`, adds to what buyers weigh.
- **Direct-to-device** (the broadband market's `direct_to_device` segment) opens with its history
  (space.yaml `d2d.open`) and needs a D2D-capable constellation; a carrier partner multiplies its
  appeal by `d2d.partner_appeal` and keeps `d2d.partner_share` of its revenue.
- **Earth observation**: a line sells everywhere once one of its EO constellations has
  `eo_min_satellites` in orbit.

After the markets (`books`): each new broadband subscriber takes a terminal made at its cost
(space.yaml's cost by year, less the player's learning, 5000) and pays the terminal's price
(4000); the carrier partner's share of D2D revenue is a cost (5000).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.ledger import CASH, COGS, REVENUE_SUBSCRIPTIONS, LedgerEntry
from tst.sim.money import exact
from tst.sim.platforms.phase import Effects
from tst.sim.products.models import SELLING, Product
from tst.sim.space import constellation as con
from tst.sim.space.data import TINY, file, is_broadband, is_eo, is_launch, year_at
from tst.sim.space.models import Constellation
from tst.sim.state import GameState, with_segments
from tst.sim.vehicles.config import interp

OFF: Final = 0.0  # tunable-exempt: a closed market's appeal multiplier


def _players(state: GameState) -> set[int]:
    return {c.id for c in state.companies if c.is_player}


def serving(state: GameState, product: Product) -> list[Constellation]:
    return [c for c in state.space.constellations if c.product_id == product.id]


def served_regions(state: GameState, product: Product, balance: Balance) -> tuple[str, ...]:
    """Regions a broadband line can sell in: covered by a constellation and licensed."""
    out: list[str] = []
    for c in serving(state, product):
        for r in con.covered_regions(c, balance):
            if r not in out and state.space.licensed(product.company_id, r):
                out.append(r)
    return tuple(out)


def d2d_open(state: GameState, data: GameData) -> bool:
    return state.turn >= file(data).d2d.open_turn


def d2d_capable(state: GameState, product: Product, data: GameData) -> bool:
    return d2d_open(state, data) and any(
        c.d2d and c.in_orbit() > 0 for c in serving(state, product)
    )


def _demand_weights(
    state: GameState, product: Product, regions: tuple[str, ...], balance: Balance, data: GameData
) -> dict[str, float]:
    home = home_region_of(state, balance, data)
    seg = balance.space.d2d_segment
    w: dict[str, float] = {}
    for m in state.markets:
        if m.category == product.category and m.segment != seg and home in regions:
            w[home] = w.get(home, 0.0) + m.addressable
    for rm in state.regional_markets:
        if rm.category == product.category and rm.segment != seg and rm.region in regions:
            w[rm.region] = w.get(rm.region, 0.0) + rm.addressable
    total = sum(w.values())
    return {r: v / total for r, v in w.items()} if total > TINY else {}


def capacity_by_region(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> tuple[dict[str, float], dict[str, float]]:
    """(broadband, D2D) subscribers the line's constellations can serve in each served region."""
    regions = served_regions(state, product, balance)
    if not regions:
        return {}, {}
    gbps = d2d = 0.0
    for c in serving(state, product):
        a, b = con.capacity_gbps(c, balance)
        gbps += a
        d2d += b
    cb = balance.space.constellation
    w = _demand_weights(state, product, regions, balance, data)
    return (
        {r: gbps * cb.subs_per_gbps * share for r, share in w.items()},
        {r: d2d * balance.space.d2d.subs_per_gbps * share for r, share in w.items()},
    )


def customers_by_region(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> tuple[dict[str, float], dict[str, float]]:
    """(broadband, D2D) subscribers by region."""
    home = home_region_of(state, balance, data)
    seg = balance.space.d2d_segment
    bb: dict[str, float] = {}
    dd: dict[str, float] = {}
    for s in state.segments_of(product.id):
        t = dd if s.segment == seg else bb
        t[home] = t.get(home, 0.0) + s.customers
    for rs in state.regional_segments_of(product.id):
        t = dd if rs.segment == seg else bb
        t[rs.region] = t.get(rs.region, 0.0) + rs.customers
    return bb, dd


def _keys(region: str, home: str) -> tuple[str, ...]:
    return (region, "") if region == home else (region,)


def effects(
    base: Effects | None, state: GameState, balance: Balance, data: GameData
) -> Effects | None:
    """The effects so far with the player's space lines' gates (module docstring)."""
    players = _players(state)
    sb = balance.space
    churn = (
        {
            p.id: sb.broadband_churn_mult
            for p in state.products
            if is_broadband(p, balance) and p.status != "retired"
        }
        if state.turn >= sb.start_turn
        else {}
    )
    lines = [
        p
        for p in state.products
        if p.company_id in players
        and p.status in SELLING
        and (is_launch(p, balance) or is_broadband(p, balance) or is_eo(p, balance))
    ]
    if not lines and not churn:
        return base
    home = home_region_of(state, balance, data)
    regions = data.region_keys
    appeal: dict[tuple[int, str], float] = {}
    segment: dict[tuple[int, str, str], float] = {}
    cut: dict[tuple[int, str], float] = {}
    for p in lines:
        if is_launch(p, balance):
            spec = state.space.spec(p.id)
            grounded = (
                spec is not None
                and spec.grounded_until is not None
                and state.turn < spec.grounded_until
            )
            if spec is None or grounded:
                for r in regions:
                    for k in _keys(r, home):
                        appeal[(p.id, k)] = OFF
            continue
        if is_eo(p, balance):
            ok = any(
                c.kind == "eo" and c.in_orbit() >= sb.constellation.eo_min_satellites
                for c in serving(state, p)
            )
            if not ok:
                for r in regions:
                    for k in _keys(r, home):
                        appeal[(p.id, k)] = OFF
            continue
        served = served_regions(state, p, balance)
        cap, cap_d2d = capacity_by_region(state, p, balance, data)
        subs, subs_d2d = customers_by_region(state, p, balance, data)
        capable = d2d_capable(state, p, data)
        partner = p.id in state.space.d2d_partners
        price = state.space.terminal_price(p.id) or 0
        for r in regions:
            keys = _keys(r, home)
            if r not in served:
                for k in keys:
                    appeal[(p.id, k)] = OFF
                continue
            m = 1.0
            have, room = subs.get(r, 0.0), cap.get(r, 0.0)
            if have > room + TINY:
                m = dmath.pow(room / have, sb.constellation.congestion_k) if room > TINY else OFF
            d = OFF
            if capable:
                d = sb.d2d.partner_appeal if partner else 1.0
                have_d, room_d = subs_d2d.get(r, 0.0), cap_d2d.get(r, 0.0)
                if have_d > room_d + TINY:
                    d *= (
                        dmath.pow(room_d / have_d, sb.constellation.congestion_k)
                        if room_d > TINY
                        else OFF
                    )
            for k in keys:
                if m != 1.0:
                    appeal[(p.id, k)] = m
                # D2D's segment is weighed apart from the rest: undo the congestion there
                ratio = d / m if m > TINY else d
                if ratio != 1.0:
                    segment[(p.id, k, sb.d2d_segment)] = ratio
                if price:
                    # money-exact: rate: a unit price in float cents, rounded where posted
                    cut[(p.id, k)] = -price / sb.terminal.amortize_months
    if not appeal and not segment and not cut and not churn:
        return base
    b = base if base is not None else Effects()
    merged_churn = dict(b.churn_mult)
    for pid, v in churn.items():
        merged_churn[pid] = merged_churn.get(pid, 1.0) * v
    merged_appeal = dict(b.appeal_mult)
    for key, v in appeal.items():
        merged_appeal[key] = merged_appeal.get(key, 1.0) * v
    merged_segment = dict(b.segment_appeal)
    for k3, v in segment.items():
        merged_segment[k3] = merged_segment.get(k3, 1.0) * v
    merged_cut = dict(b.price_cut)
    for key, v in cut.items():
        merged_cut[key] = merged_cut.get(key, 0.0) + v
    return replace(
        b,
        appeal_mult=merged_appeal,
        segment_appeal=merged_segment,
        price_cut=merged_cut,
        churn_mult=merged_churn,
    )


def terminal_cents(state: GameState, balance: Balance, data: GameData) -> float:
    """A user terminal's cost to make this month: space.yaml's cost by year, less the player's
    learning on the terminals it has made."""
    tb = balance.space.terminal
    base = interp(file(data).terminal_cost_cents, year_at(state.turn))
    made = max(state.space.world.terminals, tb.base_units)
    return base * dmath.pow(made / tb.base_units, dmath.log2(1 - tb.learning_rate))


def books(
    state: GameState,
    flows: Mapping[tuple[int, str], object],
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], dict[int, int]]:
    """Terminals for new subscribers and carriers' D2D shares (module docstring). Returns the
    state, entries and each of the player's broadband and EO lines' cash this month: its booked
    revenue in every region (price x subscribers, as phase 5 books it) less its subscribers'
    hosting (the ground segment and support, phase 6's 6300), less the carrier's share,
    plus terminal sales less their cost (a constellation's cash flow). New subscribers abroad are
    the home segment's new ones (phase 5's flows) x the segment's customers abroad over at home."""
    sb = balance.space
    players = _players(state)
    turn = state.turn
    entries: list[LedgerEntry] = []
    net: dict[int, int] = {}
    made = 0.0
    unit = terminal_cents(state, balance, data)
    for product in state.products:
        if product.company_id not in players or product.status not in SELLING:
            continue
        if not (is_broadband(product, balance) or is_eo(product, balance)):
            continue
        cash = 0
        new_total = 0.0
        d2d_revenue = 0
        abroad: dict[str, float] = {}
        category = data.category(product.category)
        for rs in state.regional_segments_of(product.id):
            abroad[rs.segment] = abroad.get(rs.segment, 0.0) + rs.customers
            cents = round(exact(rs.price_cents or 0) * exact(rs.customers))
            cash += cents - round(exact(rs.customers) * category.market(rs.segment).hosting_cents)
            if rs.segment == sb.d2d_segment:
                d2d_revenue += cents
        for seg in state.segments_of(product.id):
            cents = round(exact(seg.price_cents or 0) * exact(seg.customers))
            cash += cents - round(exact(seg.customers) * category.market(seg.segment).hosting_cents)
            if seg.segment == sb.d2d_segment:
                d2d_revenue += cents
                continue
            flow = flows.get((product.id, seg.segment))
            new = float(getattr(flow, "new", 0.0)) if flow is not None else 0.0
            if seg.customers > TINY:
                new *= 1 + abroad.get(seg.segment, 0.0) / seg.customers
            new_total += new
        if is_broadband(product, balance):
            if product.id in state.space.d2d_partners and d2d_revenue > 0:
                share = round(exact(d2d_revenue) * exact(sb.d2d.partner_share))
                if share > 0:
                    entries.append(
                        LedgerEntry.transfer(
                            turn=turn,
                            company_id=product.company_id,
                            memo=f"Carrier partner's share: {product.name}",
                            debit=COGS,
                            credit=CASH,
                            amount=share,
                        )
                    )
                    cash -= share
            if new_total > TINY:
                cost = round(exact(new_total) * exact(unit))
                price = state.space.terminal_price(product.id) or 0
                sold = round(exact(new_total) * price)
                made += new_total
                if cost > 0:
                    entries.append(
                        LedgerEntry.transfer(
                            turn=turn,
                            company_id=product.company_id,
                            memo=f"User terminals: {product.name}",
                            debit=COGS,
                            credit=CASH,
                            amount=cost,
                        )
                    )
                if sold > 0:
                    entries.append(
                        LedgerEntry.transfer(
                            turn=turn,
                            company_id=product.company_id,
                            memo=f"Terminal sales: {product.name}",
                            debit=CASH,
                            credit=REVENUE_SUBSCRIPTIONS,
                            amount=sold,
                        )
                    )
                cash += sold - cost
        net[product.id] = cash
    if made > 0:
        world = replace(state.space.world, terminals=state.space.world.terminals + made)
        state = replace(state, space=replace(state.space, world=world))
    return state, entries, net


def _factor(table: tuple[dict[str, float], dict[str, float]], region: str) -> float:
    have, room = table[0].get(region, 0.0), table[1].get(region, 0.0)
    return min(1.0, room / have) if have > room + TINY else 1.0


def trim_to_capacity(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Phase 9: a broadband line's subscribers in a region never exceed what its constellations
    can serve there (and none where it is not served)."""
    players = _players(state)
    home = home_region_of(state, balance, data)
    seg = balance.space.d2d_segment
    rows = []
    regional = []
    for p in state.products:
        if p.company_id not in players or not is_broadband(p, balance) or p.status == "retired":
            continue
        cap, cap_d2d = capacity_by_region(state, p, balance, data)
        subs, subs_d2d = customers_by_region(state, p, balance, data)
        if not d2d_capable(state, p, data):
            cap_d2d = {}

        tables = {False: (subs, cap), True: (subs_d2d, cap_d2d)}
        for s in state.segments_of(p.id):
            f = _factor(tables[s.segment == seg], home)
            if f < 1.0:
                rows.append(replace(s, customers=s.customers * f))
        for rs in state.regional_segments_of(p.id):
            f = _factor(tables[rs.segment == seg], rs.region)
            if f < 1.0:
                regional.append(replace(rs, customers=rs.customers * f))
    if not rows and not regional:
        return state
    return with_segments(state, rows, regional)
