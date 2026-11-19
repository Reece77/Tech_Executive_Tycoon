"""Satellites and constellations (docs/formulas.md 56.2), and the launches that carry them (56.1).

Each month after the sales, for each constellation (by id):

- **Build.** Up to `build_per_month` satellites while the plan's shells are short (planned
  `shells x shell_sats` less those in orbit past `replace_ahead_months` from now and those
  waiting), so replacements are built before their cohort retires: first in the
  group's live satellite plants (their capacity, satellites a month), the rest bought
  (`satellite.bought_mult` x the made cost, at most `bought_per_month`). A satellite's made cost:
  `mass x satellite_cents_per_kg(year) x (1 + life_cost x (life - lo) / (hi - lo))` (x
  `eo_cost_mult` for imaging, x `d2d.cost_mult` for a D2D-capable design), less
  `chip_share x own_chip_cut` with the group's own live chips. Capitalized (1500).
- **Launch.** Up to `launches_per_month` flights while satellites wait: on the group's own vehicle
  line (its flight cost; pads left after the month's customer launches; not while grounded) or
  bought (space.yaml's reference vehicle's price). A flight carries `payload flown / mass`
  satellites. An insured payload pays `premium_rate` of its value. The flight can fail (stream
  space (1, ...)): the satellites are lost (written off, 6700), the insurer pays `insured_share`
  of their value (4900), an own vehicle is grounded and its line loses brand, and for the player
  the loss is a critical event. Otherwise the satellites join the lowest shell short of full as a
  cohort that serves for the design's life, depreciated straight line (6700 / 1510).
- **Retire.** A cohort at its end of life is deorbited (`deorbit_cents` each, x the tighter
  debris rule's `deorbit_mult` once it has come) and leaves the books.
- **Coverage.** A shell is complete with `complete_share` of its satellites in orbit; complete
  shells open their regions (`constellation.shells[i].regions`). Capacity = satellites x mass x
  `gbps_per_kg` (a D2D design keeps `d2d.gbps_share` of it for phones). Ground stations cost
  `ground_station_cents` a covered region a month; under the debris rule each satellite in orbit
  pays `debris.fee_cents` a month.
- **Payback** (56.4 target 3): the constellation's cumulative cash flow, its product's revenue less
  its subscribers' hosting (the ground segment, 6300), everything above and its terminals'
  subsidy; `paid_back_turn` is the first month it is back
  above zero.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import (
    ACCUMULATED_DEPRECIATION,
    CASH,
    DEPRECIATION,
    GENERAL_ADMIN,
    OTHER_INCOME,
    PPE,
    LedgerEntry,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.products.models import Product
from tst.sim.rng import RngFactory
from tst.sim.space import draws, launch
from tst.sim.space.data import TINY, file, year_at
from tst.sim.space.models import (
    Cohort,
    Constellation,
    ConstellationMonth,
    LaunchRecord,
    LaunchSpec,
    SpaceState,
)
from tst.sim.state import GameState, with_product
from tst.sim.vehicles.config import interp

CHIP_CATEGORIES: Final = (
    "chips_mobile_soc",
    "chips_server_cpu",
    "chips_ai_accelerator",
)  # tunable-exempt: categories.yaml keys
BOUGHT: Final = "Bought launch"  # tunable-exempt: a label


def satellite_cents(state: GameState, c: Constellation, balance: Balance, data: GameData) -> float:
    """A satellite's made cost this month (module docstring)."""
    sb = balance.space.satellite
    per_kg = interp(file(data).satellite_cost_cents, year_at(state.turn))
    span = sb.life_months.hi - sb.life_months.lo
    life = (c.life_months - sb.life_months.lo) / span if span > 0 else 0.0
    cents = c.mass_kg * per_kg * (1 + sb.life_cost * life)
    if c.kind == "eo":
        cents *= sb.eo_cost_mult
    if c.d2d:
        cents *= balance.space.d2d.cost_mult
    if own_chips(state, c.company_id):
        cents *= 1 - sb.chip_share * sb.own_chip_cut
    return cents


def own_chips(state: GameState, company_id: int) -> bool:
    return any(
        p.company_id == company_id and p.category in CHIP_CATEGORIES and p.status == "live"
        for p in state.products
    )


def plant_capacity(state: GameState, company_id: int, balance: Balance) -> int:
    kind = balance.space.plant_kind
    return sum(
        f.live_capacity(state.turn) for f in state.company_facilities(company_id) if f.kind == kind
    )


