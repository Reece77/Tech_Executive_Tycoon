"""What the vehicles market reads, and the cars' month after it (docs/formulas.md 49.1, 49.3-49.5).

**Before the markets** (`effects`): for every live line of the player's group (rivals' lines are
static, their held features already price these in), by region:

- feature points: range and charging (`spec`), charging coverage x the share of the expected
  speed it charges at x `charging.coverage_points`, its level's points where its cars run it, its
  platform's (`software.platform_points`), and `charging.exclusive_points` where its group runs an
  exclusive network;
- the price buyers weigh: its price less the region's average subsidy it qualifies for
  (`subsidies.product_cut`), for every line, the rivals' too;
- churn: a line with over-the-air updates (own or licensed platform) is replaced
  `software.ota_churn_cut` less often.

**After the month's sales** (`month_rows`, `software_month`): each player line's `VehicleMonth`
(cars sold, a car's cost by line, the level it runs, its range and subsidy eligibility) and its
software: connectivity (`attach(year) x attach_mult x price_cents` by platform) and its level's
subscription (`level.attach x level.price_cents`) on every car on the road a month, to 4000; a
licensed platform's `licence_cents` a car sold, to 5150.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.ledger import CASH, PLATFORM_FEES, REVENUE_SUBSCRIPTIONS, LedgerEntry, LedgerLine
from tst.sim.money import exact
from tst.sim.platforms.phase import Effects
from tst.sim.products.models import SELLING
from tst.sim.state import GameState, player_companies
from tst.sim.vehicles import cells, charging, subsidies
from tst.sim.vehicles import spec as vs
from tst.sim.vehicles.config import interp
from tst.sim.vehicles.data import enabled, file, is_vehicle, year_at
from tst.sim.vehicles.models import VehicleMonth

OTA: Final = ("own", "licensed")  # tunable-exempt: platform choices with over-the-air updates
LICENSED: Final = "licensed"


def _regions_of(state: GameState, product_id: int, home: str) -> list[tuple[str, int | None]]:
    """(region, a price there) for each region the line sells in."""
    out: list[tuple[str, int | None]] = []
    home_price = next((s.price_cents for s in state.segments_of(product_id) if s.price_cents), None)
    if state.segments_of(product_id):
        out.append((home, home_price))
    seen = {home}
    for rs in state.regional_segments_of(product_id):
        if rs.region not in seen:
            seen.add(rs.region)
            out.append((rs.region, rs.price_cents))
    return out


def feature_points(
    state: GameState, product_id: int, region: str, balance: Balance, data: GameData
) -> float:
    product = state.product(product_id)
    assert product is not None
    vb = balance.vehicles
    spec = vs.spec_of(state, product, data)
    turn = state.turn
    from tst.sim.vehicles import demand

    expected_kw = interp(file(data).charge_expected_kw, year_at(turn))
    cover = demand.coverage(state, region, balance, data)
    pts = vs.range_points(spec, turn, balance, data) + vs.charge_points(spec, turn, balance, data)
    pts += vb.charging.coverage_points * cover * min(1.0, spec.charge_kw / expected_kw)
    pts += vb.levels[vs.level_in(state, product, region, balance, data)].features
    pts += vb.software.platform_points.get(spec.platform, 0.0)
    if charging.exclusive_in(state, product.company_id, region):
        pts += vb.charging.exclusive_points
    return pts


def effects(
    state: GameState, balance: Balance, data: GameData
) -> tuple[dict[tuple[int, str], float], dict[tuple[int, str], float], dict[int, float]]:
    """(feature bonus, price cut, churn multiple) by (product, region) and product (module
    docstring); empty when the save has no vehicles market."""
    if not enabled(state, balance, data):
        return {}, {}, {}
    vb = balance.vehicles
    home = home_region_of(state, balance, data)
    players = {c.id for c in player_companies(state)}
    bonus: dict[tuple[int, str], float] = {}
    cut: dict[tuple[int, str], float] = {}
    churn: dict[int, float] = {}
    for product in state.products:
        if not is_vehicle(product, balance) or product.status not in SELLING:
            continue
        mine = product.company_id in players
        if mine:
            spec = vs.spec_of(state, product, data)
            if spec.platform in OTA:
                churn[product.id] = 1 - vb.software.ota_churn_cut
        for region, price in _regions_of(state, product.id, home):
            key = (product.id, region)
            if mine:
                bonus[key] = feature_points(state, product.id, region, balance, data)
            if price:
                c = subsidies.product_cut(state, product, region, price, balance, data)
                if c > 0:
                    cut[key] = c
    return bonus, cut, churn


def attach_rate(state: GameState, platform: str, balance: Balance, data: GameData) -> float:
    base = interp(
        file(data).software_attach, year_at(min(state.turn, balance.vehicles.start_turn - 1))
    )
    if state.turn >= balance.vehicles.start_turn:  # after 2025 attach keeps rising (A)
        years = (state.turn - balance.vehicles.start_turn) / 12
        sb = balance.vehicles.software
        base = min(sb.attach_cap, base + sb.attach_growth * years)
    return min(1.0, base * balance.vehicles.software.attach_mult.get(platform, 1.0))


def month_rows(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Each player line's VehicleMonth from this month's production row (module docstring)."""
    if not enabled(state, balance, data):
        return state
    players = {c.id for c in player_companies(state)}
    home = home_region_of(state, balance, data)
    rows: list[VehicleMonth] = []
    for product in sorted(state.products, key=lambda p: p.id):
        if product.company_id not in players or not is_vehicle(product, balance):
            continue
        if product.status not in SELLING:
            continue
        prow = next((r for r in state.production if r.product_id == product.id), None)
        spec = vs.spec_of(state, product, data)
        capable = vs.capable_level(state, spec, product.company_id, balance)
        cost = vs.unit_cost(state, product, balance, data, capable)
        assembly = (
            # money-exact: rate (a car's assembly cost for the product page)
            (prow.assembly_cents / prow.units) if prow is not None and prow.units > 0 else 0.0
        )
        level = max(
            (
                vs.level_in(state, product, r, balance, data, capable)
                for r, _ in _regions_of(state, product.id, home)
            ),
            key=lambda k: list(balance.vehicles.levels).index(k),
            default="none",
        )
        eligible = tuple(
            (r, bool(subsidies.product_cut(state, product, r, price, balance, data) > 0))
            for r, price in _regions_of(state, product.id, home)
            if price and subsidies.schemes_in(state, r, data)
        )
        rows.append(
            VehicleMonth(
                turn=state.turn,
                product_id=product.id,
                units=prow.units if prow is not None else 0.0,
                battery_cents=cost.battery,
                drive_cents=cost.drive,
                chips_cents=cost.chips,
                body_cents=cost.body,
                assembly_cents=assembly,
                own_kwh=0.0,
                software_cents=0,
                licence_cents=0,
                level=level,
                range_km=vs.range_km(spec, state.turn, balance, data),
                subsidy_regions=eligible,
            )
        )
    keep = balance.vehicles.history_months
    old = [m for m in state.vehicle_months if m.turn != state.turn and m.turn > state.turn - keep]
    return replace(
        state, vehicle_months=tuple(sorted((*old, *rows), key=lambda m: (m.product_id, m.turn)))
    )


