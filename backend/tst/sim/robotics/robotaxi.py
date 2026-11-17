"""Robotaxi services (docs/formulas.md 53.3).

A **service** is a live product of the `mobility` pseudo-category. It runs in **zones**: a zone is a
city (robotics.yaml), a size (its share of the city's ride-hailing trips) and a fleet of L4 cars.

- **Permits.** A zone can be applied for where the city's region has approved L4 (M38's automotive
  regulators, `vehicles.spec.approved`) and the company can drive at L4 (its autonomy lead and AI
  quality, `vehicles.levels.l4`). The review takes the size's `review_months`, then each month a
  decision comes with `approval_chance` (stream robotics (2, region_index, zone_id)); it refuses
  with `refusal_share` plus `incident_refusal` for each serious incident of the company's in the
  last 24 months. Neither the draw nor the decision month is shown ahead.
- **Rides.** A month's covered trips are the city's ride-hailing trips (robotics.yaml, x
  robotics.scale) x the zone's share. Riders who take a robotaxi: covered trips x acceptance (from
  `acceptance.lo` at the city's first driverless service toward `acceptance.hi`, half way after
  `acceptance_years`) x (fare / price) ** elasticity x the fleet's attraction d / (d + wait_cars)
  (d = cars per 1,000 covered trips a day) x the service's trust (0.5 + brand / 100), shared with
  the rival operators' cars in the city (their fleets at the game's scale, spread over the city).
  Rides are at most cars x `max_rides_per_day` x days, and a fleet beyond its depots' capacity in
  the city runs only the share the depots serve. **Utilisation** = rides / that most.
- **Economics** (a month): revenue = rides x price (4000); energy (km x (1 + deadhead) x kWh/km x
  power), cleaning a ride, insurance and remote assistance (cars / cars_per_operator x
  operator_cents) a car (5000); the cars' depreciation over `depreciation_months` (6700). The
  depot's own costs are its facility's (phase 6). Contribution = revenue less all of these but the
  depot: positive above `breakeven_rides` rides a car a day at the reference fare (53.4 target 4).
- **Incidents.** A zone's month has a Poisson number of incidents with mean km / 1e6 x
  incident_rate x 0.5 ** (the company's driverless km / maturity_km) x (1 - ai_cut x the AI
  model's quality above the L4 threshold, as a share of the rest to 100) (stream robotics (1,
  zone_id, city_index)); each is serious with `serious_share`. A minor one costs `minor_cents` and
  a little brand. A serious one costs `serious_cents` and brand, suspends the zone's permit for
  `suspend_months` (as Cruise's in October 2023: no rides, the cars still cost their insurance and
  depreciation) and is a critical event for the player. The draws are never stored or shown.
- **Rivals** (data to 2025): Waymo, Cruise (ended), Apollo Go, Pony.ai, WeRide, Tesla, Zoox. After
  2025 their fleets grow `rival_growth` a year and each December an operator enters a new city
  with `rival_entry` (stream robotics (3, operator_index)) where the city's region has approved L4.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    COGS,
    DEPRECIATION,
    GENERAL_ADMIN,
    REVENUE_SUBSCRIPTIONS,
    LedgerEntry,
    LedgerLine,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.rng import RngFactory
from tst.sim.robotics import draws
from tst.sim.robotics.config import CityDef, CityServiceDef
from tst.sim.robotics.data import MILLION, MONTHS, THOUSAND, TINY, WEEKS_PER_MONTH, file, year_at
from tst.sim.robotics.models import RivalCity, RoboIncident, Zone, ZoneMonth
from tst.sim.state import GameState, with_product
from tst.sim.vehicles import spec as vs
from tst.sim.vehicles.config import interp

L4: Final = "l4"  # tunable-exempt: the autonomy level robotaxis run (vehicles.levels key)
DECEMBER: Final = 12  # tunable-exempt: calendar
SERIOUS_WINDOW: Final = 24  # tunable-exempt: months a serious incident counts against a permit
LAST_YEAR: Final = 2025  # tunable-exempt: robotics.yaml's last data year
TRUST_BASE: Final = 0.5  # tunable-exempt: trust = 0.5 + brand / 100
SCORE: Final = 100.0  # tunable-exempt: brand and AI quality are on 0-100
HALF: Final = 0.5  # tunable-exempt: the rate halves every maturity_km
PER_THOUSAND: Final = 1_000  # tunable-exempt: the attraction's density unit
OPEN: Final = ("active", "suspended")  # tunable-exempt: zone statuses that hold cars


def city(data: GameData, key: str) -> CityDef:
    c = file(data).robotaxi.city(key)
    assert c is not None
    return c


def trips_month(state: GameState, c: CityDef, balance: Balance, data: GameData) -> float:
    """The city's ride-hailing trips a month at the game's scale."""
    t = min(year_at(state.turn), float(LAST_YEAR))
    return file(data).robotaxi.trips_at(c, t) * MILLION * WEEKS_PER_MONTH * balance.robotics.scale


def fare_cents(c: CityDef) -> float:
    return c.fare_cents


# --- Rival operators ------------------------------------------------------------------------------


def _service_fleet(svc: CityServiceDef, turn: int, balance: Balance) -> float:
    if not svc.running(turn):
        return 0.0
    t = year_at(turn)
    if t <= LAST_YEAR:
        return interp(svc.fleet, max(t, min(svc.fleet)))
    years = t - LAST_YEAR
    return float(
        interp(svc.fleet, LAST_YEAR) * (1 + balance.robotics.robotaxi.rival_growth) ** years
    )


def _service_rides(svc: CityServiceDef, turn: int, balance: Balance) -> float:
    """A service's paid rides a week (real) this month."""
    if not svc.running(turn):
        return 0.0
    t = year_at(turn)
    if t <= LAST_YEAR:
        return interp(svc.rides, max(t, min(svc.rides))) * THOUSAND
    return _service_fleet(svc, turn, balance) * balance.robotics.robotaxi.rides_per_car_week