def planned(c: Constellation, balance: Balance) -> int:
    return c.shells * balance.space.constellation.shell_sats


def complete_shells(c: Constellation, balance: Balance) -> tuple[int, ...]:
    cb = balance.space.constellation
    need = cb.shell_sats * cb.complete_share
    return tuple(i for i in range(c.shells) if c.in_shell(i) + TINY >= need)


def covered_regions(c: Constellation, balance: Balance) -> tuple[str, ...]:
    """Regions the constellation's complete shells open (EO: every region once it sells)."""
    shells = balance.space.constellation.shells
    out: list[str] = []
    for i in complete_shells(c, balance):
        if i < len(shells):
            out += [r for r in shells[i].regions if r not in out]
    return tuple(out)


def capacity_gbps(c: Constellation, balance: Balance) -> tuple[float, float]:
    """(broadband Gbps, direct-to-device Gbps) in orbit."""
    total = c.in_orbit() * c.mass_kg * balance.space.satellite.gbps_per_kg
    if c.kind != "broadband":
        return 0.0, 0.0
    if not c.d2d:
        return total, 0.0
    share = balance.space.d2d.gbps_share
    return total * (1 - share), total * share


def _shell_for(c: Constellation, ahead: int, balance: Balance) -> int:
    """The shell a new cohort joins: the one with the fewest satellites staying past `ahead` (its
    shortfall once its oldest cohorts retire), the lowest first."""

    def staying(i: int) -> int:
        return sum(x.count for x in c.cohorts if x.shell == i and x.retire_turn > ahead)

    return min(range(c.shells), key=lambda i: (staying(i), i))


def _entry(turn: int, company: int, memo: str, debit: str, credit: str, cents: int) -> LedgerEntry:
    return LedgerEntry.transfer(
        turn=turn, company_id=company, memo=memo, debit=debit, credit=credit, amount=cents
    )


def debris_active(state: GameState) -> bool:
    t = state.space.world.debris_turn
    return t is not None and state.turn >= t


