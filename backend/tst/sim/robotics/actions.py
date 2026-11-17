"""The player's robotics actions (ADR-0014; docs/formulas.md 53.1-53.3). They take effect at once
and spend the actor's energy. A robot line itself is made with `create_product` (category
`industrial_robots` or `humanoid_robots`), assembled in an assembly plant or under a
contract-manufacturing contract (26.2), and launched as any unit-sale product; a robotaxi service
is a `mobility` product, built and launched like an OS (no segments).

- **InstallRobots** (`robotics.energy.install`): robots in one of the player's live assembly or
  vehicle plants, the group's own (an own live industrial robot line: its unit cost plus the
  integration) or bought (the market's system price). Capex to 1500, cash at once.
- **SetHumanoidSpec** (`energy.design`): a humanoid line's AI model (an own live `ai_models`
  product, or licensed) and chips (an own live `chips_ai_accelerator` product, or bought).
- **OpenZone** (`energy.zone`): apply for a driverless zone in a city (53.3: the region must have
  approved L4 and the company must drive at L4), its size and ride price.
- **AddRobotaxis** (`energy.fleet`): cars for an open zone, from an own L4 car line (its unit cost
  plus the sensor kit) or bought (robotics.yaml's robotaxi price). Capex to 1500, cash at once.
- **BuildDepot** (`energy.depot`): a depot in a city (a facility of kind `depot`, capacity in cars).
- **SetRidePrice** (`energy.price`) and **CloseZone** (`energy.close`: its cars sold at
  `facility.sale_share` of their book value, the rest a loss in 6700).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InsufficientCashError, RoboticsRuleError
from tst.sim.facilities import lifecycle
from tst.sim.hardware.production import unit_bom_cents
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    DEPRECIATION,
    PPE,
    LedgerBalances,
    LedgerEntry,
    LedgerLine,
    account_balance,
)
from tst.sim.log import inbox_item
from tst.sim.money import exact, format_money
from tst.sim.robotics import automation, humanoids
from tst.sim.robotics import robotaxi as rt
from tst.sim.robotics.config import ZONE_SIZES
from tst.sim.robotics.data import file, is_humanoid, is_industrial, is_mobility, year_at
from tst.sim.robotics.models import Depot, HumanoidSpec, PlantAutomation, Zone
from tst.sim.state import GameState
from tst.sim.vehicles import spec as vs
from tst.sim.vehicles.config import interp

VEHICLES: Final = "vehicles"  # tunable-exempt: categories.yaml key of M38's cars


@dataclass(frozen=True, slots=True)
class InstallRobots:
    actor_id: int
    facility_id: int
    robots: int
    product_id: int | None = None  # an own industrial robot line; None buys them
    kind: Literal["install_robots"] = "install_robots"


@dataclass(frozen=True, slots=True)
class SetHumanoidSpec:
    actor_id: int
    product_id: int
    ai_product_id: int | None = None
    chip_product_id: int | None = None
    kind: Literal["set_humanoid_spec"] = "set_humanoid_spec"


@dataclass(frozen=True, slots=True)
class OpenZone:
    actor_id: int
    product_id: int
    city: str
    size: str
    price_cents: int = 0  # 0: the city's human fare
    kind: Literal["open_zone"] = "open_zone"


@dataclass(frozen=True, slots=True)
class AddRobotaxis:
    actor_id: int
    zone_id: int
    cars: int
    car_product_id: int | None = None  # an own L4 car line; None buys robotaxis
    kind: Literal["add_robotaxis"] = "add_robotaxis"


@dataclass(frozen=True, slots=True)
class BuildDepot:
    actor_id: int
    city: str
    capacity: int
    kind: Literal["build_depot"] = "build_depot"


@dataclass(frozen=True, slots=True)
class SetRidePrice:
    actor_id: int
    zone_id: int
    price_cents: int
    kind: Literal["set_ride_price"] = "set_ride_price"


@dataclass(frozen=True, slots=True)
class CloseZone:
    actor_id: int
    zone_id: int
    kind: Literal["close_zone"] = "close_zone"


type RoboticsAction = (
    InstallRobots
    | SetHumanoidSpec
    | OpenZone
    | AddRobotaxis
    | BuildDepot
    | SetRidePrice
    | CloseZone
)
ACTION_TYPES: Final[dict[str, type]] = {
    "install_robots": InstallRobots,
    "set_humanoid_spec": SetHumanoidSpec,
    "open_zone": OpenZone,
    "add_robotaxis": AddRobotaxis,
    "build_depot": BuildDepot,
    "set_ride_price": SetRidePrice,
    "close_zone": CloseZone,
}


def _energy(state: GameState, action: RoboticsAction, key: str, balance: Balance) -> GameState:
    return spend_energy(
        state, action.actor_id, action.kind, balance, cost=balance.robotics.energy[key]
    )


def _capex(turn: int, company: int, memo: str, cents: int) -> LedgerEntry:
    return LedgerEntry(turn, company, memo, (LedgerLine(PPE, cents), LedgerLine(CASH, -cents)))


def _cash(balances: LedgerBalances, company: int, cents: int) -> None:
    if account_balance(balances, company, CASH) < cents:
        raise InsufficientCashError(f"this needs {format_money(cents)} in cash")


def own_robot_cents(state: GameState, product_id: int, balance: Balance, data: GameData) -> float:
    """An own robot installed: its bill of materials, its plant slots' variable cost and the
    integration (the system multiple's share above the robot's price)."""
    product = state.product(product_id)
    assert product is not None
    bom = balance.hardware.bom[product.category]
    run = balance.facility.kinds[balance.hardware.plant_kind].variable_cents * bom.plant_slots
    price = automation.robot_price_cents(state, data)
    integration = price * (file(data).prices.system_mult - 1)
    return unit_bom_cents(state, product, balance, data) + run + integration


def install_robots(
    state: GameState,
    action: InstallRobots,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    ab = balance.robotics.automation
    f = state.facility(action.facility_id)
    if f is None or f.company_id != company or f.kind not in ab.plant_kinds:
        raise RoboticsRuleError("install robots in one of your own assembly or vehicle plants")
    if f.status == "closed":
        raise RoboticsRuleError("the plant is closed")
    if not 1 <= action.robots <= ab.max_robots:
        raise RoboticsRuleError(f"an order adds 1-{ab.max_robots:,} robots")
    current = state.plant_automation(f.id)
    have = current.robots if current is not None else 0
    most = automation.robots_for(f, ab.max_share, balance)
    if have + action.robots > most:
        raise RoboticsRuleError(f"the plant takes at most {most:,} robots ({have:,} installed)")
    if action.product_id is not None:
        p = state.product(action.product_id)
        if p is None or p.company_id != company or not is_industrial(p, balance):
            raise RoboticsRuleError("own robots come from one of your industrial robot lines")
        if p.status != "live":
            raise RoboticsRuleError(f"{p.name} is not live")
        unit = own_robot_cents(state, p.id, balance, data)
        source = "own"
    else:
        unit = automation.system_cents(state, data)
        source = "bought"
    cents = round(exact(action.robots) * exact(unit))
    _cash(balances, company, cents)
    state = _energy(state, action, "install", balance)
    robots = have + action.robots
    new = PlantAutomation(
        facility_id=f.id,
        company_id=company,
        robots=robots,
        capex_cents=cents,
        own_robots=action.robots if action.product_id is not None else 0,
    )
    if current is not None:
        new = replace(
            current,
            robots=robots,
            capex_cents=current.capex_cents + cents,
            own_robots=current.own_robots + new.own_robots,
        )
    others = tuple(a for a in state.plant_automations if a.facility_id != f.id)
    state = replace(
        state,
        plant_automations=tuple(sorted((*others, new), key=lambda a: a.facility_id)),
    )
    level = automation.level_of(f, robots, balance)
    saving = automation.saving_cents(state, f, level, balance, data)
    service = round(
        exact(robots)
        * exact(automation.robot_price_cents(state, data))
        * exact(file(data).prices.service_share)
        / 12
    )
    name = lifecycle.facility_name(f, balance, data)
    log = inbox_item(
        state.turn,
        company,
        "robots_installed",
        facility=name,
        robots=f"{action.robots:,}",
        source=source,
        capex_cents=cents,
        level=f"{level:.0%}",
        saving_cents=round(saving),
        service_cents=service,
    )
    entry = _capex(state.turn, company, f"Robots installed: {name}", cents)
    return Outcome(state, (entry,), (log,))


def _own_live(
    state: GameState, product_id: int | None, company: int, category: str, what: str
) -> int | None:
    if product_id is None:
        return None
    p = state.product(product_id)
    if p is None or p.company_id != company or p.category != category or p.status != "live":
        raise RoboticsRuleError(f"choose one of your own live {what}")
    return p.id


def set_humanoid_spec(
    state: GameState, action: SetHumanoidSpec, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    product = state.product(action.product_id)
    if product is None or product.company_id != company or not is_humanoid(product, balance):
        raise RoboticsRuleError("set a design on one of your own humanoid lines")
    ai = _own_live(state, action.ai_product_id, company, humanoids.AI_CATEGORY, "AI models")
    chip = _own_live(
        state, action.chip_product_id, company, humanoids.CHIP_CATEGORY, "AI accelerators"
    )
    state = _energy(state, action, "design", balance)
    spec = HumanoidSpec(product.id, ai, chip)
    specs = tuple(s for s in state.humanoid_specs if s.product_id != product.id)
    state = replace(state, humanoid_specs=tuple(sorted((*specs, spec), key=lambda s: s.product_id)))
    log = inbox_item(
        state.turn,
        company,
        "humanoid_designed",
        product=product.name,
        ai="your own AI model" if ai is not None else "a licensed AI model",
        chips="your own accelerators" if chip is not None else "bought accelerators",
        capability=f"{humanoids.capability(state, product, balance):.0f}",
    )
    return Outcome(state, (), (log,))


def _zone_name(state: GameState, zone: Zone, data: GameData) -> str:
    product = state.product(zone.product_id)
    return f"{product.name if product else 'Robotaxi'} in {rt.city(data, zone.city).label}"


def open_zone(state: GameState, action: OpenZone, balance: Balance, data: GameData) -> Outcome:
    company = acting_company(state, action.actor_id)
    product = state.product(action.product_id)
    if product is None or product.company_id != company or not is_mobility(product, balance):
        raise RoboticsRuleError("open a zone for one of your own robotaxi services")
    if product.status != "live":
        raise RoboticsRuleError(f"{product.name} must be launched first")
    c = file(data).robotaxi.city(action.city)
    if c is None:
        raise RoboticsRuleError(f"unknown city {action.city!r}")
    if action.size not in ZONE_SIZES or action.size not in balance.robotics.robotaxi.zone_sizes:
        raise RoboticsRuleError(f"a zone is {', '.join(ZONE_SIZES)}")
    if action.price_cents < 0:
        raise RoboticsRuleError("a ride's price cannot be negative")
    if not vs.approved(state, c.region, rt.L4, balance, data):
        raise RoboticsRuleError(
            f"{data.region(c.region).label} has not approved driverless (L4) service"
        )
    if not rt.can_drive_l4(state, company, balance):
        raise RoboticsRuleError("your autonomy research and AI model do not reach L4 yet")
    if any(
        z.company_id == company and z.city == c.key and z.status in ("applied", *rt.OPEN)
        for z in state.zones
    ):
        raise RoboticsRuleError(f"you already have a zone in {c.label}")
    state = _energy(state, action, "zone", balance)
    zid = max((z.id for z in state.zones), default=0) + 1
    review = balance.robotics.robotaxi.zone_sizes[action.size].review_months
    zone = Zone(
        id=zid,
        product_id=product.id,
        company_id=company,
        city=c.key,
        size=action.size,  # type: ignore[arg-type]
        status="applied",
        applied_turn=state.turn,
        decision_turn=state.turn + review,
        price_cents=action.price_cents,
    )
    state = replace(state, zones=(*state.zones, zone))
    log = inbox_item(
        state.turn,
        company,
        "zone_applied",
        zone=_zone_name(state, zone, data),
        size=action.size,
        months=review,
    )
    return Outcome(state, (), (log,))


def _zone(state: GameState, zone_id: int, company: int) -> Zone:
    zone = state.zone(zone_id)
    if zone is None or zone.company_id != company:
        raise RoboticsRuleError("choose one of your own zones")
    return zone


def car_cents(
    state: GameState, company: int, car_product_id: int | None, balance: Balance, data: GameData
) -> float:
    """A robotaxi's cost: an own L4 car's unit cost (its bill of materials, the vehicle plant's
    variable cost) plus the sensor kit, or a bought robotaxi's price."""
    t = year_at(state.turn)
    r = file(data).robotaxi
    if car_product_id is None:
        return interp(r.vehicle_cents, t)
    p = state.product(car_product_id)
    if p is None or p.company_id != company or p.category != VEHICLES:
        raise RoboticsRuleError("own cars come from one of your car lines")
    spec = vs.spec_of(state, p, data)
    if vs.capable_level(state, spec, company, balance) != rt.L4:
        raise RoboticsRuleError(f"{p.name} cannot drive at L4")
    plant = balance.facility.kinds[balance.vehicles.plant.kind].variable_cents
    return vs.unit_cost(state, p, balance, data).total + plant + interp(r.sensor_cents, t)


