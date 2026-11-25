"""The player's telecom actions (ADR-0014; docs/formulas.md 62.1-62.4). They take effect at once
and spend the actor's energy (`telecom.energy`). A line itself (mobile, fixed broadband, wholesale
or network equipment) is made with `create_product` and launched as any product; it sells only
where its company's networks and spectrum reach (tst.sim.telecom.services).

- **BuildTowers** (`build`): new macro sites in a region with radios of a generation from a vendor
  (or the group's own network-equipment line): capex = sites x (the site's civil works + the
  radios' price, tst.sim.telecom.equipment). Refused for a generation not yet commercial anywhere
  (6G before its seeded month) or a vendor a ban refuses there.
- **AddRadios** (`build`): a generation's radios on sites the company already has (at most its
  sites not yet carrying it): capex = sites x the radios' price.
- **BuildFibre** (`build`): thousands of homes passed in a region at the year's cost a home.
- **BuildCable** (`build`): a subsea cable of a capacity between two or three regions, `km` long:
  capex = km x the year's cost a km x (Tbps / `cable.ref_tbps`) ** `cable.tbps_exponent`.
- **BidSpectrum** (`bid`): register (or change, or with 0 blocks withdraw) a bid in an announced
  auction: blocks wanted and a limit a block. Refused in an area that assigns spectrum
  administratively.
- **ReplaceRadios** (`replace`): rip-and-replace: another vendor's radios on a record's sites, at
  the radios' price x `ban.swap_mult` (removing the old kit and re-integrating a live site); when
  they go live they count as replaced against its bans.
- **SetTelecomLine** (`setting`): a line's zero-rating and satellite partner.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InsufficientCashError, TelecomRuleError
from tst.sim.facilities import goods, lifecycle
from tst.sim.facilities.models import Facility
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import exact
from tst.sim.state import GameState, with_facility
from tst.sim.telecom import equipment as eq
from tst.sim.telecom.config import OWN_SUPPLIER
from tst.sim.telecom.data import THOUSAND, end_year_at, file, is_service
from tst.sim.telecom.models import FibreNetwork, LineSetting, RadioNetwork, SubseaCable

MAX_CABLE_REGIONS: Final = 3  # tunable-exempt: a cable lands in two or three regions


@dataclass(frozen=True, slots=True)
class BuildTowers:
    actor_id: int
    region: str
    sites: int
    generation: str
    vendor: str
    city: str | None = None
    kind: Literal["build_towers"] = "build_towers"


@dataclass(frozen=True, slots=True)
class AddRadios:
    actor_id: int
    region: str
    sites: int
    generation: str
    vendor: str
    kind: Literal["add_radios"] = "add_radios"


@dataclass(frozen=True, slots=True)
class BuildFibre:
    actor_id: int
    region: str
    homes: int  # thousands of homes passed
    city: str | None = None
    kind: Literal["build_fibre"] = "build_fibre"


@dataclass(frozen=True, slots=True)
class BuildCable:
    actor_id: int
    name: str
    regions: tuple[str, ...]
    km: float
    tbps: int
    kind: Literal["build_cable"] = "build_cable"


@dataclass(frozen=True, slots=True)
class BidSpectrum:
    actor_id: int
    auction_id: int
    blocks: int
    limit_cents: int  # a block
    kind: Literal["bid_spectrum"] = "bid_spectrum"


@dataclass(frozen=True, slots=True)
class ReplaceRadios:
    actor_id: int
    facility_id: int
    vendor: str
    sites: int
    kind: Literal["replace_radios"] = "replace_radios"


@dataclass(frozen=True, slots=True)
class SetTelecomLine:
    actor_id: int
    product_id: int
    zero_rating: bool = False
    satellite_partner: bool = False
    kind: Literal["set_telecom_line"] = "set_telecom_line"


type TelecomAction = (
    BuildTowers | AddRadios | BuildFibre | BuildCable | BidSpectrum | ReplaceRadios | SetTelecomLine
)
ACTION_TYPES: Final[dict[str, type]] = {
    "build_towers": BuildTowers,
    "add_radios": AddRadios,
    "build_fibre": BuildFibre,
    "build_cable": BuildCable,
    "bid_spectrum": BidSpectrum,
    "replace_radios": ReplaceRadios,
    "set_telecom_line": SetTelecomLine,
}


# --- Checks and orders ---------------------------------------------------------------------------


def generation_open(state: GameState, generation: str, data: GameData) -> bool:
    f = file(data)
    g = next((x for x in f.generations if x.key == generation), None)
    if g is None:
        return False
    first = g.first_turn if g.first_turn is not None else state.telecom.world.g6_turn
    return first is not None and state.turn >= first


def _check_vendor(
    state: GameState, company: int, region: str, vendor: str, balance: Balance, data: GameData
) -> None:
    if vendor == OWN_SUPPLIER:
        if eq.own_line(state, company, balance) is None:
            raise TelecomRuleError("own radios need one of your live network-equipment lines")
        return
    if file(data).vendor(vendor) is None:
        raise TelecomRuleError(f"unknown vendor {vendor!r}")
    ban = eq.refusing_ban(state, region, vendor, balance, data)
    if ban is not None:
        raise TelecomRuleError(f"{ban}: no new radios from this vendor in that region")


def _order(
    state: GameState,
    company: int,
    kind: str,
    region: str,
    capacity: int,
    capex: float,
    city: str | None,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> tuple[GameState, Facility, int, int]:
    if region not in data.region_keys:
        raise TelecomRuleError(f"unknown region {region!r}")
    k = balance.facility.kinds[kind]
    sizes = k.sizes or balance.facility.sizes
    if capacity not in sizes:
        raise TelecomRuleError(
            f"{k.label.lower()} come in {', '.join(f'{s:,}' for s in sizes)} {k.unit}"
        )
    if city is not None and (not data.has_city(city) or data.city(city).region != region):
        raise TelecomRuleError(f"{city!r} is not a city in that region")
    q = lifecycle.quote(state, company, kind, region, capacity, balance, data, None)
    total = max(1, round(exact(capex)))
    monthly = max(1, round(exact(total) / exact(k.build_months)))
    if account_balance(balances, company, CASH) < monthly:
        raise InsufficientCashError(f"the first capex payment needs {monthly} cents")
    state, facility = lifecycle.order_build(
        state, company, replace(q, capex_cents=total, monthly_capex_cents=monthly)
    )
    if city is not None:
        facility = replace(facility, city=city)
        state = with_facility(state, facility)
    return state, facility, total, k.build_months


def _log(
    state: GameState,
    company: int,
    facility: Facility,
    units: str,
    what: str,
    capex: int,
    months: int,
    balance: Balance,
    data: GameData,
) -> LogItem:
    return inbox_item(
        state.turn,
        company,
        "telecom_ordered",
        facility=lifecycle.facility_name(facility, balance, data),
        units=units,
        region=data.region(facility.region).label,
        what=what,
        capex_cents=capex,
        months=months,
        ready=format_turn(facility.ready_turn),
    )


def build_towers(
    state: GameState,
    action: BuildTowers,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    if not generation_open(state, action.generation, data):
        raise TelecomRuleError("that generation is not commercial yet")
    _check_vendor(state, company, action.region, action.vendor, balance, data)
    state = spend_energy(
        state, action.actor_id, "build_towers", balance, cost=balance.telecom.energy["build"]
    )
    radio = eq.radio_cents(state, company, action.generation, action.vendor, balance, data)
    capex = action.sites * (eq.civil_cents(state, data) + radio)
    state, f, total, months = _order(
        state,
        company,
        balance.telecom.tower_kind,
        action.region,
        action.sites,
        capex,
        action.city,
        balance,
        data,
        balances,
    )
    rec = RadioNetwork(f.id, company, action.region, action.generation, action.vendor)
    state = replace(state, telecom=replace(state.telecom, radios=(*state.telecom.radios, rec)))
    g = file(data).generation(action.generation).label
    return Outcome(
        state,
        (),
        (
            _log(
                state,
                company,
                f,
                f"{action.sites:,} sites",
                f"{g} radios",
                total,
                months,
                balance,
                data,
            ),
        ),
    )


def _sites_and_radios(
    state: GameState, company: int, region: str, generation: str
) -> tuple[int, int]:
    """(sites the company has or is building, of them with the generation's radios ordered)."""
    sites = radios = 0
    for r in state.telecom.radios:
        if r.company_id != company or r.region != region:
            continue
        f = state.facility(r.facility_id)
        n = f.capacity if f is not None and f.status != "closed" else 0
        if not r.overlay:
            sites += n
        if r.generation == generation and r.replaces_facility_id is None:
            radios += n
    return sites, radios


def add_radios(
    state: GameState, action: AddRadios, balance: Balance, data: GameData, balances: LedgerBalances
) -> Outcome:
    company = acting_company(state, action.actor_id)
    if not generation_open(state, action.generation, data):
        raise TelecomRuleError("that generation is not commercial yet")
    _check_vendor(state, company, action.region, action.vendor, balance, data)
    sites, radios = _sites_and_radios(state, company, action.region, action.generation)
    if radios + action.sites > sites:
        raise TelecomRuleError(
            f"you have {max(0, sites - radios):,} sites without that generation's radios there"
        )
    state = spend_energy(
        state, action.actor_id, "add_radios", balance, cost=balance.telecom.energy["build"]
    )
    capex = action.sites * eq.radio_cents(
        state, company, action.generation, action.vendor, balance, data
    )
    state, f, total, months = _order(
        state,
        company,
        balance.telecom.radio_kind,
        action.region,
        action.sites,
        capex,
        None,
        balance,
        data,
        balances,
    )
    rec = RadioNetwork(f.id, company, action.region, action.generation, action.vendor, overlay=True)
    state = replace(state, telecom=replace(state.telecom, radios=(*state.telecom.radios, rec)))
    g = file(data).generation(action.generation).label
    return Outcome(
        state,
        (),
        (
            _log(
                state,
                company,
                f,
                f"{action.sites:,} sites",
                f"{g} radios",
                total,
                months,
                balance,
                data,
            ),
        ),
    )


def build_fibre(
    state: GameState, action: BuildFibre, balance: Balance, data: GameData, balances: LedgerBalances
) -> Outcome:
    company = acting_company(state, action.actor_id)
    state = spend_energy(
        state, action.actor_id, "build_fibre", balance, cost=balance.telecom.energy["build"]
    )
    index = goods.current(state, "equipment", data).index
    home = file(data).fibre_home_at(end_year_at(state.turn))
    capex = action.homes * THOUSAND * home * index
    state, f, total, months = _order(
        state,
        company,
        balance.telecom.fibre_kind,
        action.region,
        action.homes,
        capex,
        action.city,
        balance,
        data,
        balances,
    )
    rec = FibreNetwork(f.id, company, action.region)
    state = replace(state, telecom=replace(state.telecom, fibres=(*state.telecom.fibres, rec)))
    return Outcome(
        state,
        (),
        (
            _log(
                state,
                company,
                f,
                f"{action.homes:,} thousand homes passed",
                "fibre",
                total,
                months,
                balance,
                data,
            ),
        ),
    )


def build_cable(
    state: GameState, action: BuildCable, balance: Balance, data: GameData, balances: LedgerBalances
) -> Outcome:
    company = acting_company(state, action.actor_id)
    regions = tuple(dict.fromkeys(action.regions))
    if not 2 <= len(regions) <= MAX_CABLE_REGIONS:  # tunable-exempt: two or three landings
        raise TelecomRuleError("a cable lands in two or three regions")
    if bad := [r for r in regions if r not in data.region_keys]:
        raise TelecomRuleError(f"unknown regions {bad}")
    cb = balance.telecom.cable
    if not cb.km.lo <= action.km <= cb.km.hi:
        raise TelecomRuleError(f"a cable is {cb.km.lo:,.0f}-{cb.km.hi:,.0f} km")
    if not action.name.strip():
        raise TelecomRuleError("name the cable")
    state = spend_energy(
        state, action.actor_id, "build_cable", balance, cost=balance.telecom.energy["build"]
    )
    index = goods.current(state, "equipment", data).index
    per_km = file(data).cable_km_at(end_year_at(state.turn))
    capex = action.km * per_km * index * (action.tbps / cb.ref_tbps) ** cb.tbps_exponent
    state, f, total, months = _order(
        state,
        company,
        balance.telecom.cable_kind,
        regions[0],
        action.tbps,
        capex,
        None,
        balance,
        data,
        balances,
    )
    rec = SubseaCable(f.id, company, action.name.strip(), regions, float(action.km))
    state = replace(state, telecom=replace(state.telecom, cables=(*state.telecom.cables, rec)))
    return Outcome(
        state,
        (),
        (
            _log(
                state,
                company,
                f,
                f"{action.tbps:,} Tbps",
                f"{action.km:,.0f} km to {', '.join(data.region(r).label for r in regions[1:])}",
                total,
                months,
                balance,
                data,
            ),
        ),
    )


def bid_spectrum(
    state: GameState,
    action: BidSpectrum,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    a = state.telecom.auction(action.auction_id)
    if a is None or a.status != "announced" or state.turn >= a.turn:
        raise TelecomRuleError("bid in an announced auction before its month")
    area = file(data).region(a.region).area(a.area)
    if area is None or area.method != "auction":
        raise TelecomRuleError("that area assigns spectrum administratively")
    if a.bid_company_id is not None and a.bid_company_id != company:
        raise TelecomRuleError("another of your companies has registered in this auction")
    if action.blocks < 0 or action.blocks > a.blocks:
        raise TelecomRuleError(f"bid for 0-{a.blocks} blocks")
    if action.blocks > 0 and action.limit_cents < a.reserve_cents:
        raise TelecomRuleError("the limit must be at least the reserve")
    state = spend_energy(
        state, action.actor_id, "bid_spectrum", balance, cost=balance.telecom.energy["bid"]
    )
    if action.blocks == 0:
        b = replace(a, bid_company_id=None, bid_blocks=0, bid_limit_cents=0)
    else:
        b = replace(
            a, bid_company_id=company, bid_blocks=action.blocks, bid_limit_cents=action.limit_cents
        )
    auctions = tuple(b if x.id == a.id else x for x in state.telecom.auctions)
    return Outcome(replace(state, telecom=replace(state.telecom, auctions=auctions)))


def replace_radios(
    state: GameState,
    action: ReplaceRadios,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    old = state.telecom.radio(action.facility_id)
    if old is None or old.company_id != company:
        raise TelecomRuleError("choose one of your radio networks")
    if action.vendor == old.vendor:
        raise TelecomRuleError("replace with another vendor's radios")
    _check_vendor(state, company, old.region, action.vendor, balance, data)
    f = state.facility(old.facility_id)
    pending = sum(
        ((x := state.facility(r.facility_id)) is not None and x.capacity) or 0
        for r in state.telecom.radios
        if r.replaces_facility_id == old.facility_id
    )
    left = (f.capacity if f is not None else 0) - old.replaced - pending
    if action.sites > left:
        raise TelecomRuleError(f"{max(0, left):,} of its sites are left to replace")
    state = spend_energy(
        state, action.actor_id, "replace_radios", balance, cost=balance.telecom.energy["replace"]
    )
    radio = eq.radio_cents(state, company, old.generation, action.vendor, balance, data)
    capex = action.sites * radio * balance.telecom.ban.swap_mult  # removal and integration
    state, nf, total, months = _order(
        state,
        company,
        balance.telecom.radio_kind,
        old.region,
        action.sites,
        capex,
        None,
        balance,
        data,
        balances,
    )
    rec = RadioNetwork(
        nf.id,
        company,
        old.region,
        old.generation,
        action.vendor,
        overlay=True,
        replaces_facility_id=old.facility_id,
    )
    state = replace(state, telecom=replace(state.telecom, radios=(*state.telecom.radios, rec)))
    return Outcome(
        state,
        (),
        (
            _log(
                state,
                company,
                nf,
                f"{action.sites:,} sites",
                "replacement radios",
                total,
                months,
                balance,
                data,
            ),
        ),
    )


def set_line(state: GameState, action: SetTelecomLine, balance: Balance, data: GameData) -> Outcome:
    company = acting_company(state, action.actor_id)
    p = state.product(action.product_id)
    if p is None or p.company_id != company or not is_service(p, balance):
        raise TelecomRuleError("choose one of your mobile, broadband or wholesale lines")
    if action.zero_rating and p.category != balance.telecom.mobile:
        raise TelecomRuleError("only a mobile line can zero-rate")
    if action.satellite_partner and p.category != balance.telecom.mobile:
        raise TelecomRuleError("only a mobile line takes a satellite partner")
    state = spend_energy(
        state, action.actor_id, "set_telecom_line", balance, cost=balance.telecom.energy["setting"]
    )
    rest = tuple(s for s in state.telecom.settings if s.product_id != p.id)
    new = LineSetting(p.id, action.zero_rating, action.satellite_partner)
    settings = tuple(sorted((*rest, new), key=lambda s: s.product_id))
    return Outcome(replace(state, telecom=replace(state.telecom, settings=settings)))


def apply_telecom(
    state: GameState,
    action: TelecomAction,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    if data.telecom is None:
        raise TelecomRuleError("this game has no telecom markets")
    match action:
        case BuildTowers():
            return build_towers(state, action, balance, data, balances)
        case AddRadios():
            return add_radios(state, action, balance, data, balances)
        case BuildFibre():
            return build_fibre(state, action, balance, data, balances)
        case BuildCable():
            return build_cable(state, action, balance, data, balances)
        case BidSpectrum():
            return bid_spectrum(state, action, balance, data, balances)
        case ReplaceRadios():
            return replace_radios(state, action, balance, data, balances)
        case SetTelecomLine():
            return set_line(state, action, balance, data)
