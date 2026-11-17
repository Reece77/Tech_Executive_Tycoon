"""The player's vehicle actions (ADR-0014; docs/formulas.md 49.1-49.5). They take effect at once
and spend the actor's energy. A car line itself is made with `create_product` (category
`vehicles`), assembled in a vehicle plant (`build_facility`, kind `vehicle_plant`) or under a
contract-manufacturing contract (26.2), and launched as any unit-sale product.

- **SetVehicleSpec** (`vehicles.energy.design`): a line's pack (kWh within `spec.pack_kwh`),
  chemistry (`nmc`, `lfp`), charging speed, the autonomy level it aims for, its platform (`own`
  with an own live OS product, `licensed` Android Automotive, or `closed`) and its cells (a cell
  maker, or `own` for the group's cell plants, bought at market when short).
- **BuildCellPlant** (`vehicles.energy.cell_plant`, stage `cell_plant.stage`): a cell plant of a
  chemistry and size in a region; true capex = the quote x (1 + a hidden overrun, stream vehicles
  (2, facility)), revealed only as it is paid.
- **BuildChargingNetwork** (`vehicles.energy.charging`): chargers in a region, open or exclusive.
- **SetChargingAccess** (`vehicles.energy.exclusive`): make a network open or exclusive.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InsufficientCashError, VehicleRuleError
from tst.sim.facilities import lifecycle
from tst.sim.facilities.lifecycle import BuildQuote
from tst.sim.facilities.models import Facility
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import inbox_item
from tst.sim.money import exact
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility
from tst.sim.vehicles import cells, draws
from tst.sim.vehicles import spec as vs
from tst.sim.vehicles.config import CHEMISTRIES, LEVELS, OWN, PLATFORM_CHOICES
from tst.sim.vehicles.data import is_vehicle
from tst.sim.vehicles.models import CellPlant, ChargingNetwork, VehicleSpec

OS_CATEGORY: Final = "os"  # tunable-exempt: categories.yaml key of an own OS (M31, 44.1)


@dataclass(frozen=True, slots=True)
class SetVehicleSpec:
    actor_id: int
    product_id: int
    pack_kwh: float
    chemistry: str
    charge_kw: float
    autonomy: str
    platform: str
    cells: str
    os_product_id: int | None = None
    kind: Literal["set_vehicle_spec"] = "set_vehicle_spec"


@dataclass(frozen=True, slots=True)
class BuildCellPlant:
    actor_id: int
    region: str
    capacity: int  # MWh of cells a month
    chemistry: str
    city: str | None = None
    kind: Literal["build_cell_plant"] = "build_cell_plant"


@dataclass(frozen=True, slots=True)
class BuildChargingNetwork:
    actor_id: int
    region: str
    chargers: int
    exclusive: bool = False
    city: str | None = None
    kind: Literal["build_charging_network"] = "build_charging_network"


@dataclass(frozen=True, slots=True)
class SetChargingAccess:
    actor_id: int
    facility_id: int
    exclusive: bool
    kind: Literal["set_charging_access"] = "set_charging_access"


type VehicleAction = SetVehicleSpec | BuildCellPlant | BuildChargingNetwork | SetChargingAccess
ACTION_TYPES: Final[dict[str, type]] = {
    "set_vehicle_spec": SetVehicleSpec,
    "build_cell_plant": BuildCellPlant,
    "build_charging_network": BuildChargingNetwork,
    "set_charging_access": SetChargingAccess,
}


def set_spec(state: GameState, action: SetVehicleSpec, balance: Balance, data: GameData) -> Outcome:
    company = acting_company(state, action.actor_id)
    product = state.product(action.product_id)
    if product is None or product.company_id != company or not is_vehicle(product, balance):
        raise VehicleRuleError("set a design on one of your own car lines")
    sb = balance.vehicles.spec
    if not sb.pack_kwh.lo <= action.pack_kwh <= sb.pack_kwh.hi:
        raise VehicleRuleError(f"a pack is {sb.pack_kwh.lo:g}-{sb.pack_kwh.hi:g} kWh")
    if not sb.charge_kw.lo <= action.charge_kw <= sb.charge_kw.hi:
        raise VehicleRuleError(f"charging is {sb.charge_kw.lo:g}-{sb.charge_kw.hi:g} kW")
    if action.chemistry not in CHEMISTRIES:
        raise VehicleRuleError(f"chemistry is one of {', '.join(CHEMISTRIES)}")
    if action.autonomy not in LEVELS or action.autonomy not in balance.vehicles.levels:
        raise VehicleRuleError(f"autonomy is one of {', '.join(balance.vehicles.levels)}")
    if action.platform not in PLATFORM_CHOICES:
        raise VehicleRuleError(f"platform is one of {', '.join(PLATFORM_CHOICES)}")
    if action.cells not in cells.cell_sources(data):
        raise VehicleRuleError(f"unknown cell source {action.cells!r}")
    os_id = None
    if action.platform == OWN:
        os_product = state.product(action.os_product_id) if action.os_product_id else None
        if (
            os_product is None
            or os_product.company_id != company
            or os_product.category != OS_CATEGORY
            or os_product.status != "live"
        ):
            raise VehicleRuleError("an own platform needs one of your live operating systems")
        os_id = os_product.id
    old = state.vehicle_spec(product.id)
    spec = VehicleSpec(
        product_id=product.id,
        pack_kwh=float(action.pack_kwh),
        chemistry=action.chemistry,  # type: ignore[arg-type]
        charge_kw=float(action.charge_kw),
        autonomy=action.autonomy,  # type: ignore[arg-type]
        platform=action.platform,  # type: ignore[arg-type]
        cells=action.cells,
        origin=old.origin if old is not None else "",
        os_product_id=os_id,
    )
    state = spend_energy(
        state, action.actor_id, "set_vehicle_spec", balance, cost=balance.vehicles.energy["design"]
    )
    specs = tuple(s for s in state.vehicle_specs if s.product_id != product.id)
    state = replace(state, vehicle_specs=tuple(sorted((*specs, spec), key=lambda s: s.product_id)))
    v = data.vehicles
    assert v is not None
    log = inbox_item(
        state.turn,
        company,
        "vehicle_designed",
        product=product.name,
        pack=f"{spec.pack_kwh:g}",
        chemistry=v.battery.chemistries[spec.chemistry].label,
        range=f"{vs.range_km(spec, state.turn, balance, data):,.0f}",
        charge=f"{spec.charge_kw:g}",
        level=balance.vehicles.levels[spec.autonomy].label,
        platform={
            "own": "your own OS",
            "licensed": "Android Automotive",
            "closed": "a closed system",
        }[spec.platform],
        cells="your own cell plants" if spec.cells == OWN else v.cell_maker(spec.cells).name,
    )
    return Outcome(state, (), (log,))


def _order(
    state: GameState,
    company: int,
    kind: str,
    region: str,
    capacity: int,
    city: str | None,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
    overrun: float = 0.0,
) -> tuple[GameState, Facility, BuildQuote]:
    if region not in data.region_keys:
        raise VehicleRuleError(f"unknown region {region!r}")
    k = balance.facility.kinds[kind]
    sizes = k.sizes or balance.facility.sizes
    if capacity not in sizes:
        raise VehicleRuleError(
            f"a {k.label.lower()} has {', '.join(f'{s:,}' for s in sizes)} {k.unit}"
        )
    if city is not None and (not data.has_city(city) or data.city(city).region != region):
        raise VehicleRuleError(f"{city!r} is not a city in that region")
    q = lifecycle.quote(state, company, kind, region, capacity, balance, data, None)
    if account_balance(balances, company, CASH) < q.monthly_capex_cents:
        raise InsufficientCashError(f"the first capex payment needs {q.monthly_capex_cents} cents")
    true_capex = round(q.capex_cents * (1 + exact(overrun)))
    state, facility = lifecycle.order_build(state, company, replace(q, capex_cents=true_capex))
    if city is not None:
        facility = replace(facility, city=city)
        state = with_facility(state, facility)
    return state, facility, q


def build_cell_plant(
    state: GameState,
    action: BuildCellPlant,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    cb = balance.vehicles.cell_plant
    if state.company(company).stage < cb.stage:
        raise VehicleRuleError(f"a cell plant needs stage {cb.stage}")
    if action.chemistry not in CHEMISTRIES:
        raise VehicleRuleError(f"chemistry is one of {', '.join(CHEMISTRIES)}")
    fid = state.next_ids.facility
    rng = RngFactory(state.save_meta.master_seed)
    u = float(draws.gen(rng, state.turn, draws.CELL_PLANT, fid).random())
    overrun = cb.overrun.lo + (cb.overrun.hi - cb.overrun.lo) * u
    state = spend_energy(
        state,
        action.actor_id,
        "build_cell_plant",
        balance,
        cost=balance.vehicles.energy["cell_plant"],
    )
    state, facility, q = _order(
        state,
        company,
        cb.kind,
        action.region,
        action.capacity,
        action.city,
        balance,
        data,
        balances,
        overrun,
    )
    plant = CellPlant(
        facility.id,
        company,
        action.chemistry,  # type: ignore[arg-type]
        estimate_cents=q.capex_cents,
        overrun=overrun,
    )
    state = replace(
        state, cell_plants=tuple(sorted((*state.cell_plants, plant), key=lambda c: c.facility_id))
    )
    v = data.vehicles
    assert v is not None
    log = inbox_item(
        state.turn,
        company,
        "cell_plant_ordered",
        facility=lifecycle.facility_name(facility, balance, data),
        units=f"{q.capacity:,} MWh a month",
        chemistry=v.battery.chemistries[action.chemistry].label,
        region=data.region(action.region).label,
        capex_cents=q.capex_cents,
        months=q.build_months,
        ready=format_turn(facility.ready_turn),
        staff=q.staff_needed,
    )
    return Outcome(state, (), (log,))


def build_charging(
    state: GameState,
    action: BuildChargingNetwork,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    state = spend_energy(
        state,
        action.actor_id,
        "build_charging_network",
        balance,
        cost=balance.vehicles.energy["charging"],
    )
    state, facility, q = _order(
        state,
        company,
        balance.vehicles.charging.kind,
        action.region,
        action.chargers,
        action.city,
        balance,
        data,
        balances,
    )
    net = ChargingNetwork(facility.id, company, action.region, exclusive=action.exclusive)
    state = replace(
        state,
        charging_networks=tuple(
            sorted((*state.charging_networks, net), key=lambda n: n.facility_id)
        ),
    )
    log = inbox_item(
        state.turn,
        company,
        "charging_ordered",
        facility=lifecycle.facility_name(facility, balance, data),
        units=f"{q.capacity:,} chargers",
        region=data.region(action.region).label,
        mode="exclusive to your cars" if action.exclusive else "open to every EV",
        capex_cents=q.capex_cents,
        months=q.build_months,
        ready=format_turn(facility.ready_turn),
    )
    return Outcome(state, (), (log,))


def set_access(state: GameState, action: SetChargingAccess, balance: Balance) -> Outcome:
    company = acting_company(state, action.actor_id)
    net = next((n for n in state.charging_networks if n.facility_id == action.facility_id), None)
    if net is None or net.company_id != company:
        raise VehicleRuleError("choose one of your charging networks")
    state = spend_energy(
        state,
        action.actor_id,
        "set_charging_access",
        balance,
        cost=balance.vehicles.energy["exclusive"],
    )
    nets = tuple(
        replace(n, exclusive=action.exclusive) if n.facility_id == net.facility_id else n
        for n in state.charging_networks
    )
    return Outcome(replace(state, charging_networks=nets))


def apply_vehicles(
    state: GameState,
    action: VehicleAction,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    if data.vehicles is None:
        raise VehicleRuleError("this game has no vehicles market")
    match action:
        case SetVehicleSpec():
            return set_spec(state, action, balance, data)
        case BuildCellPlant():
            return build_cell_plant(state, action, balance, data, balances)
        case BuildChargingNetwork():
            return build_charging(state, action, balance, data, balances)
        case SetChargingAccess():
            return set_access(state, action, balance)
