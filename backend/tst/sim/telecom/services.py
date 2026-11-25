"""Where the player's telecom lines can sell (docs/formulas.md 62.1-62.4), read before the markets
through M31's `Effects`, for the player's own lines only (rivals' lines follow the engine and, to
2025, the history; an operator the player acquires keeps the network its data gives it, a
follow-up):

- **Mobile:** appeal x the network's coverage in the region (none without spectrum; a
  direct-to-device satellite partner adds `satellite.partner_coverage` from its opening), x
  `(capacity / demand) ** congestion_k` when over capacity, x `regulation.zero_rating_appeal` for a
  zero-rating line where no net-neutrality rule is in force; its generations add feature points.
- **Fixed broadband:** appeal x the share of the region's households its fibre passes; phase 9
  trims subscribers to `fibre.max_take_up` of homes passed.
- **Wholesale:** sells only where the company has spare capacity (mobile, fibre and subsea
  cables); phase 9 trims contracts to it.

After the markets (`books`): a satellite partner keeps `satellite.partner_fee_share` of a mobile
line's revenue in the regions its coverage comes from (5000).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.geo.formulas import cost_ratio
from tst.sim.ledger import CASH, COGS, LedgerEntry
from tst.sim.money import exact
from tst.sim.platforms.phase import Effects
from tst.sim.products.models import SELLING, Product
from tst.sim.state import GameState, with_segments
from tst.sim.telecom import networks as nw
from tst.sim.telecom.data import TINY, file, is_service, is_telecom_rival

OFF: Final = 0.0  # tunable-exempt: a closed market's appeal multiplier


def own_lines(state: GameState, balance: Balance, data: GameData) -> list[Product]:
    """The player's selling telecom service lines that its own networks serve."""
    players = {c.id for c in state.companies if c.is_player}
    out = []
    for p in state.products:
        if p.company_id not in players or p.status not in SELLING or not is_service(p, balance):
            continue
        company = state.company(p.company_id)
        if company is not None and is_telecom_rival(company, data):
            continue  # an acquired operator keeps its data network (follow-up)
        out.append(p)
    return out


def _keys(region: str, home: str) -> tuple[str, ...]:
    return (region, "") if region == home else (region,)


