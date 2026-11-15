"""M33's immediate actions (ADR-0014, docs/formulas.md 47.2, 47.4).

- **OrderTools**: tools of a queued generation into the company's stock (any month, from its
  first shipment), at today's price; `prepay` pays `prepay_share` of the price now.
- **PrepayOrder**: prepay an open order of the player's (once): a one-off charge, to the fab's
  capex for a fab's order, else to 1530 with the stock's value.
- **StartLitho / SetLithoFunding / StopLitho**: the lithography programme's stages (47.4).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.equipment import controls as ec
from tst.sim.equipment import data as ed
from tst.sim.equipment import programme as ep
from tst.sim.equipment import queue as eq
from tst.sim.equipment import stock
from tst.sim.equipment.models import Programme, ToolOrder
from tst.sim.errors import EquipmentRuleError, InsufficientCashError
from tst.sim.fabs import market as fm
from tst.sim.geopolitics import world
from tst.sim.group.assets import inbox_company
from tst.sim.ledger import CASH, LedgerBalances, LedgerEntry, account_balance
from tst.sim.log import inbox_item
from tst.sim.money import times
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility

DEFAULT_COUNTRY: Final = "us"  # tunable-exempt: a company without a site (countries.yaml key)


@dataclass(frozen=True, slots=True)
class OrderTools:
    actor_id: int
    generation: str
    tools: int
    prepay: bool = False
    kind: Literal["order_tools"] = "order_tools"


@dataclass(frozen=True, slots=True)
class PrepayOrder:
    actor_id: int
    order_id: int
    kind: Literal["prepay_order"] = "prepay_order"


@dataclass(frozen=True, slots=True)
class StartLitho:
    actor_id: int
    stage: str
    funding: float
    kind: Literal["start_litho"] = "start_litho"


@dataclass(frozen=True, slots=True)
class SetLithoFunding:
    actor_id: int
    stage: str
    funding: float
    kind: Literal["set_litho_funding"] = "set_litho_funding"


@dataclass(frozen=True, slots=True)
class StopLitho:
    actor_id: int
    stage: str
    kind: Literal["stop_litho"] = "stop_litho"


type EquipmentAction = OrderTools | PrepayOrder | StartLitho | SetLithoFunding | StopLitho

ACTION_TYPES: Final[dict[str, type]] = {
    "order_tools": OrderTools,
    "prepay_order": PrepayOrder,
    "start_litho": StartLitho,
    "set_litho_funding": SetLithoFunding,
    "stop_litho": StopLitho,
}


def company_country(state: GameState, company_id: int, balance: Balance, data: GameData) -> str:
    if not world.enabled(data):
        return DEFAULT_COUNTRY
    return world.company_country(state, state.company(company_id), balance, data)


def _queued(data: GameData, generation: str) -> None:
    try:
        g = ed.equipment_file(data).generation(generation)
    except KeyError as e:
        raise EquipmentRuleError(f"unknown tool generation {generation!r}") from e
    if not g.queued:
        raise EquipmentRuleError(f"{g.label} tools are not ordered through the queue")


def order_tools(
    state: GameState, action: OrderTools, balance: Balance, data: GameData, balances: LedgerBalances
) -> Outcome:
    _queued(data, action.generation)
    company = acting_company(state, action.actor_id)
    g = ed.equipment_file(data).generation(action.generation)
    qb = balance.equipment.queue
    if not 0 < action.tools <= qb.max_order:
        raise EquipmentRuleError(f"an order is 1 to {qb.max_order} tools")
    if state.turn < g.first_shipment_turn:
        raise EquipmentRuleError(f"{g.label} tools are not shipping yet")
    country = company_country(state, company, balance, data)
    price = ed.price_cents(state, g, balance)
    order = ToolOrder(
        id=eq.next_order_id(state),
        buyer=eq.PLAYER,
        generation=g.key,
        tools=action.tools,
        placed_turn=state.turn,
        company_id=company,
        country=country,
        price_cents=price,
        prepaid=action.prepay,
    )
    why = ec.order_blocked(state, data, order)
    if why is not None:
        raise EquipmentRuleError(f"{why}: {g.label} tools cannot ship to you")
    prepay = round(qb.prepay_share * price * action.tools) if action.prepay else 0
    if prepay and account_balance(balances, company, CASH) < prepay:
        raise InsufficientCashError(f"the prepayment needs {prepay} cents")
    lead = eq.lead(state, order, balance, data)
    state = spend_energy(state, action.actor_id, "order_tools", balance, cost=qb.energy)
    order = replace(order, prepaid_cents=prepay)
    state = replace(state, tool_orders=(*state.tool_orders, order))
    entries: tuple[LedgerEntry, ...] = ()
    if prepay:
        entries = (
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=company,
                memo=f"Tool prepayment: {g.label}",
                debit=stock.TOOLS_ACCOUNT,
                credit=CASH,
                amount=prepay,
            ),
        )
    log = inbox_item(
        state.turn,
        inbox_company(state, company),
        "tools_ordered",
        link_kind="equipment",
        link_id=order.id,
        tools=action.tools,
        generation=g.label,
        supplier=_maker(data, g.key),
        price_cents=price,
        prepaid=" (prepaid)" if action.prepay else "",
        lead=lead_text(lead),
    )
    return Outcome(state, entries, (log,))


def _label(data: GameData, generation: str) -> str:
    return ed.equipment_file(data).generation(generation).label


def _maker(data: GameData, generation: str) -> str:
    ef = ed.equipment_file(data)
    return ef.supplier(ef.generation(generation).maker).name


def lead_text(lead: eq.Lead) -> str:
    if lead.low is None or lead.high is None:
        return "an unknown time (longer than the queue can see)"
    if lead.low == lead.high:
        return f"about {lead.low} months"
    return f"{lead.low}-{lead.high} months"


def prepay_order(
    state: GameState,
    action: PrepayOrder,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    order = next((o for o in state.tool_orders if o.id == action.order_id), None)
    if order is None or order.buyer != eq.PLAYER or order.company_id is None:
        raise EquipmentRuleError("that is not one of your tool orders")
    from tst.sim.equipment.fablink import ToolPlan, prepay_cents

    group = {c.id for c in world.group(state)} if world.enabled(data) else {company}
    if order.company_id not in group and order.company_id != company:
        raise EquipmentRuleError("that is not one of your tool orders")
    if order.status != "open":
        raise EquipmentRuleError("only an open order can be prepaid")
    if order.prepaid:
        raise EquipmentRuleError("the order is already prepaid")
    plan = ToolPlan(
        order.generation,
        order.remaining,
        0,
        0,
        order.remaining,
        order.price_cents,
        order.price_cents,
        None,
        None,
        None,
        None,
    )
    cents = prepay_cents(plan, balance)
    payer = order.company_id
    if account_balance(balances, payer, CASH) < cents:
        raise InsufficientCashError(f"the prepayment needs {cents} cents")
    state = spend_energy(
        state, action.actor_id, "prepay_order", balance, cost=balance.equipment.queue.energy
    )
    held = 0 if order.facility_id is not None else cents
    state = replace(
        state,
        tool_orders=tuple(
            replace(o, prepaid=True, prepaid_cents=held) if o.id == order.id else o
            for o in state.tool_orders
        ),
    )
    if order.facility_id is not None and state.facility(order.facility_id) is not None:
        facility = state.facility(order.facility_id)
        assert facility is not None
        state = with_facility(state, replace(facility, capex_cents=facility.capex_cents + cents))
        fab = fm.fab_of(state, order.facility_id)
        if fab is not None:
            from tst.sim.state import with_fab

            state = with_fab(state, replace(fab, estimate_cents=fab.estimate_cents + cents))
        entries: tuple[LedgerEntry, ...] = ()
    else:
        entries = (
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=payer,
                memo=f"Tool prepayment: {_label(data, order.generation)}",
                debit=stock.TOOLS_ACCOUNT,
                credit=CASH,
                amount=cents,
            ),
        )
    log = inbox_item(
        state.turn,
        inbox_company(state, payer),
        "tools_prepaid",
        link_kind="equipment",
        link_id=order.id,
        cents=cents,
        tools=order.remaining,
        generation=ed.equipment_file(data).generation(order.generation).label,
        supplier=_maker(data, order.generation),
    )
    return Outcome(state, entries, (log,))


def _funding(balance: Balance, funding: float) -> float:
    f = balance.equipment.programme.funding
    if not f.lo <= funding <= f.hi:
        raise EquipmentRuleError(f"funding is {f.lo:g} to {f.hi:g} times the reference budget")
    return funding


def start_litho(
    state: GameState, action: StartLitho, rng: RngFactory, balance: Balance, data: GameData
) -> Outcome:
    if not ed.enabled(data):
        raise EquipmentRuleError("there is no equipment data")
    company = acting_company(state, action.actor_id)
    funding = _funding(balance, action.funding)
    why = ep.why_not(state, company, action.stage, balance, data)
    if why is not None:
        raise EquipmentRuleError(why)
    state = spend_energy(
        state,
        action.actor_id,
        "start_litho",
        balance,
        cost=balance.equipment.programme.start_energy,
    )
    prog = ep.start(state, company, action.stage, funding, rng, balance, data)
    state = replace(state, programmes=(*state.programmes, prog))
    p = ed.equipment_file(data).stage(action.stage)
    ref = ep.reference_cents(p, balance)
    log = inbox_item(
        state.turn,
        inbox_company(state, company),
        "litho_started",
        link_kind="equipment",
        stage=p.label,
        funding=f"{funding:.0%}",
        cents=times(round(ref), funding),
        estimate_cents=p.cost,
        months=f"{p.months[0]}-{p.months[1]} months",
    )
    return Outcome(state, (), (log,))


def _running(state: GameState, company: int, stage: str) -> Programme:
    prog = ep.latest(state, company, stage)
    if prog is None or prog.status != "running":
        raise EquipmentRuleError(f"no running programme stage {stage!r}")
    return prog


def set_funding(state: GameState, action: SetLithoFunding, balance: Balance) -> Outcome:
    company = acting_company(state, action.actor_id)
    prog = _running(state, company, action.stage)
    funding = _funding(balance, action.funding)
    new = replace(prog, funding=funding)
    return Outcome(
        replace(state, programmes=tuple(new if p is prog else p for p in state.programmes))
    )


def stop_litho(state: GameState, action: StopLitho, balance: Balance) -> Outcome:
    company = acting_company(state, action.actor_id)
    prog = _running(state, company, action.stage)
    state = spend_energy(
        state, action.actor_id, "stop_litho", balance, cost=balance.equipment.programme.stop_energy
    )
    new = replace(prog, status="stopped", ended_turn=state.turn)
    return Outcome(
        replace(state, programmes=tuple(new if p is prog else p for p in state.programmes))
    )


def apply_equipment(
    state: GameState,
    action: EquipmentAction,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    if not ed.enabled(data):
        raise EquipmentRuleError("there is no equipment data")
    match action:
        case OrderTools():
            return order_tools(state, action, balance, data, balances)
        case PrepayOrder():
            return prepay_order(state, action, balance, data, balances)
        case StartLitho():
            return start_litho(state, action, rng, balance, data)
        case SetLithoFunding():
            return set_funding(state, action, balance)
        case StopLitho():
            return stop_litho(state, action, balance)