def rival_fleet(state: GameState, city_key: str, balance: Balance, data: GameData) -> float:
    """Rival operators' robotaxis in the city this month, real cars."""
    total = 0.0
    for op in file(data).robotaxi.operators:
        if op.ended is not None and state.turn >= _turn(op.ended):
            continue
        for svc in op.services:
            if svc.city == city_key:
                total += _service_fleet(svc, state.turn, balance)
    rb = balance.robotics.robotaxi
    for rc in state.robotics_world.rival_cities:
        if rc.city == city_key and rc.start_turn <= state.turn:
            years = (state.turn - rc.start_turn) / MONTHS
            total += rc.fleet * (1 + rb.rival_growth) ** years
    return total


@dataclass(frozen=True, slots=True)
class RivalService:
    """A rival service that has started (public): operator, city, fleet, rides a week (real)."""

    operator: str
    city: str
    since: int
    running: bool
    fleet: float
    rides_week: float


def rival_services(state: GameState, balance: Balance, data: GameData) -> list[RivalService]:
    """Every rival service that has started (public): operator, city, fleet, rides a week."""
    out: list[RivalService] = []
    for op in file(data).robotaxi.operators:
        ended = op.ended is not None and state.turn >= _turn(op.ended)
        for svc in op.services:
            if svc.start_turn > state.turn:
                continue
            running = svc.running(state.turn) and not ended
            out.append(
                RivalService(
                    op.label,
                    svc.city,
                    svc.start_turn,
                    running,
                    _service_fleet(svc, state.turn, balance) if running else 0.0,
                    _service_rides(svc, state.turn, balance) if running else 0.0,
                )
            )
    rb = balance.robotics.robotaxi
    labels = {op.key: op.label for op in file(data).robotaxi.operators}
    for rc in state.robotics_world.rival_cities:
        if rc.start_turn > state.turn:
            continue
        years = (state.turn - rc.start_turn) / MONTHS
        fleet = rc.fleet * (1 + rb.rival_growth) ** years
        out.append(
            RivalService(
                labels.get(rc.operator, rc.operator),
                rc.city,
                rc.start_turn,
                True,
                fleet,
                fleet * rb.rides_per_car_week,
            )
        )
    return out


def _turn(month: str) -> int:
    from tst.sim.facilities.config import month_to_turn

    return month_to_turn(month)


def first_service_turn(state: GameState, city_key: str, data: GameData) -> int | None:
    """The month the city's first driverless service began (any operator's or the player's)."""
    turns = [
        svc.start_turn
        for op in file(data).robotaxi.operators
        for svc in op.services
        if svc.city == city_key and svc.start_turn <= state.turn
    ]
    turns += [
        rc.start_turn
        for rc in state.robotics_world.rival_cities
        if rc.city == city_key and rc.start_turn <= state.turn
    ]
    turns += [
        z.approved_turn
        for z in state.zones
        if z.city == city_key and z.approved_turn is not None and z.approved_turn <= state.turn
    ]
    return min(turns) if turns else None