def customers_by_region(state: GameState, product: Product, home: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for s in state.segments_of(product.id):
        out[home] = out.get(home, 0.0) + s.customers
    for rs in state.regional_segments_of(product.id):
        out[rs.region] = out.get(rs.region, 0.0) + rs.customers
    return out


def company_customers(
    state: GameState, company_id: int, category: str, home: str
) -> dict[str, float]:
    out: dict[str, float] = {}
    for p in state.products:
        if p.company_id != company_id or p.category != category or p.status not in SELLING:
            continue
        for r, v in customers_by_region(state, p, home).items():
            out[r] = out.get(r, 0.0) + v
    return out


def neutrality_in_force(state: GameState, region: str, data: GameData) -> bool:
    """A net-neutrality rule is in force in any of the region's areas."""
    return any(n.region == region and n.in_force(state.turn) for n in file(data).neutrality)


def satellite_open(state: GameState, data: GameData) -> bool:
    """Direct-to-device has opened (space.yaml's d2d.open): a partner can carry phones."""
    return data.space is not None and state.turn >= data.space.d2d.open_turn


def mobile_coverage(
    state: GameState,
    product: Product,
    region: str,
    net: nw.RegionNetwork,
    balance: Balance,
    data: GameData,
) -> tuple[float, float]:
    """(coverage the line sells with, the share of it a satellite partner provides)."""
    setting = state.telecom.setting(product.id)
    cov = net.coverage
    partner = 0.0
    if setting is not None and setting.satellite_partner and satellite_open(state, data):
        extra = min(balance.telecom.satellite.partner_coverage, max(0.0, 1.0 - cov))
        partner = extra
        cov += extra
    return cov, (partner / cov if cov > TINY else 0.0)


def spare_gb(
    state: GameState,
    company_id: int,
    region: str,
    net: nw.RegionNetwork,
    balance: Balance,
    data: GameData,
    home: str,
) -> float:
    """Capacity left for wholesale in a region: mobile and fibre capacity over the company's
    own subscribers' traffic, plus its subsea cables landing there."""
    tb = balance.telecom
    traffic = nw.traffic_gb(state, balance, data)
    mobile = company_customers(state, company_id, tb.mobile, home).get(region, 0.0)
    fixed = company_customers(state, company_id, tb.fixed, home).get(region, 0.0)
    spare = max(0.0, net.capacity_gb - mobile * traffic)
    spare += max(0.0, net.fibre_gb - fixed * traffic * tb.capacity.fixed_gb_mult)
    return spare + net.cable_gb


def effects(
    base: Effects | None, state: GameState, balance: Balance, data: GameData
) -> Effects | None:
    """The effects so far with the player's telecom lines' gates (module docstring)."""
    lines = own_lines(state, balance, data)
    if not lines:
        return base
    tb = balance.telecom
    home = home_region_of(state, balance, data)
    regions = data.region_keys
    appeal: dict[tuple[int, str], float] = {}
    bonus: dict[tuple[int, str], float] = {}
    nets: dict[tuple[int, str], nw.RegionNetwork] = {}
    traffic = nw.traffic_gb(state, balance, data)
    contract = nw.contract_gb(state, balance, data)

    def net_of(company_id: int, region: str) -> nw.RegionNetwork:
        key = (company_id, region)
        if key not in nets:
            nets[key] = nw.network(state, company_id, region, balance, data)
        return nets[key]

    for p in lines:
        setting = state.telecom.setting(p.id)
        for r in regions:
            net = net_of(p.company_id, r)
            if p.category == tb.mobile:
                cov, _ = mobile_coverage(state, p, r, net, balance, data)
                m = cov
                demand = (
                    company_customers(state, p.company_id, tb.mobile, home).get(r, 0.0) * traffic
                )
                if cov > TINY and demand > net.capacity_gb + TINY:
                    m *= (
                        dmath.pow(net.capacity_gb / demand, tb.capacity.congestion_k)
                        if net.capacity_gb > TINY
                        else OFF
                    )
                if (
                    setting is not None
                    and setting.zero_rating
                    and not neutrality_in_force(state, r, data)
                ):
                    m *= tb.regulation.zero_rating_appeal
                points = nw.feature_points(net, balance, data)
                for k in _keys(r, home):
                    if m != 1.0:
                        appeal[(p.id, k)] = m
                    if points:
                        bonus[(p.id, k)] = points
            elif p.category == tb.fixed:
                households = nw.households(state, r, balance, data)
                m = min(1.0, net.homes_passed / households) if households > TINY else OFF
                for k in _keys(r, home):
                    if m != 1.0:
                        appeal[(p.id, k)] = m
            else:
                room = spare_gb(state, p.company_id, r, net, balance, data, home) / contract
                m = OFF if room <= TINY else 1.0
                for k in _keys(r, home):
                    if m != 1.0:
                        appeal[(p.id, k)] = m
    if not appeal and not bonus:
        return base
    b = base if base is not None else Effects()
    merged_appeal = dict(b.appeal_mult)
    for key, v in appeal.items():
        merged_appeal[key] = merged_appeal.get(key, 1.0) * v
    merged_bonus = dict(b.feature_bonus)
    for key, v in bonus.items():
        merged_bonus[key] = merged_bonus.get(key, 0.0) + v
    return replace(b, appeal_mult=merged_appeal, feature_bonus=merged_bonus)


def trim_to_capacity(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Phase 9: fixed subscribers to `max_take_up` of homes passed, wholesale contracts to spare
    capacity, by region (the home segment and the regional ones scaled alike)."""
    lines = own_lines(state, balance, data)
    if not lines:
        return state
    tb = balance.telecom
    home = home_region_of(state, balance, data)
    contract = nw.contract_gb(state, balance, data)
    rows = []
    regional = []
    for p in lines:
        if p.category == tb.mobile:
            continue
        have = customers_by_region(state, p, home)
        for r, n in have.items():
            if n <= TINY:
                continue
            net = nw.network(state, p.company_id, r, balance, data)
            if p.category == tb.fixed:
                room = net.homes_passed * tb.fibre.max_take_up
            else:
                room = spare_gb(state, p.company_id, r, net, balance, data, home) / contract
            if n <= room + TINY:
                continue
            f = room / n if n > TINY else 0.0
            if r == home:
                rows += [replace(s, customers=s.customers * f) for s in state.segments_of(p.id)]
            regional += [
                replace(rs, customers=rs.customers * f)
                for rs in state.regional_segments_of(p.id)
                if rs.region == r
            ]
    if not rows and not regional:
        return state
    return with_segments(state, rows, regional)


def books(
    state: GameState, balance: Balance, data: GameData
) -> tuple[list[LedgerEntry], dict[tuple[int, str], int]]:
    """A satellite partner's share of a mobile line's revenue (module docstring); and each of the
    player's service lines' revenue by (company, region) this month, less subscribers' hosting
    (the network's cash flow, target 3)."""
    tb = balance.telecom
    home = home_region_of(state, balance, data)
    entries: list[LedgerEntry] = []
    revenue: dict[tuple[int, str], int] = {}
    for p in own_lines(state, balance, data):
        category = data.category(p.category)
        partner_cents = 0
        rows: list[tuple[str, str, int | None, float]] = [
            (home, s.segment, s.price_cents, s.customers) for s in state.segments_of(p.id)
        ] + [
            (rs.region, rs.segment, rs.price_cents, rs.customers)
            for rs in state.regional_segments_of(p.id)
        ]
        for region, segment, price, customers in rows:
            cents = round(exact(price or 0) * exact(customers))
            hosting = round(
                exact(customers)
                * category.market(segment).hosting_cents
                * cost_ratio(region, home, data, p.category)
            )
            fee = 0
            if p.category == tb.mobile and cents > 0:
                net = nw.network(state, p.company_id, region, balance, data)
                _, share = mobile_coverage(state, p, region, net, balance, data)
                if share > TINY:
                    fee = round(exact(cents) * exact(share) * exact(tb.satellite.partner_fee_share))
            partner_cents += fee
            key = (p.company_id, region)
            revenue[key] = revenue.get(key, 0) + cents - hosting - fee
        if partner_cents > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=p.company_id,
                    memo=f"Satellite partner's share: {p.name}",
                    debit=COGS,
                    credit=CASH,
                    amount=partner_cents,
                )
            )
    return entries, revenue
