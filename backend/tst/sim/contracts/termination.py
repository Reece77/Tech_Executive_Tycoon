"""Breaking a contract (M23a; playtest 5's Terminate button).

Every contract and offtake the player's group holds can be terminated before its end: commodity
contracts and offtakes (33.3), refinery contracts (36.1), contract-manufacturing and foundry
(wafer) contracts (26.2, 26.3), a mine's sale contracts (35.3) and a fab's foundry contracts
(below). The **fee** is quoted first (`quote`) and is

    the remaining months' take-or-pay minimum, discounted monthly at the base rate (20.1),
    x (1 + contracts.break_penalty)

where a month's minimum is the contract's take-or-pay share x its monthly volume x its price: the
share each kind already charges on what it does not take (commodity.contract_take_or_pay,
offtake.take_or_pay, refining.deal.take_or_pay, hardware.contract.take_or_pay,
chips.contract.take_or_pay, contracts.mine_take_or_pay, contracts.foundry.take_or_pay). An
offtake's unused prepayment counts against the fee (the supplier keeps it; any excess comes back).
The fee posts to 6900 general and admin against cash; the contract ends this month.

The **counterparty remembers** (`relations`): its score (0-1, 1 by default) falls
contracts.relationship_hit and recovers contracts.relationship_recovery a month. A new deal with
it costs price x (1 + contracts.relationship_premium x (1 - score)) (`premium`), and below
contracts.relationship_floor it signs nothing new (`check_willing`).

Everything is exact (money.exact; Codex review 5 finding 10): fractions until the posting.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Final, Literal

from tst.sim.actions.hiring import Outcome, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.contracts.models import ContractKind, Relation
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InsufficientCashError, InvalidActionError
from tst.sim.ledger import CASH, GENERAL_ADMIN, PREPAID, LedgerBalances, LedgerEntry, LedgerLine
from tst.sim.log import inbox_item
from tst.sim.money import MILLICENTS_PER_CENT, exact, format_money
from tst.sim.state import (
    GameState,
    company_cash,
    with_commodity_deal,
    with_foundry_contract,
    with_mine_deal,
    with_production_contract,
    with_refining_deal,
    with_relation,
)

MONTHS: Final = 12  # tunable-exempt: calendar
PERCENT: Final = 100  # tunable-exempt: the base rate is a percentage
KINDS: Final = ("commodity", "refining", "production", "mine", "foundry")


@dataclass(frozen=True, slots=True)
class TerminateContract:
    """Break one contract of the player's group (module docstring) at its quoted fee."""

    actor_id: int
    contract: ContractKind
    contract_id: int
    kind: Literal["terminate_contract"] = "terminate_contract"


ACTION_TYPES: Final[dict[str, type]] = {"terminate_contract": TerminateContract}


@dataclass(frozen=True, slots=True)
class TerminationQuote:
    contract: ContractKind
    contract_id: int
    company_id: int
    counterparty: str
    months_left: int
    monthly_minimum_cents: int
    discounted_cents: int  # the months' minimums discounted at the base rate
    penalty_cents: int
    prepaid_cents: int  # an offtake's unused prepayment, kept against the fee
    fee_cents: int  # discounted + penalty
    cash_cents: int  # what leaves cash: the fee less the prepayment (negative: a refund)


# --- Relations ---------------------------------------------------------------------------------


def score(state: GameState, counterparty: str, balance: Balance) -> Fraction:
    """A counterparty's willingness to deal now (module docstring)."""
    r = next((x for x in state.relations if x.counterparty == counterparty), None)
    if r is None:
        return Fraction(1)
    recovered = exact(r.score) + exact(balance.contracts.relationship_recovery) * (
        state.turn - r.turn
    )
    return min(Fraction(1), recovered)


def premium(state: GameState, counterparty: str, balance: Balance) -> Fraction:
    """A new deal's price multiple with this counterparty: 1 + premium x (1 - score)."""
    cb = balance.contracts
    return 1 + exact(cb.relationship_premium) * (1 - score(state, counterparty, balance))


def check_willing(state: GameState, counterparty: str, label: str, balance: Balance) -> None:
    if score(state, counterparty, balance) < exact(balance.contracts.relationship_floor):
        raise InvalidActionError(
            f"{label} will not sign with your group again yet: you broke contracts with it"
        )