def acceptance(state: GameState, city_key: str, balance: Balance, data: GameData) -> float:
    rb = balance.robotics.robotaxi
    first = first_service_turn(state, city_key, data)
    if first is None:
        return rb.acceptance.lo
    years = (state.turn - first) / MONTHS
    return rb.acceptance.lo + (rb.acceptance.hi - rb.acceptance.lo) * years / (
        years + rb.acceptance_years
    )


def december_rivals(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> GameState:
    """Each December from robotics.start: an operator may enter a new city (module docstring)."""
    rb = balance.robotics
    if state.turn < rb.start_turn or turn_to_ym(state.turn)[1] != DECEMBER:
        return state
    f = file(data).robotaxi
    added = list(state.robotics_world.rival_cities)
    for i, op in enumerate(f.operators):
        if op.ended is not None:
            continue
        u = float(draws.gen(rng, state.turn, draws.RIVAL, i).random())
        if u >= rb.robotaxi.rival_entry:
            continue
        served = {s.city for s in op.services} | {rc.city for rc in added if rc.operator == op.key}
        for c in f.cities:
            if c.key in served or not vs.approved(state, c.region, L4, balance, data):
                continue
            added.append(RivalCity(op.key, c.key, state.turn + 1, rb.robotaxi.rival_fleet))
            break
    if len(added) == len(state.robotics_world.rival_cities):
        return state
    return replace(state, robotics_world=replace(state.robotics_world, rival_cities=tuple(added)))


# --- The player's zones -------------------------------------------------------------------------


def can_drive_l4(state: GameState, company_id: int, balance: Balance) -> bool:
    """The company's autonomy lead and AI quality reach L4 (vehicles.levels.l4)."""
    level = balance.vehicles.levels.get(L4)
    if level is None:
        return False
    lead = state.research_lead(company_id, balance.vehicles.domain)
    ai = vs.best_ai_quality(state, company_id)
    return lead + TINY >= level.lead and (level.ai_quality <= 0 or ai >= level.ai_quality)


def serious_recent(state: GameState, company_id: int) -> int:
    return sum(
        1
        for i in state.robo_incidents
        if i.company_id == company_id and i.serious and i.turn > state.turn - SERIOUS_WINDOW
    )


def company_km(state: GameState, company_id: int) -> float:
    return sum(z.km_driven for z in state.zones if z.company_id == company_id)


def depot_capacity(state: GameState, company_id: int, city_key: str, balance: Balance) -> float:
    """Cars the company's live depots in the city serve."""
    cars = 0.0
    for d in state.depots:
        if d.company_id != company_id or d.city != city_key:
            continue
        f = state.facility(d.facility_id)
        if f is not None:
            cars += f.live_capacity(state.turn) * balance.robotics.robotaxi.depot_cars
    return cars


def incident_rate(state: GameState, company_id: int, balance: Balance) -> float:
    """Incidents a million km for the company's robotaxis this month (never shown)."""
    rb = balance.robotics.robotaxi
    maturity = HALF ** (company_km(state, company_id) / rb.maturity_km)
    threshold = balance.vehicles.levels[L4].ai_quality if L4 in balance.vehicles.levels else 0.0
    ai = vs.best_ai_quality(state, company_id)
    above = max(0.0, ai - threshold) / max(TINY, SCORE - threshold)
    return float(rb.incident_rate * maturity * (1 - rb.ai_cut * min(1.0, above)))


def most_rides(cars: int, balance: Balance) -> float:
    rb = balance.robotics.robotaxi
    return cars * rb.max_rides_per_day * rb.days_per_month


def zone_demand(
    state: GameState, zone: Zone, balance: Balance, data: GameData, brand: float
) -> float:
    """Riders who would take the zone's robotaxis this month (module docstring)."""
    rb = balance.robotics.robotaxi
    c = city(data, zone.city)
    covered = trips_month(state, c, balance, data) * rb.zone_sizes[zone.size].share
    if covered <= TINY or zone.cars <= 0:
        return 0.0
    price = zone.price_cents or c.fare_cents
    priced = (c.fare_cents / price) ** rb.price_elasticity if price > 0 else 0.0
    per_day = covered / rb.days_per_month / PER_THOUSAND
    density = zone.cars / per_day if per_day > TINY else 0.0
    attraction = density / (density + rb.wait_cars)
    trust = TRUST_BASE + brand / SCORE
    willing = covered * acceptance(state, zone.city, balance, data) * priced * attraction * trust
    rivals = rival_fleet(state, zone.city, balance, data) * balance.robotics.scale
    rivals *= rb.zone_sizes[zone.size].share
    share = zone.cars / (zone.cars + rivals) if zone.cars + rivals > TINY else 0.0
    return willing * share


def zone_costs(
    zone: Zone, rides: float, c: CityDef, balance: Balance
) -> tuple[int, int, int, int, float]:
    """(energy, cleaning, insurance, remote assistance) cents and km for the month's rides."""
    rb = balance.robotics.robotaxi
    km = rides * c.km_per_trip * (1 + rb.deadhead)
    energy = round(exact(km) * exact(rb.kwh_per_km) * exact(rb.power_cents))
    cleaning = round(exact(rides) * rb.cleaning_cents)
    insurance = zone.cars * rb.insurance_cents
    remote = round(exact(zone.cars) * exact(rb.operator_cents) / exact(rb.cars_per_operator))
    return energy, cleaning, insurance, remote, km


def car_month_depreciation(zone: Zone, balance: Balance) -> int:
    book = zone.capex_cents - zone.depreciated_cents
    if book <= 0:
        return 0
    return min(
        book, round(exact(zone.capex_cents) / exact(balance.robotics.robotaxi.depreciation_months))
    )


def car_cents_for_zone(state: GameState, zone: Zone, balance: Balance, data: GameData) -> float:
    """A zone's cost a car (its fleet's capex over its cars, or a bought robotaxi's price)."""
    if zone.cars > 0 and zone.capex_cents > 0:
        return zone.capex_cents / zone.cars
    return float(interp(file(data).robotaxi.vehicle_cents, year_at(state.turn)))


def breakeven_rides(c: CityDef, balance: Balance, car_cents: float) -> float:
    """Rides a car a day at which a car's month earns nothing at the city's fare (53.4)."""
    rb = balance.robotics.robotaxi
    per_ride = c.fare_cents - (
        c.km_per_trip * (1 + rb.deadhead) * rb.kwh_per_km * rb.power_cents + rb.cleaning_cents
    )
    fixed = (
        rb.insurance_cents
        + rb.operator_cents / rb.cars_per_operator
        + car_cents / rb.depreciation_months
    )
    if per_ride <= 0:
        return float("inf")
    return fixed / per_ride / rb.days_per_month


def _post(turn: int, company: int, memo: str, debit: str, amount: int) -> LedgerEntry:
    return LedgerEntry(turn, company, memo, (LedgerLine(debit, amount), LedgerLine(CASH, -amount)))


def zones_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """After the month's sales: permits decided, suspensions lifted, rides and their books,
    incidents (module docstring)."""
    if not state.zones:
        return state, [], []
    rb = balance.robotics.robotaxi
    turn = state.turn
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    out: list[Zone] = []
    keep = balance.robotics.history_months
    months: list[ZoneMonth] = []
    f = file(data).robotaxi
    for zone in sorted(state.zones, key=lambda z: z.id):
        c = city(data, zone.city)
        product = state.product(zone.product_id)
        name = f"{product.name if product else 'Robotaxi'} in {c.label}"
        if (
            zone.status == "applied"
            and zone.decision_turn is not None
            and turn >= zone.decision_turn
        ):
            region_index = data.region_index(c.region)
            gen = draws.gen(rng, turn, draws.APPROVAL, region_index, zone.id)
            if float(gen.random()) < rb.approval_chance:
                refuse = rb.refusal_share + rb.incident_refusal * serious_recent(
                    state, zone.company_id
                )
                if float(gen.random()) < refuse:
                    zone = replace(zone, status="refused")
                    logs.append(inbox_item(turn, zone.company_id, "zone_refused", zone=name))
                else:
                    zone = replace(zone, status="active", approved_turn=turn)
                    logs.append(inbox_item(turn, zone.company_id, "zone_approved", zone=name))
        if (
            zone.status == "suspended"
            and zone.suspended_until is not None
            and turn >= zone.suspended_until
        ):
            zone = replace(zone, status="active", suspended_until=None)
            logs.append(inbox_item(turn, zone.company_id, "zone_reinstated", zone=name))
        if zone.status not in OPEN:
            out.append(zone)
            continue
        brand = product.brand if product is not None else 0.0
        rides = 0.0
        if zone.status == "active" and product is not None and product.status == "live":
            served = depot_capacity(state, zone.company_id, zone.city, balance)
            fleet = sum(
                z.cars
                for z in state.zones
                if z.company_id == zone.company_id and z.city == zone.city and z.status in OPEN
            )
            cover = min(1.0, served / fleet) if fleet > 0 else 0.0
            rides = min(
                zone_demand(state, zone, balance, data, brand),
                most_rides(zone.cars, balance) * cover,
            )
        price = zone.price_cents or round(c.fare_cents)
        revenue = round(exact(rides) * exact(price))
        energy, cleaning, insurance, remote, km = zone_costs(zone, rides, c, balance)
        dep = car_month_depreciation(zone, balance)
        company = zone.company_id
        if revenue:
            entries.append(
                LedgerEntry(
                    turn,
                    company,
                    f"Rides: {name}",
                    (LedgerLine(CASH, revenue), LedgerLine(REVENUE_SUBSCRIPTIONS, -revenue)),
                )
            )
        for memo, cents in (
            ("Robotaxi energy", energy),
            ("Robotaxi cleaning", cleaning),
            ("Robotaxi insurance", insurance),
            ("Remote assistance", remote),
        ):
            if cents > 0:
                entries.append(_post(turn, company, f"{memo}: {name}", COGS, cents))
        if dep > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=company,
                    memo=f"Depreciation: robotaxis in {c.label}",
                    debit=DEPRECIATION,
                    credit=ACCUMULATED_DEPRECIATION,
                    amount=dep,
                )
            )
        most = most_rides(zone.cars, balance)
        month = ZoneMonth(
            turn=turn,
            zone_id=zone.id,
            cars=zone.cars,
            rides=rides,
            utilisation=rides / most if most > TINY else 0.0,
            revenue_cents=revenue,
            energy_cents=energy,
            cleaning_cents=cleaning,
            insurance_cents=insurance,
            remote_cents=remote,
            depreciation_cents=dep,
            km=km,
        )
        months.append(month)
        zone = replace(
            zone,
            depreciated_cents=zone.depreciated_cents + dep,
            km_driven=zone.km_driven + km / MILLION,
            month=month,
        )
        # incidents (never stored as draws)
        if km > 0:
            mean = km / MILLION * incident_rate(state, company, balance)
            gen = draws.gen(rng, turn, draws.INCIDENT, zone.id, f.city_index(zone.city))
            n = int(gen.poisson(mean))
            for _ in range(n):
                serious = float(gen.random()) < rb.serious_share
                state, zone, more_entries, more_logs = _incident(
                    state, zone, serious, name, balance
                )
                entries += more_entries
                logs += more_logs
        out.append(zone)
    old = [m for m in state.zone_months if m.turn != turn and m.turn > turn - keep]
    state = replace(
        state,
        zones=tuple(out),
        zone_months=tuple(sorted((*old, *months), key=lambda m: (m.zone_id, m.turn))),
    )
    return state, entries, logs


