"""Foundry contracts (M23a; playtest 5's fab card: "there are no contracts to lock in foundry
customers"; docs/formulas.md 38.2).

A fab's owner signs a rival chip designer (the chip incumbents, as 38.2's slot buyers) for
`monthly_starts` wafer starts a month over contracts.foundry.months at a price a start of at most
contracts.foundry.max_price x the node's slot price (its market price x fab.slot.discount). One
designer contracts at most contracts.foundry.customer_share of the fab's capacity, and the fab's
contracts together at most contracts.foundry.max_share. A designer that the group broke a
contract with signs only above contracts.relationship_floor, at no better than its premium.

Each month (`plants.settle_fabs`) the contracts take the fab's spare starts first, in id order,
before spot slots: the designer takes what the fab delivers (their demand is abstract), paying the
contract price to 4420 foundry sales. A live fab short of starts delivers less, and owes nothing;
contracts.foundry.take_or_pay is what the designer would owe on starts it did not take, so it
prices the owner's early termination (contracts.termination).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.contracts import termination as ct
from tst.sim.contracts.models import FoundryContract
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import FabRuleError
from tst.sim.fabs import market as fm
from tst.sim.fabs.models import Fab
from tst.sim.log import inbox_item
from tst.sim.money import format_money
from tst.sim.state import GameState, with_foundry_contract

EPS: Final = 1e-9  # tunable-exempt: float tolerance on starts


@dataclass(frozen=True, slots=True)
class SignFoundryContract:
    actor_id: int
    fab_id: int
    customer: str  # a chip incumbent's name
    monthly_starts: float
    months: int
    price_cents: float  # a start
    kind: Literal["sign_foundry_contract"] = "sign_foundry_contract"


ACTION_TYPES: Final[dict[str, type]] = {"sign_foundry_contract": SignFoundryContract}


def customers(data: GameData) -> list[str]:
    """The rival designers a fab can sign: the chip incumbents (38.2's slot buyers)."""
    return [
        c.name
        for c in data.incumbents
        if any(data.category(p.category).chip_type is not None for p in c.products)
    ]


def running(state: GameState, fab_id: int) -> list[FoundryContract]:
    return [c for c in state.foundry_contracts if c.fab_id == fab_id and c.running(state.turn)]


def slot_price_cents(state: GameState, fab: Fab, balance: Balance, data: GameData) -> float:
    return fm.node_price_cents(state, fab.node, balance, data) * balance.fab.slot.discount


def sign(
    state: GameState, action: SignFoundryContract, balance: Balance, data: GameData
) -> Outcome:
    from tst.sim.group.assets import group_ids

    founder = state.founder_of(state.player.id)
    if founder is None or founder.id != action.actor_id:
        raise FabRuleError("only the founder signs the group's foundry contracts")
    fab = fm.fab_of(state, action.fab_id)
    facility = state.facility(action.fab_id)
    if fab is None or facility is None or facility.company_id not in group_ids(state):
        raise FabRuleError(f"no fab {action.fab_id} in your group")
    if facility.status == "closed":
        raise FabRuleError("that fab is closed")
    fb = balance.contracts.foundry
    if action.customer not in customers(data):
        raise FabRuleError(f"the designers are {', '.join(customers(data))}")
    if not fb.months.lo <= action.months <= fb.months.hi:
        raise FabRuleError(f"a foundry contract runs {fb.months.lo:g}-{fb.months.hi:g} months")
    if action.monthly_starts <= 0 or action.price_cents <= 0:
        raise FabRuleError("a foundry contract needs starts and a price")
    ct.check_willing(state, action.customer, action.customer, balance)
    ceiling = slot_price_cents(state, fab, balance, data) * fb.max_price
    ceiling /= float(ct.premium(state, action.customer, balance))
    if action.price_cents > ceiling * (1 + EPS):
        raise FabRuleError(
            f"{action.customer} pays at most {format_money(round(ceiling))} a start at this node"
        )
    cap = facility.capacity
    mine = sum(
        c.monthly_starts for c in running(state, fab.facility_id) if c.customer == action.customer
    )
    if mine + action.monthly_starts > cap * fb.customer_share * (1 + EPS):
        raise FabRuleError(
            f"one designer takes at most {cap * fb.customer_share:,.0f} starts a month here"
        )
    total = sum(c.monthly_starts for c in running(state, fab.facility_id))
    if total + action.monthly_starts > cap * fb.max_share * (1 + EPS):
        raise FabRuleError(f"at most {cap * fb.max_share:,.0f} starts a month go under contract")
    state = spend_energy(state, action.actor_id, action.kind, balance, cost=fb.energy)
    contract = FoundryContract(
        id=max((c.id for c in state.foundry_contracts), default=0) + 1,
        fab_id=fab.facility_id,
        company_id=facility.company_id,
        customer=action.customer,
        monthly_starts=action.monthly_starts,
        price_cents=action.price_cents,
        signed_turn=state.turn,
        end_turn=state.turn + action.months - 1,
    )
    state = with_foundry_contract(state, contract)
    from tst.sim.fabs.plants import fab_name

    log = inbox_item(
        state.turn,
        state.player.id,
        "foundry_contract_signed",
        link_kind="fab",
        link_id=fab.facility_id,
        customer=action.customer,
        starts=f"{action.monthly_starts:,.0f}",
        fab=fab_name(state, fab, balance, data),
        price=format_money(round(action.price_cents)),
        end=format_turn(contract.end_turn),
    )
    return Outcome(state, (), (log,))


def deliver(
    state: GameState, fab: Fab, spare: float
) -> tuple[GameState, float, float, tuple[tuple[str, float], ...]]:
    """The month's contracted starts out of `spare` (module docstring): (state, starts
    delivered, revenue cents, (customer, starts) rows)."""
    left = spare
    revenue = 0.0
    rows: list[tuple[str, float]] = []
    for c in sorted(running(state, fab.facility_id), key=lambda x: x.id):
        got = min(left, c.monthly_starts)
        left -= got
        revenue += got * c.price_cents
        if got > EPS:
            rows.append((c.customer, got))
        state = with_foundry_contract(state, replace(c, delivered=got))
    return state, spare - left, revenue, tuple(rows)


def end_contracts(state: GameState) -> GameState:
    for c in state.foundry_contracts:
        if c.status == "active" and state.turn > c.end_turn:
            state = with_foundry_contract(state, replace(c, status="ended"))
    return state


__all__ = ["ACTION_TYPES", "SignFoundryContract", "customers", "deliver", "running", "sign"]
