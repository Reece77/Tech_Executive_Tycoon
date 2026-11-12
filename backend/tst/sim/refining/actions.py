"""Refining's immediate actions (ADR-0014, docs/formulas.md 36.1): order a refinery and sign a
refinery contract. Staffing and selling a plant use M12a's facility actions (`staff_facility`,
`sell_facility`): a refinery is a facility.

**Building.** A refinery of a recipe's kind, in a region, at one of the kind's sizes; a
by-product line (`byproduct_recovery`) needs a host: one of the company's other refineries in
the same region. Capex is quoted at the equipment index (22.4); the plant's true capex is the
quote x (1 + a hidden overrun) drawn once on stream `refining` (key: the facility id), M19's
rule, and is revealed only as it is paid. The first monthly payment must be in cash.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.contracts import termination as ct
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InsufficientCashError, RefiningRuleError
from tst.sim.facilities import lifecycle
from tst.sim.facilities.lifecycle import BuildQuote
from tst.sim.group.assets import check_country, place
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import inbox_item
from tst.sim.refining import goods as rg
from tst.sim.refining.draws import OVERRUN, refining_draws
from tst.sim.refining.models import Refinery, RefiningDeal
from tst.sim.refining.plants import group_of, refinery_of
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility, with_refinery, with_refining_deal

BYPRODUCT_KIND: Final = "byproduct_recovery"  # the kind that is an add-on to a host plant


@dataclass(frozen=True, slots=True)
class BuildRefinery:
    actor_id: int
    recipe: str  # refining.recipes key
    region: str
    capacity: int
    host_id: int | None = None  # a by-product line's host plant (default: the first in region)
    city: str | None = None
    company_id: int | None = None  # a group company the founder builds for (default: own)
    country: str | None = None  # M23a: the country it sits in (default: its city's, the region's)
    kind: Literal["build_refinery"] = "build_refinery"


@dataclass(frozen=True, slots=True)
class SignRefiningDeal:
    actor_id: int
    side: Literal["buy", "sell"]
    good: str
    months: int
    volume: float  # volume units a month
    company_id: int | None = None
    kind: Literal["sign_refining_deal"] = "sign_refining_deal"


type RefiningAction = BuildRefinery | SignRefiningDeal

ACTION_TYPES: Final[dict[str, type]] = {
    "build_refinery": BuildRefinery,
    "sign_refining_deal": SignRefiningDeal,
}


def _company(state: GameState, actor_id: int, company_id: int | None) -> int:
    own = acting_company(state, actor_id)
    if company_id is None or company_id == own:
        return own
    founder = state.founder_of(state.player.id)
    if founder is None or founder.id != actor_id or company_id not in group_of(state, own):
        raise RefiningRuleError("only the founder builds for another company of the group")
    return company_id


def host_for(
    state: GameState, company: int, region: str, host_id: int | None, balance: Balance
) -> int:
    """A by-product line's host: the named plant, or the company's first other refinery in
    the region (36.1: 'a gallium or germanium line on an existing plant')."""
    for ref in state.refineries:
        f = state.facility(ref.facility_id)
        if f is None or f.status == "closed" or f.company_id != company or f.region != region:
            continue
        if f.kind == BYPRODUCT_KIND:
            continue
        if host_id is None or host_id == f.id:
            return f.id
    raise RefiningRuleError("a by-product line needs one of your plants in the same region")


@dataclass(frozen=True, slots=True)
class RefineryQuote:
    recipe: str
    quote: BuildQuote  # the estimate: what the player sees


def quote(
    state: GameState,
    company: int,
    recipe: str,
    region: str,
    capacity: int,
    balance: Balance,
    data: GameData,
) -> RefineryQuote:
    rb = balance.refining
    if recipe not in rb.recipes:
        raise RefiningRuleError(f"unknown recipe {recipe!r}")
    if region not in data.region_keys:
        raise RefiningRuleError(f"unknown region {region!r}")
    kind_key = rb.recipes[recipe].kind
    kind = balance.facility.kinds[kind_key]
    allowed = kind.sizes or balance.facility.sizes
    if capacity not in allowed:
        sizes = ", ".join(f"{s:,}" for s in allowed)
        raise RefiningRuleError(f"a {kind.label.lower()} has {sizes} {kind.unit}")
    q = lifecycle.quote(state, company, kind_key, region, capacity, balance, data)
    return RefineryQuote(recipe, q)


def overrun_share(state: GameState, facility_id: int, balance: Balance) -> float:
    """The hidden overrun (engine only): uniform in `refining.overrun`."""
    o = balance.refining.overrun
    rng = RngFactory(state.save_meta.master_seed)
    u = float(refining_draws(rng, state.turn, OVERRUN, facility_id).random())
    return o.lo + (o.hi - o.lo) * u


def build_refinery(
    state: GameState,
    action: BuildRefinery,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = _company(state, action.actor_id, action.company_id)
    rq = quote(state, company, action.recipe, action.region, action.capacity, balance, data)
    q = rq.quote
    kind_key = q.kind
    host = None
    if kind_key == BYPRODUCT_KIND:
        host = host_for(state, company, action.region, action.host_id, balance)
    elif action.host_id is not None:
        raise RefiningRuleError("only a by-product line has a host plant")
    if action.city is not None and (
        not data.has_city(action.city) or data.city(action.city).region != action.region
    ):
        raise RefiningRuleError(f"{action.city!r} is not a city in that region")
    check_country(data, action.region, action.country)
    if account_balance(balances, company, CASH) < q.monthly_capex_cents:
        raise InsufficientCashError(f"the first capex payment needs {q.monthly_capex_cents} cents")
    state = spend_energy(
        state, action.actor_id, "build_refinery", balance, cost=balance.refining.build_energy
    )
    facility_id = state.next_ids.facility
    true_capex = round(q.capex_cents * (1 + overrun_share(state, facility_id, balance)))
    state, facility = lifecycle.order_build(state, company, replace(q, capex_cents=true_capex))
    if action.city is not None:
        facility = replace(facility, city=action.city)
        state = with_facility(state, facility)
    state = place(state, "facility", facility.id, action.country)
    state = with_refinery(
        state,
        Refinery(
            facility_id=facility.id,
            company_id=company,
            recipe=action.recipe,
            estimate_cents=q.capex_cents,
            host_id=host,
        ),
    )
    kind = balance.facility.kinds[kind_key]
    log = inbox_item(
        state.turn,
        company,
        "refinery_ordered",
        link_kind="refinery",
        link_id=facility.id,
        plant=lifecycle.facility_name(facility, balance, data),
        units=f"{q.capacity:,} {kind.unit}",
        region=data.region(action.region).label,
        capex_cents=q.capex_cents,
        months=q.build_months,
        ready=format_turn(facility.ready_turn),
        staff=q.staff_needed,
    )
    return Outcome(state, (), (log,))


def sign_deal(
    state: GameState, action: SignRefiningDeal, balance: Balance, data: GameData
) -> Outcome:
    """A buy or sell contract at this month's price (36.1)."""
    company = _company(state, action.actor_id, action.company_id)
    rb = balance.refining
    known = {r.input_good for r in rb.recipes.values() if r.input_good} | {
        r.output_good for r in rb.recipes.values()
    }
    if action.side not in ("buy", "sell"):
        raise RefiningRuleError("a contract buys or sells")
    if action.good not in known:
        raise RefiningRuleError(f"{action.good!r} is not a refinery input or output")
    if not rb.deal.months.lo <= action.months <= rb.deal.months.hi:
        raise RefiningRuleError(
            f"a contract runs {rb.deal.months.lo:g} to {rb.deal.months.hi:g} months"
        )
    if action.volume <= 0:
        raise RefiningRuleError("a contract needs a volume")
    who = f"refining:{action.good}"  # M23a: the market remembers a broken contract
    ct.check_willing(state, who, "The market", balance)
    state = spend_energy(state, action.actor_id, "sign_refining_deal", balance, cost=rb.deal.energy)
    price = ct.offered(
        state,
        who,
        rg.price_cents(state, action.good, balance, data),
        balance,
        buying=action.side == "buy",
    )
    deal = RefiningDeal(
        id=max((d.id for d in state.refining_deals), default=0) + 1,
        company_id=company,
        side=action.side,
        good=action.good,
        signed_turn=state.turn,
        end_turn=state.turn + action.months - 1,
        monthly_volume=action.volume,
        price_cents=price,
    )
    log = inbox_item(
        state.turn,
        company,
        "refining_deal_signed",
        link_kind="refinery",
        side=action.side,
        good=rg.label(action.good, balance, data),
        volume=f"{action.volume:,.1f} {rg.volume_unit(action.good, balance, data)}",
        months=action.months,
        price_cents=round(price),
    )
    return Outcome(with_refining_deal(state, deal), (), (log,))


def apply_refining(
    state: GameState,
    action: RefiningAction,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    match action:
        case BuildRefinery():
            return build_refinery(state, action, balance, data, balances)
        case SignRefiningDeal():
            return sign_deal(state, action, balance, data)


__all__ = ["refinery_of"]