def _incident(
    state: GameState, zone: Zone, serious: bool, name: str, balance: Balance
) -> tuple[GameState, Zone, list[LedgerEntry], list[LogItem]]:
    rb = balance.robotics.robotaxi
    turn = state.turn
    cost = rb.serious_cents if serious else rb.minor_cents
    entries = [_post(turn, zone.company_id, f"Robotaxi incident: {name}", GENERAL_ADMIN, cost)]
    product = state.product(zone.product_id)
    if product is not None:
        points = rb.brand_points.get("serious" if serious else "minor", 0.0)
        state = with_product(state, replace(product, brand=max(0.0, product.brand - points)))
    until = None
    logs: list[LogItem] = []
    if serious and zone.status == "active":
        until = turn + rb.suspend_months
        zone = replace(zone, status="suspended", suspended_until=until)
        logs.append(
            inbox_item(
                turn,
                zone.company_id,
                "robotaxi_serious",
                zone=name,
                cost_cents=cost,
                months=rb.suspend_months,
            )
        )
        from tst.sim.robotics.events import queue_incident

        state = queue_incident(state, zone)
    elif not serious:
        logs.append(inbox_item(turn, zone.company_id, "robotaxi_minor", zone=name, cost_cents=cost))
    incident = RoboIncident(turn, zone.id, zone.company_id, zone.city, serious, cost, until)
    keep = balance.robotics.history_months
    recent = tuple(i for i in state.robo_incidents if i.turn > turn - keep)
    state = replace(state, robo_incidents=(*recent, incident))
    return state, zone, entries, logs
