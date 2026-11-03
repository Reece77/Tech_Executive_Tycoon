"""Capital actions once public (docs/formulas.md 25.5): buyback, dividend and secondary
offering. The rules live here; the immediate actions spend energy and call them."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance
from tst.sim.errors import InvalidActionError
from tst.sim.finance.captable import fd_shares
from tst.sim.finance.models import CapEntry
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.markets_public import formulas as pf
from tst.sim.markets_public.ipo import PUBLIC_HOLDERS
from tst.sim.markets_public.models import PublicCompany
from tst.sim.state import GameState, public_of, with_cap_entry, with_public


def listed(state: GameState, company_id: int) -> PublicCompany:
    public = public_of(state, company_id)
    if public is None:
        raise InvalidActionError("only a listed company can do that")
    return public


def _float_entry(state: GameState, company_id: int) -> CapEntry | None:
    entries = [
        e
        for e in state.company_cap(company_id)
        if e.holder_kind == "group" and e.name == PUBLIC_HOLDERS
    ]
    return min(entries, key=lambda e: e.id) if entries else None


def buyback_price_cents(public: PublicCompany, balance: Balance) -> int:
    return round(public.price_cents * (1 + balance.public.capital.buyback_premium))


def buyback(
    state: GameState, company_id: int, amount_cents: int, cash_cents: int, balance: Balance
) -> tuple[GameState, LedgerEntry, int, int]:
    """Buy shares at P x 1.02 from the public float (25.5): cash leaves to common equity
    (treasury) and shares outstanding fall. Returns the state, the entry, the shares and the
    cost."""
    public = listed(state, company_id)
    cb = balance.public.capital
    if amount_cents <= 0:
        raise InvalidActionError("a buyback needs a positive amount")
    if amount_cents > cash_cents:
        raise InvalidActionError("a buyback cannot spend more cash than the company has")
    price = buyback_price_cents(public, balance)
    entry = _float_entry(state, company_id)
    cap = min(
        int(fd_shares(state, company_id) * cb.buyback_max_share),
        entry.shares if entry else 0,
    )
    shares = min(amount_cents // price, cap)
    if shares <= 0:
        raise InvalidActionError("the amount buys no shares")
    assert entry is not None
    cost = shares * price
    state = with_cap_entry(state, replace(entry, shares=entry.shares - shares))
    posted = LedgerEntry.transfer(
        turn=state.turn,
        company_id=company_id,
        memo=f"Buyback: {shares:,} shares at ${price / pf.PCT:,.2f}",
        debit=COMMON_EQUITY,
        credit=CASH,
        amount=cost,
    )
    return state, posted, shares, cost


def declare_dividend(
    state: GameState, company_id: int, per_share_cents: int, cash_cents: int, outstanding: int
) -> GameState:
    """A cash amount per share, paid at the next month end (25.5)."""
    public = listed(state, company_id)
    if per_share_cents <= 0:
        raise InvalidActionError("a dividend needs a positive amount a share")
    if public.dividend_cents:
        raise InvalidActionError("a dividend is already declared for this month")
    if per_share_cents * outstanding > cash_cents:
        raise InvalidActionError("the dividend would cost more cash than the company has")
    return with_public(state, replace(public, dividend_cents=per_share_cents))


def secondary(
    state: GameState, company_id: int, shares: int, balance: Balance
) -> tuple[GameState, LedgerEntry, int]:
    """New shares at P x 0.95 less a 3% fee (25.5). Returns the state, the entry and the net."""
    public = listed(state, company_id)
    cb = balance.public.capital
    if shares <= 0:
        raise InvalidActionError("an offering needs a positive number of shares")
    if shares > fd_shares(state, company_id) * cb.secondary_max_share:
        raise InvalidActionError(
            f"one offering sells at most {cb.secondary_max_share:.0%} of the shares"
        )
    price = round(public.price_cents * (1 - cb.secondary_discount))
    gross = shares * price
    net = gross - round(gross * cb.secondary_fee)
    entry = _float_entry(state, company_id)
    if entry is not None:
        state = with_cap_entry(state, replace(entry, shares=entry.shares + shares))
    else:
        entry_id, ids = state.next_ids.take("cap_entry")
        state = with_cap_entry(
            replace(state, next_ids=ids),
            CapEntry(
                entry_id, company_id, "group", "common", shares, state.turn, name=PUBLIC_HOLDERS
            ),
        )
    posted = LedgerEntry.transfer(
        turn=state.turn,
        company_id=company_id,
        memo=f"Secondary offering: {shares:,} shares at ${price / pf.PCT:,.2f}, net of fees",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=net,
    )
    return state, posted, net