def add_robotaxis(
    state: GameState,
    action: AddRobotaxis,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    zone = _zone(state, action.zone_id, company)
    rb = balance.robotics.robotaxi
    if zone.status not in ("applied", *rt.OPEN):
        raise RoboticsRuleError("the zone is closed")
    if not 1 <= action.cars <= rb.max_cars:
        raise RoboticsRuleError(f"an order adds 1-{rb.max_cars:,} cars")
    if not rt.can_drive_l4(state, company, balance):
        raise RoboticsRuleError("your autonomy research and AI model do not reach L4 yet")
    unit = car_cents(state, company, action.car_product_id, balance, data)
    cents = round(exact(action.cars) * exact(unit))
    _cash(balances, company, cents)
    state = _energy(state, action, "fleet", balance)
    new = replace(
        zone,
        cars=zone.cars + action.cars,
        capex_cents=zone.capex_cents + cents,
        car_product_id=action.car_product_id
        if action.car_product_id is not None
        else zone.car_product_id,
    )
    state = replace(state, zones=tuple(new if z.id == zone.id else z for z in state.zones))
    name = _zone_name(state, zone, data)
    log = inbox_item(
        state.turn,
        company,
        "fleet_added",
        zone=name,
        cars=f"{action.cars:,}",
        source="own" if action.car_product_id is not None else "bought",
        capex_cents=cents,
        months=rb.depreciation_months,
    )
    return Outcome(state, (_capex(state.turn, company, f"Robotaxis: {name}", cents),), (log,))


def build_depot(
    state: GameState,
    action: BuildDepot,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    c = file(data).robotaxi.city(action.city)
    if c is None:
        raise RoboticsRuleError(f"unknown city {action.city!r}")
    kind = balance.facility.kinds[balance.robotics.depot_kind]
    sizes = kind.sizes or balance.facility.sizes
    if action.capacity not in sizes:
        raise RoboticsRuleError(f"a depot serves {', '.join(f'{s:,}' for s in sizes)} cars")
    q = lifecycle.quote(
        state, company, balance.robotics.depot_kind, c.region, action.capacity, balance, data
    )
    _cash(balances, company, q.monthly_capex_cents)
    state = _energy(state, action, "depot", balance)
    state, facility = lifecycle.order_build(state, company, q)
    depot = Depot(facility.id, company, c.key)
    state = replace(
        state, depots=tuple(sorted((*state.depots, depot), key=lambda d: d.facility_id))
    )
    log = inbox_item(
        state.turn,
        company,
        "depot_ordered",
        facility=lifecycle.facility_name(facility, balance, data),
        units=f"{q.capacity:,} cars",
        city=c.label,
        capex_cents=q.capex_cents,
        months=q.build_months,
        ready=format_turn(facility.ready_turn),
        staff=q.staff_needed,
    )
    return Outcome(state, (), (log,))


def set_ride_price(state: GameState, action: SetRidePrice, balance: Balance) -> Outcome:
    company = acting_company(state, action.actor_id)
    zone = _zone(state, action.zone_id, company)
    if action.price_cents < 0:
        raise RoboticsRuleError("a ride's price cannot be negative")
    state = _energy(state, action, "price", balance)
    new = replace(zone, price_cents=action.price_cents)
    return Outcome(replace(state, zones=tuple(new if z.id == zone.id else z for z in state.zones)))


def close_zone(state: GameState, action: CloseZone, balance: Balance, data: GameData) -> Outcome:
    company = acting_company(state, action.actor_id)
    zone = _zone(state, action.zone_id, company)
    if zone.status == "closed":
        raise RoboticsRuleError("the zone is already closed")
    state = _energy(state, action, "close", balance)
    book = zone.capex_cents - zone.depreciated_cents
    sale = round(exact(book) * exact(balance.facility.sale_share))
    entries: list[LedgerEntry] = []
    if book > 0:
        # the cars leave the books: cash for the sale, the rest a loss, cost and depreciation out
        entries.append(
            LedgerEntry(
                state.turn,
                company,
                f"Robotaxis sold: {_zone_name(state, zone, data)}",
                (
                    LedgerLine(CASH, sale),
                    LedgerLine(DEPRECIATION, book - sale),
                    LedgerLine(ACCUMULATED_DEPRECIATION, zone.depreciated_cents),
                    LedgerLine(PPE, -zone.capex_cents),
                ),
            )
        )
    new = replace(zone, status="closed", cars=0, capex_cents=0, depreciated_cents=0)
    state = replace(state, zones=tuple(new if z.id == zone.id else z for z in state.zones))
    log = inbox_item(
        state.turn,
        company,
        "zone_closed",
        zone=_zone_name(state, zone, data),
        cars=f"{zone.cars:,}",
        sale_cents=sale,
    )
    return Outcome(state, tuple(entries), (log,))


def apply_robotics(
    state: GameState,
    action: RoboticsAction,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    if data.robotics is None:
        raise RoboticsRuleError("this game has no robotics markets")
    match action:
        case InstallRobots():
            return install_robots(state, action, balance, data, balances)
        case SetHumanoidSpec():
            return set_humanoid_spec(state, action, balance, data)
        case OpenZone():
            return open_zone(state, action, balance, data)
        case AddRobotaxis():
            return add_robotaxis(state, action, balance, data, balances)
        case BuildDepot():
            return build_depot(state, action, balance, data, balances)
        case SetRidePrice():
            return set_ride_price(state, action, balance)
        case CloseZone():
            return close_zone(state, action, balance, data)