def month(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    revenue: dict[int, int],
    pads_used: dict[int, float],
) -> tuple[GameState, list[LedgerEntry], list[LogItem], list[LaunchRecord], list[int]]:
    """Every constellation's month (module docstring). `revenue`: product id -> this month's
    revenue; `pads_used`: company -> launches its sites flew for customers. Returns the state,
    entries, logs, the launches flown and the constellations that lost satellites."""
    sb = balance.space
    turn = state.turn
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    flown: list[LaunchRecord] = []
    lost_ids: list[int] = []
    plant_left: dict[int, int] = {}
    pads_left: dict[int, float] = {}
    out: list[Constellation] = []
    months: list[ConstellationMonth] = []
    for c in sorted(state.space.constellations, key=lambda x: x.id):
        company = c.company_id
        memo = f"Constellation {c.name}"
        spend = 0
        received = 0
        # --- build ---
        ahead = turn + sb.constellation.replace_ahead_months
        staying = sum(x.count for x in c.cohorts if x.retire_turn > ahead)
        need = max(0, planned(c, balance) - staying - c.ground)
        want = min(c.build_per_month, need)
        if company not in plant_left:
            plant_left[company] = plant_capacity(state, company, balance)
        made = min(want, plant_left[company])
        plant_left[company] -= made
        bought = min(want - made, sb.satellite.bought_per_month)
        unit = satellite_cents(state, c, balance, data)
        build = round(
            exact(made) * exact(unit) + exact(bought) * exact(unit * sb.satellite.bought_mult)
        )
        if build > 0:
            entries.append(_entry(turn, company, f"{memo}: satellites built", PPE, CASH, build))
            spend += build
        ground = c.ground + made + bought
        capex = c.capex_cents + build
        # unit value of a waiting satellite: its build cost (made and bought averaged in)
        wait_value = capex - sum(x.cost_cents for x in c.cohorts)
        cohorts = list(c.cohorts)
        lost_now = 0
        # --- launch ---
        vehicle: Product | None = (
            state.product(c.vehicle_product_id) if c.vehicle_product_id is not None else None
        )
        spec = state.space.spec(vehicle.id) if vehicle is not None else None
        for _ in range(min(c.launches_per_month, sb.max_launches_month)):
            if ground <= 0:
                break
            own = vehicle is not None and spec is not None and vehicle.status == "live"
            if (
                own
                and spec is not None
                and spec.grounded_until is not None
                and turn < spec.grounded_until
            ):
                break  # the line is grounded: wait for it
            if own and vehicle is not None and spec is not None:
                cost = launch.flight_cost(
                    spec.payload_kg,
                    vehicle.quality,
                    spec.flights,
                    launch.capable_level(state, spec, company, balance),
                    balance,
                )
                if company not in pads_left:
                    pads = launch.site_capacity(state, company, balance) * cost.pad_rate
                    pads_left[company] = pads - pads_used.get(company, 0.0)
                if pads_left[company] < 1 - TINY:
                    break
                pads_left[company] -= 1
                price, payload = cost.flight_cents, cost.payload_kg
                rate = launch.failure_rate(spec.flights, vehicle.quality, balance)
                gen = draws.gen(rng, turn, draws.FLIGHT, vehicle.id, spec.flights)
                label = vehicle.name
            else:
                price, payload = launch.bought_price_cents(state, balance, data)
                rate = sb.failure.floor
                gen = draws.gen(rng, turn, draws.FLIGHT, 0, c.id, len(flown))
                label = BOUGHT
            sats = min(ground, int(payload // c.mass_kg))
            if sats <= 0:
                break
            launch_cents = round(price)
            entries.append(_entry(turn, company, f"{memo}: launch", PPE, CASH, launch_cents))
            spend += launch_cents
            capex += launch_cents
            each_wait = wait_value / ground if ground > 0 else 0.0
            value = round(exact(each_wait) * sats) + launch_cents
            if c.insured:
                premium = round(exact(value) * exact(sb.failure.premium_rate))
                if premium > 0:
                    entries.append(
                        _entry(
                            turn, company, f"{memo}: launch insurance", GENERAL_ADMIN, CASH, premium
                        )
                    )
                    spend += premium
            failed = float(gen.random()) < rate
            ground -= sats
            wait_value -= round(exact(each_wait) * sats)
            insured = 0
            if failed:
                lost_now += sats
                entries.append(
                    _entry(turn, company, f"{memo}: satellites lost", DEPRECIATION, PPE, value)
                )
                capex -= value
                if c.insured:
                    insured = round(exact(value) * exact(sb.failure.insured_share))
                    if insured > 0:
                        entries.append(
                            _entry(
                                turn,
                                company,
                                f"{memo}: insurance paid",
                                CASH,
                                OTHER_INCOME,
                                insured,
                            )
                        )
                        received += insured
            else:
                cohorts.append(
                    Cohort(
                        shell=_shell_for(replace(c, cohorts=tuple(cohorts)), ahead, balance),
                        launch_turn=turn,
                        count=sats,
                        cost_cents=value,
                        retire_turn=turn + c.life_months,
                    )
                )
            if own and vehicle is not None and spec is not None:
                state, spec = record_flight(state, vehicle, spec, failed, rng, balance)
            flown.append(
                LaunchRecord(
                    turn=turn,
                    company_id=company,
                    product_id=vehicle.id if own and vehicle is not None else None,
                    vehicle=label,
                    purpose="own",
                    constellation_id=c.id,
                    satellites=sats,
                    ok=not failed,
                    insured_cents=insured,
                )
            )
            if failed:
                break  # the programme stands down for the rest of the month
        # --- retire, depreciate ---
        retired = 0
        keep: list[Cohort] = []
        dep = 0
        depreciated = c.depreciated_cents
        for x in cohorts:
            gross = x.cost_cents
            if x.retire_turn <= turn:
                retired += x.count
                rest = gross - x.depreciated_cents
                if rest > 0:
                    entries.append(
                        _entry(
                            turn,
                            company,
                            f"{memo}: depreciation",
                            DEPRECIATION,
                            ACCUMULATED_DEPRECIATION,
                            rest,
                        )
                    )
                if gross > 0:
                    entries.append(
                        _entry(
                            turn,
                            company,
                            f"{memo}: satellites deorbited",
                            ACCUMULATED_DEPRECIATION,
                            PPE,
                            gross,
                        )
                    )
                capex -= gross
                depreciated -= x.depreciated_cents
                continue
            life = max(1, x.retire_turn - x.launch_turn)
            d = min(gross - x.depreciated_cents, round(exact(gross) / exact(life)))
            dep += d
            keep.append(replace(x, depreciated_cents=x.depreciated_cents + d))
        # money-exact: rate (a satellite's disposal, rounded where the month's disposal posts)
        disposal_each = sb.constellation.deorbit_cents * (
            sb.debris.deorbit_mult if debris_active(state) else 1
        )
        disposal = round(exact(retired) * exact(disposal_each))
        if disposal > 0:
            entries.append(
                _entry(turn, company, f"{memo}: deorbiting", GENERAL_ADMIN, CASH, disposal)
            )
            spend += disposal
        if dep > 0:
            entries.append(
                _entry(
                    turn,
                    company,
                    f"{memo}: depreciation",
                    DEPRECIATION,
                    ACCUMULATED_DEPRECIATION,
                    dep,
                )
            )
            depreciated += dep
        new = replace(
            c,
            ground=ground,
            cohorts=tuple(keep),
            capex_cents=capex,
            depreciated_cents=depreciated,
            lost=c.lost + lost_now,
        )
        covered = covered_regions(new, balance) if new.kind == "broadband" else ()
        ground_cost = sb.constellation.ground_station_cents * len(covered)
        if new.kind == "eo" and new.in_orbit() >= sb.constellation.eo_min_satellites:
            ground_cost = sb.constellation.ground_station_cents
        fee = new.in_orbit() * sb.debris.fee_cents if debris_active(state) else 0
        for label_, cents in (("ground stations", ground_cost), ("debris fees", fee)):
            if cents > 0:
                entries.append(
                    _entry(turn, company, f"{memo}: {label_}", GENERAL_ADMIN, CASH, cents)
                )
                spend += cents
        rev = revenue.get(new.product_id, 0) if new.product_id is not None else 0
        cash = new.cash_cents + rev + received - spend
        paid = new.paid_back_turn
        if paid is None and cash >= 0 and new.cash_cents < 0:
            paid = turn
        gbps, d2d = capacity_gbps(new, balance)
        cm = ConstellationMonth(
            turn=turn,
            constellation_id=new.id,
            in_orbit=new.in_orbit(),
            built=made + bought,
            launched=sum(r.satellites for r in flown if r.constellation_id == new.id and r.ok),
            lost=lost_now,
            retired=retired,
            capacity_gbps=gbps + d2d,
            covered=covered,
            subscribers=_subscribers(state, new),
            revenue_cents=rev + received,
            spend_cents=spend,
        )
        new = replace(new, cash_cents=cash, paid_back_turn=paid, month=cm)
        months.append(cm)
        if lost_now:
            lost_ids.append(new.id)
        out.append(new)
        if covered != (c.month.covered if c.month is not None else ()):
            opened = [r for r in covered if c.month is None or r not in c.month.covered]
            for r in opened:
                logs.append(
                    inbox_item(
                        turn,
                        company,
                        "space_region_covered",
                        constellation=c.name,
                        region=data.region(r).label,
                    )
                )
    keep_months = sb.constellation.history_months
    history = tuple(m for m in state.space.months if m.turn > turn - keep_months) + tuple(months)
    space: SpaceState = replace(state.space, constellations=tuple(out), months=history)
    return replace(state, space=space), entries, logs, flown, lost_ids


def _subscribers(state: GameState, c: Constellation) -> float:
    if c.product_id is None:
        return 0.0
    total = sum(s.customers for s in state.segments_of(c.product_id))
    return total + sum(s.customers for s in state.regional_segments_of(c.product_id))


def record_flight(
    state: GameState,
    vehicle: Product,
    spec: LaunchSpec,
    failed: bool,
    rng: RngFactory,
    balance: Balance,
) -> tuple[GameState, LaunchSpec]:
    """A vehicle line's flight: its count, and after a failure its grounding (drawn on stream space
    (3, product_id, failures)) and brand."""
    fb = balance.space.failure
    turn = state.turn
    s = replace(
        spec,
        flights=spec.flights + 1,
        first_flight_turn=spec.first_flight_turn if spec.first_flight_turn is not None else turn,
    )
    if failed:
        u = float(draws.gen(rng, turn, draws.AFTER, vehicle.id, spec.failures).random())
        months = round(fb.ground_months.lo + (fb.ground_months.hi - fb.ground_months.lo) * u)
        s = replace(s, failures=spec.failures + 1, grounded_until=turn + 1 + months)
        product = state.product(vehicle.id)
        if product is not None:
            state = with_product(
                state, replace(product, brand=max(0.0, product.brand - fb.brand_points))
            )
    specs = tuple(s if x.product_id == s.product_id else x for x in state.space.launch_specs)
    return replace(state, space=replace(state.space, launch_specs=specs)), s
