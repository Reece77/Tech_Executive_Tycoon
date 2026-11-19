"""The player's space actions (ADR-0014; docs/formulas.md 56). They take effect at once and spend
the actor's energy. A launch vehicle line, a broadband line and an Earth-observation line are made
with `create_product` (categories `launch`, `satellite_broadband`, `earth_observation`); launch
sites and satellite plants with `build_facility` (kinds `launch_site`, `satellite_plant`; a launch
site only in a region with a launch range, `space.site_regions`).

- **SetLaunchSpec** (`space.energy.design`): a vehicle line's payload to LEO and the reuse level
  it aims for (`expendable`, `recovery`, `full`; flown at the best its reusability lead allows).
- **PlanConstellation** (`space.energy.constellation`): a new constellation of a kind (`broadband`
  or `eo`) serving one of the company's lines, its shells, satellite design (mass, life, D2D) and
  plan (built and launched a month, the vehicle line or bought launches, insured or not).
- **SetConstellationPlan** (`space.energy.plan`): change a constellation's shells and plan.
- **ApplyLicence** (`space.energy.licence`): apply for landing rights and spectrum in a region,
  at `licence.fee_cents`.
- **SetTerminalPrice** (`space.energy.terminal`): a broadband line's user terminal price.
- **SetD2dPartner** (`space.energy.partner`): partner a broadband line's direct-to-device service
  with mobile carriers, or not.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InsufficientCashError, SpaceRuleError
from tst.sim.ledger import CASH, GENERAL_ADMIN, LedgerBalances, LedgerEntry, account_balance
from tst.sim.log import inbox_item
from tst.sim.space.config import CONSTELLATION_KINDS, REUSE_LEVELS
from tst.sim.space.data import is_broadband, is_eo, is_launch
from tst.sim.space.models import Constellation, LaunchSpec, Licence
from tst.sim.state import GameState

NAME_MAX: Final = 60  # tunable-exempt: a name's length


@dataclass(frozen=True, slots=True)
class SetLaunchSpec:
    actor_id: int
    product_id: int
    payload_kg: float
    reuse: str
    kind: Literal["set_launch_spec"] = "set_launch_spec"


@dataclass(frozen=True, slots=True)
class PlanConstellation:
    actor_id: int
    name: str
    constellation_kind: str
    product_id: int
    shells: int
    mass_kg: float
    life_months: int
    build_per_month: int
    launches_per_month: int
    vehicle_product_id: int | None = None
    d2d: bool = False
    insured: bool = True
    kind: Literal["plan_constellation"] = "plan_constellation"


@dataclass(frozen=True, slots=True)
class SetConstellationPlan:
    actor_id: int
    constellation_id: int
    shells: int
    build_per_month: int
    launches_per_month: int
    vehicle_product_id: int | None = None
    insured: bool = True
    kind: Literal["set_constellation_plan"] = "set_constellation_plan"


@dataclass(frozen=True, slots=True)
class ApplyLicence:
    actor_id: int
    region: str
    kind: Literal["apply_licence"] = "apply_licence"


@dataclass(frozen=True, slots=True)
class SetTerminalPrice:
    actor_id: int
    product_id: int
    price_cents: int
    kind: Literal["set_terminal_price"] = "set_terminal_price"


@dataclass(frozen=True, slots=True)
class SetD2dPartner:
    actor_id: int
    product_id: int
    partner: bool
    kind: Literal["set_d2d_partner"] = "set_d2d_partner"


type SpaceAction = (
    SetLaunchSpec
    | PlanConstellation
    | SetConstellationPlan
    | ApplyLicence
    | SetTerminalPrice
    | SetD2dPartner
)
ACTION_TYPES: Final[dict[str, type]] = {
    "set_launch_spec": SetLaunchSpec,
    "plan_constellation": PlanConstellation,
    "set_constellation_plan": SetConstellationPlan,
    "apply_licence": ApplyLicence,
    "set_terminal_price": SetTerminalPrice,
    "set_d2d_partner": SetD2dPartner,
}


def _energy(state: GameState, actor: int, key: str, balance: Balance) -> GameState:
    return spend_energy(state, actor, f"space_{key}", balance, cost=balance.space.energy[key])


def _own_line(state: GameState, company: int, product_id: int | None) -> object:
    product = state.product(product_id) if product_id is not None else None
    if product is None or product.company_id != company or product.status == "retired":
        return None
    return product


def set_launch_spec(
    state: GameState, action: SetLaunchSpec, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    product = state.product(action.product_id)
    if product is None or product.company_id != company or not is_launch(product, balance):
        raise SpaceRuleError("set a design on one of your own launch vehicle lines")
    vb = balance.space.vehicle
    if not vb.payload_kg.lo <= action.payload_kg <= vb.payload_kg.hi:
        raise SpaceRuleError(f"a payload is {vb.payload_kg.lo:,.0f}-{vb.payload_kg.hi:,.0f} kg")
    if action.reuse not in REUSE_LEVELS:
        raise SpaceRuleError(f"reuse is one of {', '.join(REUSE_LEVELS)}")
    old = state.space.spec(product.id)
    spec = LaunchSpec(
        product_id=product.id,
        company_id=company,
        payload_kg=float(action.payload_kg),
        reuse=action.reuse,
        flights=old.flights if old else 0,
        failures=old.failures if old else 0,
        grounded_until=old.grounded_until if old else None,
        pending=old.pending if old else 0.0,
        first_flight_turn=old.first_flight_turn if old else None,
    )
    state = _energy(state, action.actor_id, "design", balance)
    specs = tuple(s for s in state.space.launch_specs if s.product_id != product.id)
    space = replace(
        state.space, launch_specs=tuple(sorted((*specs, spec), key=lambda s: s.product_id))
    )
    return Outcome(replace(state, space=space))


def _check_plan(
    state: GameState,
    company: int,
    shells: int,
    build: int,
    launches: int,
    vehicle_id: int | None,
    balance: Balance,
) -> None:
    sb = balance.space
    most = min(sb.constellation.max_shells, len(sb.constellation.shells))
    if not 1 <= shells <= most:
        raise SpaceRuleError(f"a constellation has 1-{most} shells")
    if build < 0 or launches < 0 or launches > sb.max_launches_month:
        raise SpaceRuleError(
            f"plan 0 or more satellites and 0-{sb.max_launches_month} launches a month"
        )
    if vehicle_id is not None:
        v = state.product(vehicle_id)
        if v is None or v.company_id != company or not is_launch(v, balance):
            raise SpaceRuleError("launch on one of your own vehicle lines, or buy launches")
        if state.space.spec(vehicle_id) is None:
            raise SpaceRuleError("the vehicle line needs a design first")


def plan_constellation(
    state: GameState, action: PlanConstellation, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    sb = balance.space
    name = action.name.strip()
    if not name or len(name) > NAME_MAX:
        raise SpaceRuleError(f"a constellation needs a name of 1-{NAME_MAX} characters")
    if action.constellation_kind not in CONSTELLATION_KINDS:
        raise SpaceRuleError(f"a constellation is one of {', '.join(CONSTELLATION_KINDS)}")
    product = state.product(action.product_id)
    want = is_broadband if action.constellation_kind == "broadband" else is_eo
    if product is None or product.company_id != company or not want(product, balance):
        raise SpaceRuleError(
            "a broadband constellation serves one of your satellite broadband lines, an imaging "
            "one one of your Earth-observation lines"
        )
    if action.d2d and action.constellation_kind != "broadband":
        raise SpaceRuleError("only broadband satellites can serve phones directly")
    s = sb.satellite
    if not s.mass_kg.lo <= action.mass_kg <= s.mass_kg.hi:
        raise SpaceRuleError(f"a satellite is {s.mass_kg.lo:,.0f}-{s.mass_kg.hi:,.0f} kg")
    if not s.life_months.lo <= action.life_months <= s.life_months.hi:
        raise SpaceRuleError(
            f"a satellite's life is {s.life_months.lo:.0f}-{s.life_months.hi:.0f} months"
        )
    _check_plan(
        state,
        company,
        action.shells,
        action.build_per_month,
        action.launches_per_month,
        action.vehicle_product_id,
        balance,
    )
    cid = max((c.id for c in state.space.constellations), default=0) + 1
    c = Constellation(
        id=cid,
        company_id=company,
        name=name,
        kind=action.constellation_kind,  # type: ignore[arg-type]
        product_id=product.id,
        shells=action.shells,
        mass_kg=float(action.mass_kg),
        life_months=int(action.life_months),
        d2d=action.d2d,
        insured=action.insured,
        build_per_month=action.build_per_month,
        launches_per_month=action.launches_per_month,
        vehicle_product_id=action.vehicle_product_id,
        created_turn=state.turn,
    )
    state = _energy(state, action.actor_id, "constellation", balance)
    space = replace(state.space, constellations=(*state.space.constellations, c))
    return Outcome(replace(state, space=space))


def set_constellation_plan(
    state: GameState, action: SetConstellationPlan, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    c = state.space.constellation(action.constellation_id)
    if c is None or c.company_id != company:
        raise SpaceRuleError("change the plan of one of your own constellations")
    _check_plan(
        state,
        company,
        action.shells,
        action.build_per_month,
        action.launches_per_month,
        action.vehicle_product_id,
        balance,
    )
    new = replace(
        c,
        shells=action.shells,
        build_per_month=action.build_per_month,
        launches_per_month=action.launches_per_month,
        vehicle_product_id=action.vehicle_product_id,
        insured=action.insured,
    )
    state = _energy(state, action.actor_id, "plan", balance)
    cons = tuple(new if x.id == c.id else x for x in state.space.constellations)
    return Outcome(replace(state, space=replace(state.space, constellations=cons)))


def apply_licence(
    state: GameState,
    action: ApplyLicence,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    lb = balance.space.licence
    if action.region not in data.region_keys:
        raise SpaceRuleError(f"unknown region {action.region!r}")
    old = state.space.licence(company, action.region)
    if old is not None and old.status in ("applied", "granted"):
        raise SpaceRuleError(f"a licence in {data.region(action.region).label} is {old.status}")
    if account_balance(balances, company, CASH) < lb.fee_cents:
        raise InsufficientCashError("not enough cash for the licence fee")
    lic = Licence(
        company_id=company,
        region=action.region,
        status="applied",
        applied_turn=state.turn,
        decision_turn=state.turn + lb.review_months.get(action.region, 0),
    )
    state = _energy(state, action.actor_id, "licence", balance)
    rest = tuple(
        x
        for x in state.space.licences
        if not (x.company_id == company and x.region == action.region)
    )
    space = replace(
        state.space,
        licences=tuple(
            sorted((*rest, lic), key=lambda x: (x.company_id, data.region_index(x.region)))
        ),
    )
    entries: tuple[LedgerEntry, ...] = ()
    if lb.fee_cents > 0:
        entries = (
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=company,
                memo=f"Spectrum and landing rights application: {data.region(action.region).label}",
                debit=GENERAL_ADMIN,
                credit=CASH,
                amount=lb.fee_cents,
            ),
        )
    log = inbox_item(
        state.turn, company, "space_licence_applied", region=data.region(action.region).label
    )
    return Outcome(replace(state, space=space), entries, (log,))


def set_terminal_price(
    state: GameState, action: SetTerminalPrice, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    product = state.product(action.product_id)
    if product is None or product.company_id != company or not is_broadband(product, balance):
        raise SpaceRuleError("set a terminal price on one of your own broadband lines")
    if action.price_cents < 0:
        raise SpaceRuleError("a terminal's price is 0 or more")
    state = _energy(state, action.actor_id, "terminal", balance)
    rest = tuple(x for x in state.space.terminal_prices if x[0] != product.id)
    prices = tuple(sorted((*rest, (product.id, int(action.price_cents)))))
    return Outcome(replace(state, space=replace(state.space, terminal_prices=prices)))


def set_d2d_partner(
    state: GameState, action: SetD2dPartner, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    product = state.product(action.product_id)
    if product is None or product.company_id != company or not is_broadband(product, balance):
        raise SpaceRuleError("partner one of your own broadband lines")
    state = _energy(state, action.actor_id, "partner", balance)
    rest = tuple(x for x in state.space.d2d_partners if x != product.id)
    partners = tuple(sorted((*rest, product.id))) if action.partner else rest
    return Outcome(replace(state, space=replace(state.space, d2d_partners=partners)))


def apply_space(
    state: GameState,
    action: SpaceAction,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    if data.space is None:
        raise SpaceRuleError("this game has no space markets")
    match action:
        case SetLaunchSpec():
            return set_launch_spec(state, action, balance, data)
        case PlanConstellation():
            return plan_constellation(state, action, balance, data)
        case SetConstellationPlan():
            return set_constellation_plan(state, action, balance, data)
        case ApplyLicence():
            return apply_licence(state, action, balances, balance, data)
        case SetTerminalPrice():
            return set_terminal_price(state, action, balance, data)
        case SetD2dPartner():
            return set_d2d_partner(state, action, balance, data)
