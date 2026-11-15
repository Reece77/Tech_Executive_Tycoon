"""The player's power actions (ADR-0014; docs/formulas.md 46.2-46.3). They take effect at once
and spend the actor's energy.

- **BuildPlant**: order a plant of a type and size in a region (a city's site), from stage 4
  (`power.plants.min_stage`). With `site_id` it sits behind the meter of that facility (a data
  centre or fab of the same company, in the same city); otherwise it is grid-tied and joins the
  region's queue. Its hidden overrun is drawn at the order (stream power (1, facility)).
- **SignPpa**: a power-purchase agreement with a generator in a region for a volume a month
  and 5-20 years, at the quoted price; at most `power.ppa.max_share` x the company's regional
  demand (at least one month's 1 MW), and not with a generator the group broke with (M23a).

Data centres and fabs ordered from `power.start` above `power.queue.min_mw` join the queue
from their own order (`after_order`, called by the facility and fab actions).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InsufficientCashError, PowerRuleError
from tst.sim.facilities.models import Facility
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import format_money
from tst.sim.power import demand, plants, ppa, queues
from tst.sim.power.models import Plant
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility, with_plant, with_ppa

SITE_KINDS: Final = ("data_centre_general", "data_centre_gpu", "fab")  # tunable-exempt: 46.2
NUCLEAR_MIN_MW: Final = 1000  # tunable-exempt: a large reactor comes only in its 1 GW size


@dataclass(frozen=True, slots=True)
class BuildPlant:
    actor_id: int
    plant_type: str
    mw: float
    region: str
    city: str | None = None
    site_id: int | None = None  # behind the meter at this facility
    kind: Literal["build_plant"] = "build_plant"


@dataclass(frozen=True, slots=True)
class SignPpa:
    actor_id: int
    region: str
    producer: str
    mwh_month: float
    years: int
    kind: Literal["sign_ppa"] = "sign_ppa"


type PowerAction = BuildPlant | SignPpa
ACTION_TYPES: Final[dict[str, type]] = {"build_plant": BuildPlant, "sign_ppa": SignPpa}


def site_of(state: GameState, company: int, action: BuildPlant) -> Facility | None:
    """The behind-the-meter host, checked (46.2)."""
    if action.site_id is None:
        return None
    f = state.facility(action.site_id)
    if f is None or f.company_id != company or f.status == "closed":
        raise PowerRuleError(f"facility {action.site_id} is not one of your sites")
    if f.kind not in SITE_KINDS:
        raise PowerRuleError("a plant can sit behind the meter of a data centre or a fab only")
    if f.region != action.region or (action.city is not None and f.city != action.city):
        raise PowerRuleError("a behind-the-meter plant is built at its site's city")
    return f


def check_build(
    state: GameState, company: int, action: BuildPlant, balance: Balance, data: GameData
) -> None:
    pb = balance.power.plants
    if data.power is None:
        raise PowerRuleError("power plants are not in this game's data")
    if not plants.plants_unlocked(state, company, balance):
        raise PowerRuleError(f"owned plants unlock at stage {pb.min_stage}")
    if action.plant_type not in {t.key for t in data.power.plant_types}:
        raise PowerRuleError(f"unknown plant type {action.plant_type!r}")
    if not plants.available(state, action.plant_type, data):
        raise PowerRuleError("no small modular reactor can be ordered yet")
    if action.mw not in pb.sizes_mw:
        sizes = ", ".join(f"{s:,.0f}" for s in pb.sizes_mw)
        raise PowerRuleError(f"a plant is {sizes} MW")
    if action.plant_type == "nuclear" and action.mw < NUCLEAR_MIN_MW:
        raise PowerRuleError(f"a large reactor is {NUCLEAR_MIN_MW:,} MW")
    if action.region not in data.region_keys:
        raise PowerRuleError(f"unknown region {action.region!r}")
    if action.city is not None and (
        not data.has_city(action.city) or data.city(action.city).region != action.region
    ):
        raise PowerRuleError(f"{action.city!r} is not a city in that region")


def build_plant(
    state: GameState, action: BuildPlant, balances: LedgerBalances, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    check_build(state, company, action, balance, data)
    site = site_of(state, company, action)
    city = action.city or (site.city if site is not None else None)
    q = plants.quote(
        state, action.plant_type, action.mw, action.region, site is not None, balance, data
    )
    if account_balance(balances, company, CASH) < q.monthly_capex_cents:
        raise InsufficientCashError(
            f"the first capex payment needs {format_money(q.monthly_capex_cents)}"
        )
    state = spend_energy(
        state, action.actor_id, "build_plant", balance, cost=balance.power.plants.energy
    )
    facility_id, ids = state.next_ids.take("facility")
    state = replace(state, next_ids=ids)
    rng = RngFactory(state.save_meta.master_seed)
    over = plants.draw_overrun(rng, state.turn, facility_id, action.plant_type, balance)
    capex = round(q.capex_cents * (1 + over))
    months = plants.true_months(action.plant_type, q.build_months, over, balance)
    facility = Facility(
        id=facility_id,
        company_id=company,
        kind=plants.PLANT_KIND,
        region=action.region,
        capacity=round(action.mw),
        on_time=round(action.mw),
        ordered_turn=state.turn,
        ready_turn=q.ready_turn,
        late_turn=q.ready_turn,
        capex_cents=capex,
        input_index=1.0,
        city=city,
    )
    state = with_facility(state, facility)
    plant = Plant(
        facility_id=facility_id,
        company_id=company,
        type=action.plant_type,
        mw=action.mw,
        estimate_cents=q.capex_cents,
        complete_turn=state.turn + months,
        monthly_capex_cents=-(-capex // months),
        site_id=site.id if site is not None else None,
        connected=site is not None,
    )
    state = with_plant(state, plant)
    grid_note = "It sits behind the meter: no grid connection needed."
    if site is None:
        state = queues.join(state, facility, plants.PLANT_KIND, action.mw, data)
        entry = queues.entry_for(state, facility_id)
        assert entry is not None
        state = with_plant(state, replace(plant, queue_id=entry.id))
        lo, hi = queues.shown_range(entry.median_months, balance)
        grid_note = (
            f"It joins the {data.region(action.region).label} grid queue: {lo:.0f}-{hi:.0f} months."
        )
    log = inbox_item(
        state.turn,
        company,
        "plant_ordered",
        plant=plants.plant_name(state, plant, data),
        capex=format_money(q.capex_cents),
        months=q.build_months,
        ready=format_turn(q.ready_turn),
        grid=grid_note,
    )
    return Outcome(state, (), (log,))


def check_ppa(
    state: GameState, company: int, action: SignPpa, balance: Balance, data: GameData
) -> None:
    from tst.sim.contracts.termination import check_willing

    pb = balance.power.ppa
    if data.power is None:
        raise PowerRuleError("power contracts are not in this game's data")
    if action.region not in data.region_keys:
        raise PowerRuleError(f"unknown region {action.region!r}")
    s = ppa.seller(data, action.region, action.producer)
    if s is None:
        raise PowerRuleError(f"{action.producer!r} does not sell power in that region")
    if not pb.years.lo <= action.years <= pb.years.hi:
        raise PowerRuleError(f"a power contract runs {pb.years.lo:.0f}-{pb.years.hi:.0f} years")
    if action.mwh_month <= 0:
        raise PowerRuleError("a power contract needs a volume")
    cap = max(
        balance.power.hours_a_month,
        pb.max_share * ppa.regional_demand(state, company, action.region),
    )
    if action.mwh_month > cap:
        raise PowerRuleError(f"at most {cap:,.0f} MWh a month: your demand there sets the size")
    check_willing(state, f"power:{action.producer}", s.name, balance)


def sign_ppa(state: GameState, action: SignPpa, balance: Balance, data: GameData) -> Outcome:
    company = acting_company(state, action.actor_id)
    check_ppa(state, company, action, balance, data)
    q = ppa.quote(
        state, action.region, action.producer, action.mwh_month, action.years, balance, data
    )
    state = spend_energy(state, action.actor_id, "sign_ppa", balance, cost=balance.power.ppa.energy)
    contract = ppa.from_quote(state, company, q)
    state = with_ppa(state, contract)
    log = inbox_item(
        state.turn,
        company,
        "ppa_signed",
        producer=q.producer_name,
        mwh=f"{q.mwh_month:,.0f}",
        region=data.region(action.region).label,
        price=format_money(round(q.price_cents)),
        start=format_turn(q.start_turn),
        end=format_turn(q.end_turn),
        take_or_pay=f"{balance.power.ppa.take_or_pay:.0%}",
    )
    return Outcome(state, (), (log,))


def apply_power(
    state: GameState,
    action: PowerAction,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    if isinstance(action, BuildPlant):
        return build_plant(state, action, balances, balance, data)
    return sign_ppa(state, action, balance, data)


def after_order(
    state: GameState, facility: Facility, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """A data centre or fab just ordered joins the queue when it must (46.3)."""
    if not queues.load_joins(state, facility, balance, data):
        return state, []
    mw = demand.facility_mw(state, facility, balance, data)
    state = queues.join(state, facility, facility.kind, mw, data)
    entry = queues.entry_for(state, facility.id)
    assert entry is not None
    lo, hi = queues.shown_range(entry.median_months, balance)
    from tst.sim.facilities.lifecycle import facility_name

    log = inbox_item(
        state.turn,
        facility.company_id,
        "grid_queued",
        facility=facility_name(facility, balance, data),
        mw=f"{mw:,.0f}",
        region=data.region(facility.region).label,
        wait=f"{lo:.0f}-{hi:.0f} months",
    )
    return state, [log]