def offered(
    state: GameState, counterparty: str, price: float, balance: Balance, *, buying: bool = True
) -> float:
    """A new deal's price with a counterparty the group broke a contract with: dearer to buy
    from it, cheaper to sell to it (x or / the premium); unchanged otherwise."""
    if not any(x.counterparty == counterparty for x in state.relations):
        return price
    p = premium(state, counterparty, balance)
    return float(exact(price) * p) if buying else float(exact(price) / p)


def remember(state: GameState, counterparty: str, balance: Balance) -> GameState:
    now = score(state, counterparty, balance)
    old = next((x for x in state.relations if x.counterparty == counterparty), None)
    hit = max(Fraction(0), now - exact(balance.contracts.relationship_hit))
    return with_relation(
        state,
        Relation(counterparty, float(hit), state.turn, (old.breaks if old else 0) + 1),
    )


# --- Quotes ------------------------------------------------------------------------------------


def discounted(monthly: Fraction, months: int, base_rate_pct: float) -> Fraction:
    """Sum over the months left of the month's minimum / (1 + r / 12)^k, k = 1..months."""
    step = 1 + exact(base_rate_pct) / PERCENT / MONTHS
    total = Fraction(0)
    factor = Fraction(1)
    for _ in range(months):
        factor /= step
        total += monthly * factor
    return total


def _group(state: GameState) -> set[int]:
    from tst.sim.group.assets import group_ids

    return group_ids(state)


def _terms(
    state: GameState, contract: ContractKind, contract_id: int, balance: Balance, data: GameData
) -> tuple[int, str, int, Fraction, int]:
    """(company, counterparty, last month, a month's minimum in cents, unused prepayment)."""
    from tst.sim.commodities import offtake

    group = _group(state)
    if contract == "commodity":
        d = next((x for x in state.commodity_deals if x.id == contract_id), None)
        if d is None or d.company_id not in group or not d.running(state.turn):
            raise InvalidActionError(f"no running commodity deal {contract_id}")
        commodity_share = exact(
            balance.offtake.take_or_pay
            if d.kind == "offtake"
            else balance.commodity.contract_take_or_pay
        )
        value = exact(offtake.value_cents(d.monthly_volume, d.signing_price, d.good, data))
        who = d.supplier or f"traders:{d.good}"
        return d.company_id, who, d.end_turn, commodity_share * value, d.prepaid_left_cents
    if contract == "refining":
        r = next((x for x in state.refining_deals if x.id == contract_id), None)
        if r is None or r.company_id not in group or not r.running(state.turn):
            raise InvalidActionError(f"no running refinery contract {contract_id}")
        share = exact(balance.refining.deal.take_or_pay)
        value = exact(r.monthly_volume) * exact(r.price_cents)
        return r.company_id, f"refining:{r.good}", r.end_turn, share * value, 0
    if contract == "production":
        c = next((x for x in state.production_contracts if x.id == contract_id), None)
        if c is None or c.company_id not in group or not c.running(state.turn):
            raise InvalidActionError(f"no running production contract {contract_id}")
        production_share = exact(
            balance.chips.contract.take_or_pay
            if c.kind == "wafer"
            else balance.hardware.contract.take_or_pay
        )
        value = Fraction(c.units * c.price_millicents, MILLICENTS_PER_CENT)
        return c.company_id, c.supplier, c.end_turn, production_share * value, 0
    if contract == "mine":
        m = next((x for x in state.mine_deals if x.id == contract_id), None)
        mine = state.mine(m.mine_id) if m is not None else None
        if m is None or mine is None or mine.company_id not in group or not m.running(state.turn):
            raise InvalidActionError(f"no running mine sale {contract_id}")
        value = exact(m.volume_t_year) / MONTHS * exact(m.last_usd_t or m.signing_usd_t) * 100
        share = exact(balance.contracts.mine_take_or_pay)
        return mine.company_id, m.buyer, m.end_turn, share * value, 0
    f = next((x for x in state.foundry_contracts if x.id == contract_id), None)
    if f is None or f.company_id not in group or not f.running(state.turn):
        raise InvalidActionError(f"no running foundry contract {contract_id}")
    share = exact(balance.contracts.foundry.take_or_pay)
    return (
        f.company_id,
        f.customer,
        f.end_turn,
        share * exact(f.monthly_starts) * Fraction(f.price_millicents, MILLICENTS_PER_CENT),
        0,
    )


