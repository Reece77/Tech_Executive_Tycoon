"""The founder's wealth (docs/formulas.md 37.1, 37.5, M26): personal-book postings for
investments, share prices, what each holding is worth, and net worth with its parts.
Read-only except `post`, which adds one balanced entry to the personal book."""

from __future__ import annotations

import math
from fractions import Fraction

from tst.sim.data_models import Balance, GameData
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.founder.investing_models import STAKE_FULL, AngelStake, WealthPoint
from tst.sim.founder.models import FAMILY_OFFICE, PersonalEntry
from tst.sim.founder.personal import book_balances, cash_cents
from tst.sim.ledger import LedgerBalances, LedgerLine
from tst.sim.state import GameState, group_listing, listed_id, public_of, with_personal_entries

CENTS_A_DOLLAR = 100  # tunable-exempt: cents in a dollar


def post(
    state: GameState,
    person_id: int,
    memo: str,
    source: str,
    debit: str,
    credit: str,
    cents: int,
) -> GameState:
    """One balanced entry in the founder's own book (37.1); nothing for 0. A negative amount
    swaps the sides."""
    if cents == 0:
        return state
    if cents < 0:
        debit, credit, cents = credit, debit, -cents
    entry = PersonalEntry(
        turn=state.turn,
        person_id=person_id,
        memo=memo,
        source=source,
        lines=(LedgerLine(debit, cents), LedgerLine(credit, -cents)),
    )
    return with_personal_entries(state, entry)


def account_cents(state: GameState, person_id: int, account: str) -> int:
    return book_balances(state.personal_book, person_id).get(account, 0)


def family_office_cents(state: GameState, person_id: int) -> int:
    return account_cents(state, person_id, FAMILY_OFFICE)


def stake_value_cents(stake: AngelStake) -> int:
    """An angel stake at its startup's last round price (37.5)."""
    return int(Fraction(stake.stake_ppm, STAKE_FULL) * stake.last_post_cents)


def shares_outstanding(state: GameState, company_id: int, balance: Balance) -> int:
    """Shares a listed company has: the player's issued shares, a carve-out's or spin-off's
    at listing, else a listed rival's notional `personal.rival_shares` (M26 decision)."""
    if public_of(state, company_id) is not None:
        from tst.sim.markets_public.public import outstanding_shares

        return max(1, outstanding_shares(state, company_id))
    listing = group_listing(state, company_id)
    if listing is not None:
        return max(1, listing.shares)
    return balance.personal.rival_shares


def share_price_cents(
    state: GameState, company_id: int, balances: LedgerBalances, balance: Balance, data: GameData
) -> int | None:
    """A listed company's share price at the last month end (25.3, 28.1); None if private.
    At least one cent."""
    public = public_of(state, company_id)
    if public is not None:
        return max(1, public.price_cents)
    from tst.sim.mna.valuation import market_cap_cents

    cap = market_cap_cents(state, company_id, balances, balance, data)
    if cap is None:
        return None
    return max(1, round(Fraction(cap, shares_outstanding(state, company_id, balance))))


def own_stake_cents(
    state: GameState, person_id: int, balances: LedgerBalances, balance: Balance, data: GameData
) -> int:
    """The founder's stake in their own company (37.5): shares x the share price once listed,
    else their fully diluted share of 28.1's fundamental value."""
    if state.ended and state.player.failed_turn is not None:
        return 0
    cid = listed_id(state)
    held = person_shares(state, cid, person_id)
    if held <= 0:
        return 0
    public = public_of(state, cid)
    if public is not None:
        return held * public.price_cents
    from tst.sim.mna.valuation import fundamental_value_cents

    total = fd_shares(state, cid)
    if total <= 0:
        return 0
    value = fundamental_value_cents(state, cid, balances, balance, data)
    return int(Fraction(held, total) * value)


def net_worth(
    state: GameState, person_id: int, balances: LedgerBalances, balance: Balance, data: GameData
) -> WealthPoint:
    """Net worth now (37.5): personal cash, angel stakes at the last round price, public
    shares at market (holdings and M16's spin-off shares), the family office and the stake
    in the founder's own company."""
    angel = sum(
        stake_value_cents(s)
        for s in state.angel_stakes
        if s.person_id == person_id and s.status == "open"
    )
    public = 0
    for h in state.public_holdings:
        if h.person_id != person_id or h.shares <= 0:
            continue
        price = share_price_cents(state, h.company_id, balances, balance, data)
        public += h.shares * price if price is not None else h.cost_cents
    for ps in state.personal_stakes:  # M16 (31.5): spin-off shares in the founder's name
        if ps.person_id != person_id:
            continue
        from tst.sim.mna.valuation import market_cap_cents

        cap = market_cap_cents(state, ps.company_id, balances, balance, data) or 0
        public += int(Fraction(ps.stake_bp, 10_000) * cap)  # tunable-exempt: basis points
    return WealthPoint(
        person_id=person_id,
        turn=state.turn,
        cash_cents=cash_cents(state, person_id),
        angel_cents=angel,
        public_cents=public,
        family_office_cents=family_office_cents(state, person_id),
        own_stake_cents=own_stake_cents(state, person_id, balances, balance, data),
    )


def personal_wealth_cents(
    state: GameState, person_id: int, balances: LedgerBalances, balance: Balance, data: GameData
) -> int:
    """Cash plus investments at value (37.4's family-office gate): net worth without the
    founder's own company."""
    point = net_worth(state, person_id, balances, balance, data)
    return point.total_cents - point.own_stake_cents


def legacy_wealth(net_worth_cents: int, balance: Balance) -> float:
    """37.5: `legacy_points x log10(1 + net worth / unit)`; nothing for a net worth at or
    below zero."""
    pb = balance.personal
    unit = pb.legacy_unit_dollars * CENTS_A_DOLLAR
    return pb.legacy_points * math.log10(1 + max(0, net_worth_cents) / unit)
