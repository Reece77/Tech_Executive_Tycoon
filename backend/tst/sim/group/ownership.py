"""Ownership history and disposals (M16, docs/formulas.md 31.1; Codex review 4 findings 2
and 3). A holding opens when a company is kept as a brand (a closing, or a sale after a
takeover bid) and ends when the company fails, is sold or is spun off. The end posts a
**disposal** on the owner's books: its investment and the goodwill it paid go out, the
difference to what it received goes to 4930."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import GameData
from tst.sim.group.models import EndReason, Ownership
from tst.sim.ledger import (
    CASH,
    DISPOSAL,
    GOODWILL,
    INVESTMENT_SUBSIDIARIES,
    LedgerBalances,
    LedgerEntry,
    LedgerLine,
    account_balance,
)
from tst.sim.log import LogItem
from tst.sim.mna import formulas as mf
from tst.sim.state import GameState, owner_at, with_company, with_ownership

BALANCE_SHEET = ("asset", "liability")


def book_cents(balances: LedgerBalances, company_id: int, data: GameData) -> int:
    """A company's book equity: its balance-sheet accounts' sum (debit positive)."""
    return sum(
        account_balance(balances, company_id, a.code)
        for a in data.accounts
        if a.type in BALANCE_SHEET
    )


def equity_cents(balances: LedgerBalances, company_id: int, data: GameData) -> int:
    """A company's equity accounts' balance (debit positive, so usually negative)."""
    return sum(
        account_balance(balances, company_id, a.code) for a in data.accounts if a.type == "equity"
    )


def carrying_cents(ownership: Ownership, balances: LedgerBalances, data: GameData) -> int:
    """The owner's 1810 investment in the company now: its book equity at closing, less what
    has been swept since and plus what has been funded (each moves the company's equity by
    the same amount, 28.5)."""
    now = equity_cents(balances, ownership.company_id, data)
    return ownership.book_cents - (now - ownership.equity_cents)


def goodwill_of(state: GameState, ownership: Ownership) -> int:
    """The goodwill the owner booked when it bought the company (28.3): the price less the
    book equity, from the acquisition closed at the holding's start; 0 without one. A holding
    passed on inside the group carries the goodwill it came with."""
    if ownership.goodwill_cents is not None:
        return ownership.goodwill_cents
    for a in reversed(state.acquisitions):
        if (
            a.target_id == ownership.company_id
            and a.acquirer_id == ownership.owner_id
            and a.closed_turn == ownership.from_turn
        ):
            return mf.goodwill_cents(a.price_cents, ownership.book_cents)
    return 0


def acquire(
    state: GameState,
    company_id: int,
    owner_id: int,
    balances: LedgerBalances,
    data: GameData,
) -> GameState:
    """Open a holding of `company_id` by `owner_id` from this turn (a kept brand's closing),
    ending the seller's holding if there was one. The company's parent changes where the
    closing sets it (tst.sim.mna.integration, tst.sim.modes.serial)."""
    held = owner_at(state, company_id)
    if held is not None and held.id:
        state = with_ownership(state, replace(held, to_turn=state.turn, end_reason="sold"))
    return with_ownership(
        state,
        Ownership(
            id=0,
            company_id=company_id,
            owner_id=owner_id,
            from_turn=state.turn,
            book_cents=book_cents(balances, company_id, data),
            equity_cents=equity_cents(balances, company_id, data),
        ),
    )


def disposal_entry(
    state: GameState,
    ownership: Ownership,
    balances: LedgerBalances,
    data: GameData,
    received_cents: int = 0,
    memo: str | None = None,
) -> LedgerEntry | None:
    """The owner's disposal (31.1): the investment (1810) and the company's goodwill (1800)
    out, what it received in cash in, the difference to 4930 (a debit is a loss)."""
    investment = carrying_cents(ownership, balances, data)
    goodwill = goodwill_of(state, ownership)
    name = state.company(ownership.company_id).name
    lines = (
        LedgerLine(CASH, received_cents),
        LedgerLine(INVESTMENT_SUBSIDIARIES, -investment),
        LedgerLine(GOODWILL, -goodwill),
        LedgerLine(DISPOSAL, investment + goodwill - received_cents),
    )
    kept = tuple(x for x in lines if x.amount != 0)
    if len(kept) < 2:
        return None
    return LedgerEntry(state.turn, ownership.owner_id, memo or f"Disposal of {name}", kept)


def end_holding(
    state: GameState,
    ownership: Ownership,
    reason: EndReason,
    balances: LedgerBalances,
    data: GameData,
    received_cents: int = 0,
) -> tuple[GameState, list[LedgerEntry]]:
    """End a holding this turn with its disposal; the company no longer has a parent. A
    holding without a record (a hand-built state's brand: id 0) is recorded as it ends."""
    # a holding with no record (id 0) has no known investment at closing: nothing posts
    entry = (
        disposal_entry(state, ownership, balances, data, received_cents) if ownership.id else None
    )
    ended = replace(ownership, to_turn=state.turn, end_reason=reason)
    state = with_ownership(state, ended)
    company = state.company(ownership.company_id)
    if company.parent_id == ownership.owner_id:
        state = with_company(state, replace(company, parent_id=None))
    return state, [entry] if entry is not None else []


def disposals(
    state: GameState, balances: LedgerBalances, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Phase 7 after insolvency: every held company that has failed leaves its owner's group
    this turn (31.1; Codex review 4 finding 2). Its earlier periods keep its contributions;
    the owner writes off its investment and goodwill. Pre-M16 saves' failed brands are
    disposed of the first month this runs."""
    entries: list[LedgerEntry] = []
    for company in state.companies:
        if company.alive:
            continue
        held = owner_at(state, company.id)
        if held is None:
            continue
        state, posted = end_holding(state, held, "failed", balances, data)
        entries += posted
    return state, tuple(entries), ()