def quote(
    state: GameState, contract: ContractKind, contract_id: int, balance: Balance, data: GameData
) -> TerminationQuote:
    if contract not in KINDS:
        raise InvalidActionError(f"a contract is one of {', '.join(KINDS)}")
    company, who, end, monthly, prepaid = _terms(state, contract, contract_id, balance, data)
    months = max(0, end - state.turn + 1)  # this month and every later one it covers
    pv = discounted(monthly, months, state.macro.base_rate if state.macro else 0.0)
    penalty = pv * exact(balance.contracts.break_penalty)
    fee = round(pv + penalty)
    return TerminationQuote(
        contract=contract,
        contract_id=contract_id,
        company_id=company,
        counterparty=who,
        months_left=months,
        monthly_minimum_cents=round(monthly),
        discounted_cents=round(pv),
        penalty_cents=fee - round(pv),
        prepaid_cents=prepaid,
        fee_cents=fee,
        cash_cents=fee - prepaid,
    )


# --- The action --------------------------------------------------------------------------------


def _end(state: GameState, contract: ContractKind, contract_id: int) -> GameState:
    last = state.turn - 1
    if contract == "commodity":
        d = next(x for x in state.commodity_deals if x.id == contract_id)
        return with_commodity_deal(state, replace(d, end_turn=last, status="ended"))
    if contract == "refining":
        r = next(x for x in state.refining_deals if x.id == contract_id)
        return with_refining_deal(state, replace(r, end_turn=last, status="ended"))
    if contract == "production":
        c = next(x for x in state.production_contracts if x.id == contract_id)
        return with_production_contract(state, replace(c, end_turn=last, status="ended"))
    if contract == "mine":
        m = next(x for x in state.mine_deals if x.id == contract_id)
        return with_mine_deal(state, replace(m, end_turn=last))
    f = next(x for x in state.foundry_contracts if x.id == contract_id)
    return with_foundry_contract(state, replace(f, end_turn=last, status="ended"))


def terminate(
    state: GameState,
    action: TerminateContract,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> Outcome:
    founder = state.founder_of(state.player.id)
    if founder is None or founder.id != action.actor_id:
        raise InvalidActionError("only the founder breaks the group's contracts")
    q = quote(state, action.contract, action.contract_id, balance, data)
    if q.cash_cents > 0 and company_cash(balances, q.company_id) < q.cash_cents:
        raise InsufficientCashError(f"breaking it costs {format_money(q.cash_cents)}")
    state = spend_energy(
        state, action.actor_id, action.kind, balance, cost=balance.contracts.terminate_energy
    )
    if action.contract == "commodity" and q.prepaid_cents:
        d = next(x for x in state.commodity_deals if x.id == action.contract_id)
        state = with_commodity_deal(state, replace(d, prepaid_left_cents=0))
    state = remember(_end(state, action.contract, action.contract_id), q.counterparty, balance)
    lines = [
        LedgerLine(GENERAL_ADMIN, q.fee_cents),
        LedgerLine(PREPAID, -q.prepaid_cents),
        LedgerLine(CASH, -q.cash_cents),
    ]
    entries: tuple[LedgerEntry, ...] = ()
    if any(x.amount for x in lines):
        entries = (
            LedgerEntry(
                state.turn,
                q.company_id,
                f"Contract terminated: {q.counterparty}",
                tuple(x for x in lines if x.amount),
            ),
        )
    log = inbox_item(
        state.turn,
        state.player.id,
        "contract_terminated",
        link_kind="group",
        counterparty=q.counterparty,
        fee=format_money(q.fee_cents),
        month=format_turn(state.turn),
    )
    return Outcome(state, entries, (log,))


__all__ = [
    "ACTION_TYPES",
    "TerminateContract",
    "TerminationQuote",
    "check_willing",
    "offered",
    "premium",
    "quote",
    "score",
    "terminate",
]
