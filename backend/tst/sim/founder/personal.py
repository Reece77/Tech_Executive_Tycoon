"""The founder's personal account (docs/formulas.md 32.2, M24): a separate double-entry book
in integer cents, never mixed with a company's (ADR-0003). `credit` is the only way money
enters it; gifts move personal cash to the foundation's endowment and grants leave it."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from tst.sim.data_models import Balance
from tst.sim.errors import InvalidActionError
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.founder.models import (
    ENDOWMENT,
    INCOME_SOURCES,
    PERSONAL_CASH,
    PERSONAL_INCOME,
    PERSONAL_SPENDING,
    PersonalEntry,
)
from tst.sim.ledger import LedgerLine
from tst.sim.log import LogItem, inbox_item
from tst.sim.markets_public import formulas as pf
from tst.sim.markets_public.capital import listed
from tst.sim.markets_public.ipo import PUBLIC_HOLDERS
from tst.sim.state import GameState, with_cap_entry, with_personal_entries


def _entry(
    turn: int, person_id: int, memo: str, source: str, debit: str, credit: str, cents: int
) -> PersonalEntry:
    return PersonalEntry(
        turn=turn,
        person_id=person_id,
        memo=memo,
        source=source,
        lines=(LedgerLine(debit, cents), LedgerLine(credit, -cents)),
    )


def credit(state: GameState, person_id: int, cents: int, source: str, memo: str = "") -> GameState:
    """Money into the founder's personal cash from `source` (32.2's hook: secondaries,
    dividends, exits, salary; M16 calls it for group dividends). Nothing for 0 or less."""
    if source not in INCOME_SOURCES:
        raise ValueError(f"unknown personal income source {source!r}")
    if cents <= 0:
        return state
    entry = _entry(
        state.turn, person_id, memo or source, source, PERSONAL_CASH, PERSONAL_INCOME, cents
    )
    return with_personal_entries(state, entry)


def gift(state: GameState, person_id: int, cents: int) -> GameState:
    """Personal cash to the foundation's endowment (32.3)."""
    entry = _entry(
        state.turn, person_id, "Gift to the foundation", "gift", ENDOWMENT, PERSONAL_CASH, cents
    )
    return with_personal_entries(state, entry)


def grant(state: GameState, person_id: int, cents: int) -> GameState:
    """A year's grants leave the endowment (32.3)."""
    entry = _entry(
        state.turn,
        person_id,
        "Foundation grants",
        "grant",
        PERSONAL_SPENDING,
        ENDOWMENT,
        cents,
    )
    return with_personal_entries(state, entry)


def book_balances(entries: Iterable[PersonalEntry], person_id: int) -> dict[str, int]:
    """Each personal account's balance (debit positive) for one founder."""
    out: dict[str, int] = {}
    for e in entries:
        if e.person_id != person_id:
            continue
        for line in e.lines:
            out[line.account] = out.get(line.account, 0) + line.amount
    return out


def cash_cents(state: GameState, person_id: int) -> int:
    return book_balances(state.personal_book, person_id).get(PERSONAL_CASH, 0)


def endowment_cents(state: GameState, person_id: int) -> int:
    return book_balances(state.personal_book, person_id).get(ENDOWMENT, 0)


def income_by_source(state: GameState, person_id: int) -> dict[str, int]:
    out = dict.fromkeys(INCOME_SOURCES, 0)
    for e in state.personal_book:
        if e.person_id == person_id and e.source in out:
            out[e.source] += sum(line.amount for line in e.lines if line.account == PERSONAL_CASH)
    return out


def salary_month(state: GameState, balance: Balance) -> GameState:
    """The founder's salary after tax reaches the book each month (32.2); the company's
    payroll already paid it (6000_salaries). A founder on 0 salary gets nothing."""
    company = state.player
    founder = state.founder_of(company.id)
    job = state.employment_of(founder.id) if founder is not None else None
    if founder is None or job is None or job.salary_cents <= 0:
        return state
    net = job.salary_cents - round(job.salary_cents * balance.personal.tax_rate)
    return credit(state, founder.id, net, "salary", "Salary after tax")


def dividend_share(state: GameState, company_id: int, per_share_cents: int) -> GameState:
    """The founder's share of a dividend paid (32.2, 25.5): per share x the founder's
    shares. Called where the dividend is paid."""
    founder = state.founder_of(company_id)
    if founder is None or per_share_cents <= 0:
        return state
    cents = per_share_cents * person_shares(state, company_id, founder.id)
    return credit(state, founder.id, cents, "dividend", "Dividend on your shares")


def sell_shares(
    state: GameState, company_id: int, person_id: int, shares: int, balance: Balance
) -> tuple[GameState, int, LogItem]:
    """The founder sells some of their own shares into the public float (32.2; M24 decision):
    at 25.5's secondary price P x (1 - secondary_discount) less secondary_fee, at most
    secondary_max_share of the shares in one sale. The company's books do not move; the net
    reaches the founder's personal cash. Returns the state, the net and the news."""
    public = listed(state, company_id)
    cb = balance.public.capital
    held = person_shares(state, company_id, person_id)
    if shares <= 0:
        raise InvalidActionError("a sale needs a positive number of shares")
    if shares > held:
        raise InvalidActionError(f"you hold {held:,} shares")
    if shares > fd_shares(state, company_id) * cb.secondary_max_share:
        raise InvalidActionError(
            f"one sale sells at most {cb.secondary_max_share:.0%} of the shares"
        )
    price = round(public.price_cents * (1 - cb.secondary_discount))
    gross = shares * price
    net = gross - round(gross * cb.secondary_fee)
    mine = [
        e
        for e in state.company_cap(company_id)
        if e.holder_kind == "person" and e.person_id == person_id
    ]
    left = shares
    for entry in sorted(mine, key=lambda e: e.id):
        take = min(left, entry.shares)
        state = with_cap_entry(state, replace(entry, shares=entry.shares - take))
        left -= take
        if not left:
            break
    floats = [
        e
        for e in state.company_cap(company_id)
        if e.holder_kind == "group" and e.name == PUBLIC_HOLDERS
    ]
    if floats:
        first = min(floats, key=lambda e: e.id)
        state = with_cap_entry(state, replace(first, shares=first.shares + shares))
    else:
        from tst.sim.finance.models import CapEntry

        entry_id, ids = state.next_ids.take("cap_entry")
        state = with_cap_entry(
            replace(state, next_ids=ids),
            CapEntry(
                entry_id, company_id, "group", "common", shares, state.turn, name=PUBLIC_HOLDERS
            ),
        )
    memo = f"Sold {shares:,} of your shares at ${price / pf.PCT:,.2f}, net of fees"
    state = credit(state, person_id, net, "secondary", memo)
    log = inbox_item(
        state.turn,
        company_id,
        "founder_shares_sold",
        shares=f"{shares:,}",
        net_cents=net,
    )
    return state, net, log