def software_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    """Subscriptions and licences for this month's rows; own-cell kWh onto them."""
    vb = balance.vehicles
    home = home_region_of(state, balance, data)
    entries: list[LedgerEntry] = []
    out = []
    for m in state.vehicle_months:
        if m.turn != state.turn:
            out.append(m)
            continue
        product = state.product(m.product_id)
        assert product is not None
        spec = vs.spec_of(state, product, data)
        sb = vb.software
        connectivity = attach_rate(state, spec.platform, balance, data) * sb.price_cents.get(
            spec.platform, 0.0
        )
        capable = vs.capable_level(state, spec, product.company_id, balance)
        total = exact(0)
        for region, _ in _regions_of(state, product.id, home):
            from tst.sim.vehicles.autonomy import cars_on_road

            cars = cars_on_road(state, product.id, region, balance, data)
            lv = vb.levels[vs.level_in(state, product, region, balance, data, capable)]
            total += exact(cars) * (exact(connectivity) + exact(lv.attach) * exact(lv.price_cents))
        software = round(total)
        licence = (
            round(exact(m.units) * exact(sb.licence_cents)) if spec.platform == LICENSED else 0
        )
        if software > 0:
            entries.append(
                LedgerEntry(
                    state.turn,
                    product.company_id,
                    f"Car software: {product.name}",
                    (
                        LedgerLine(CASH, software, product.division_id),
                        LedgerLine(REVENUE_SUBSCRIPTIONS, -software, product.division_id),
                    ),
                )
            )
        if licence > 0:
            entries.append(
                LedgerEntry(
                    state.turn,
                    product.company_id,
                    f"Android Automotive licences: {product.name}",
                    (
                        LedgerLine(PLATFORM_FEES, licence, product.division_id),
                        LedgerLine(CASH, -licence, product.division_id),
                    ),
                )
            )
        own = cells.own_kwh(state, product.id)
        battery = m.battery_cents
        if own > 0 and m.units > 0:  # own cells at the plant's cost, not the market's
            per_car = own / m.units
            # money-exact: rate (a kWh's cost for the product page)
            plant_unit = (
                sum(
                    lot.taken * lot.unit_cents  # money-exact: rate (the product page)
                    for lot in state.cell_lots
                    if lot.product_id == product.id and lot.turn == state.turn
                )
                / own
            )
            # money-exact: rate (a car's pack cost for the product page)
            battery -= per_car * (cells.market_cents(state, balance, data) - plant_unit)
        out.append(
            replace(
                m,
                software_cents=software,
                licence_cents=licence,
                own_kwh=own,
                battery_cents=battery,
            )
        )
    return replace(state, vehicle_months=tuple(out)), entries


def units_of(cat_units: float, segment: str, data: GameData, category: str) -> float:
    return cat_units * data.category(category).market(segment).units_per_customer


def with_effects(
    base: Effects | None, state: GameState, balance: Balance, data: GameData
) -> Effects | None:
    """The platforms' effects with the cars' added (feature points add, churn multiplies)."""
    bonus, cut, churn = effects(state, balance, data)
    if not bonus and not cut and not churn:
        return base
    b = base if base is not None else Effects()
    feature = dict(b.feature_bonus)
    for k, v in bonus.items():
        feature[k] = feature.get(k, 0.0) + v
    churn_mult = dict(b.churn_mult)
    for pid, m in churn.items():
        churn_mult[pid] = churn_mult.get(pid, 1.0) * m
    return replace(b, feature_bonus=feature, churn_mult=churn_mult, price_cut=cut)
