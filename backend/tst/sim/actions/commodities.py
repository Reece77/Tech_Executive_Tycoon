"""Commodity actions (ADR-0014, docs/formulas.md 33.3, M17): sign a fixed-price commodity
contract (energy 6) or an offtake agreement with a named supplier (energy 5), with optional
prepayment. They take effect at once and spend the actor's energy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.calendar import format_turn
from tst.sim.commodities import offtake
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import CommodityRuleError, InsufficientCashError
from tst.sim.ledger import CASH, PREPAID, LedgerBalances, LedgerEntry, LedgerLine, account_balance
from tst.sim.log import inbox_item
from tst.sim.state import GameState, with_commodity_deal


@dataclass(frozen=True, slots=True)
class SignCommodityContract:
    actor_id: int
    good: str  # commodities.yaml key
    months: int
    volume_year: float  # volume units a year
    kind: Literal["sign_commodity_contract"] = "sign_commodity_contract"


@dataclass(frozen=True, slots=True)
class SignOfftake:
    actor_id: int
    good: str
    supplier: str  # suppliers.yaml key
    years: int
    volume_year: float
    prepay: float = 0.0  # share of year 1's value paid now (at most offtake.prepay_max)
    kind: Literal["sign_offtake"] = "sign_offtake"


def sign_commodity_contract(
    state: GameState, action: SignCommodityContract, balance: Balance, data: GameData
) -> Outcome:
    company = acting_company(state, action.actor_id)
    q = offtake.contract_quote(state, action.good, action.months, action.volume_year, balance, data)
    state = spend_energy(
        state,
        action.actor_id,
        "sign_commodity_contract",
        balance,
        cost=balance.commodity.contract_energy,
    )
    deal = offtake.deal_from_quote(state, offtake.next_deal_id(state), company, q)
    state = with_commodity_deal(state, deal)
    log = inbox_item(
        state.turn,
        company,
        "commodity_deal_signed",
        deal=offtake.name_of(deal, data),
        volume=f"{deal.volume_year:,.1f} {_unit(deal.good, data)} a year",
        price=f"{deal.signing_price:,.2f} {_price_unit(deal.good, data)}",
        end=format_turn(deal.end_turn),
        take_or_pay=f"{balance.commodity.contract_take_or_pay:.0%}",
    )
    return Outcome(state, (), (log,))


def sign_offtake(
    state: GameState,
    action: SignOfftake,
    balance: Balance,
    data: GameData,
    balances: LedgerBalances,
) -> Outcome:
    company = acting_company(state, action.actor_id)
    from tst.sim.geopolitics import supply as geo_supply

    banned = geo_supply.banned_supplier(  # M23a: suppliers obey their country's export bans
        state, company, action.good, action.supplier, balance, data
    )
    if banned is not None:
        raise CommodityRuleError(f"{banned.rule.title}: this supplier cannot sell it to you")
    q = offtake.offtake_quote(
        state,
        action.good,
        action.supplier,
        action.years,
        action.volume_year,
        action.prepay,
        balance,
        data,
    )
    if q.prepaid_cents and account_balance(balances, company, CASH) < q.prepaid_cents:
        raise InsufficientCashError(f"the prepayment needs {q.prepaid_cents} cents")
    state = spend_energy(
        state, action.actor_id, "sign_offtake", balance, cost=balance.offtake.energy
    )
    deal = offtake.deal_from_quote(state, offtake.next_deal_id(state), company, q)
    state = with_commodity_deal(state, deal)
    entries: tuple[LedgerEntry, ...] = ()
    if q.prepaid_cents:
        entries = (
            LedgerEntry(
                turn=state.turn,
                company_id=company,
                memo=f"Prepayment: {offtake.name_of(deal, data)}",
                lines=(LedgerLine(PREPAID, q.prepaid_cents), LedgerLine(CASH, -q.prepaid_cents)),
            ),
        )
    log = inbox_item(
        state.turn,
        company,
        "offtake_signed",
        deal=offtake.name_of(deal, data),
        volume=f"{deal.volume_year:,.1f} {_unit(deal.good, data)} a year",
        floor=f"{deal.floor:,.2f}",
        ceiling=f"{deal.ceiling:,.2f} {_price_unit(deal.good, data)}",
        end=format_turn(deal.end_turn),
        prepaid_cents=q.prepaid_cents,
        take_or_pay=f"{balance.offtake.take_or_pay:.0%}",
    )
    return Outcome(state, entries, (log,))


def _unit(good: str, data: GameData) -> str:
    assert data.commodities is not None
    return data.commodities.good(good).volume_unit


def _price_unit(good: str, data: GameData) -> str:
    assert data.commodities is not None
    return data.commodities.good(good).unit
