"""Estate planning and estate tax (docs/formulas.md 45.6). Public rules only: the home
region's rate above its exemption (estate_tax.<region>, by year from the M36 dossier), gift
tax on lifetime gifts above the same exemption where the region has one, a family trust that
holds shares outside the estate (the head still votes them), and shares given to the
foundation. At a health succession the estate pays its tax from personal cash first, then by
selling shares, and what is left passes to the heir."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.family import rules
from tst.sim.family.config import EstateRegion, EstateYear
from tst.sim.family.models import ESTATE_BUYERS, FOUNDATION_HOLDER, TRUST_HOLDER
from tst.sim.family.transfers import move_book, move_person_shares
from tst.sim.finance.captable import fd_shares, last_round, person_shares
from tst.sim.founder.models import (
    ANGEL,
    ENDOWMENT,
    FAMILY_OFFICE,
    PERSONAL_CASH,
    PERSONAL_INCOME,
    PERSONAL_SPENDING,
    PUBLIC_SHARES,
)
from tst.sim.founder.personal import book_balances, cash_cents
from tst.sim.founder.wealth import post, stake_value_cents
from tst.sim.ledger import LedgerBalances
from tst.sim.log import LogItem, inbox_item
from tst.sim.markets_public.ipo import PUBLIC_HOLDERS
from tst.sim.state import (
    GameState,
    foundation_of,
    listed_id,
    public_of,
    with_angel_stake,
    with_family,
    with_public_holding,
)

ESTATE_SOURCE: Final = "estate"
RATE_STEPS: Final = 10_000  # tunable-exempt: a rate as an exact fraction (to 1/10,000)


def rule(balance: Balance, region: str, turn: int) -> EstateYear:
    """The region's rate and exemption in the calendar year of `turn` (the last change at or
    before it; before the first, the first)."""
    data: EstateRegion = balance.estate_tax[region]
    year, _ = turn_to_ym(turn)
    current = data.history[0]
    for h in data.history:
        if h.year <= year:
            current = h
    return current


def share_price(
    state: GameState,
    company_id: int,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> int:
    """Cents a share: the market price once listed; else the fully diluted share of 28.1's
    value with balances, or the last round's price; at least one cent."""
    public = public_of(state, company_id)
    if public is not None:
        return max(1, public.price_cents)
    if balances is not None:
        from tst.sim.mna.valuation import fundamental_value_cents

        fd = fd_shares(state, company_id)
        if fd > 0:
            value = fundamental_value_cents(state, company_id, balances, balance, data)
            return max(1, int(Fraction(value, fd)))
    latest = last_round(state, company_id)
    price = latest.price if latest is not None else None
    return max(1, int(price)) if price is not None else 1


@dataclass(frozen=True, slots=True)
class EstateQuote:
    """What the estate would owe now (45.6; public)."""

    region: str
    rate: float
    exemption_cents: int
    used_exemption_cents: int  # by lifetime gifts
    shares: int  # the head's own shares in the listed (or operating) company
    share_price_cents: int
    shares_cents: int
    cash_cents: int
    other_cents: int  # family office, public holdings and angel stakes at value
    estate_cents: int
    taxable_cents: int
    tax_cents: int
    shares_to_sell: int
    family_bp_now: int
    family_bp_after: int
    trust_shares: int


def quote(
    state: GameState,
    person_id: int,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> EstateQuote:
    person = state.person(person_id)
    r = rule(balance, person.region, state.turn)
    region = balance.estate_tax[person.region]
    family = state.family
    gifts = family.lifetime_gifts_cents if family is not None else 0
    used = min(r.exemption_cents, gifts) if region.gift_tax else 0
    cid = listed_id(state)
    held = person_shares(state, cid, person_id)
    price = share_price(state, cid, balances, balance, data)
    books = book_balances(state.personal_book, person_id)
    cash = books.get(PERSONAL_CASH, 0)
    other = books.get(FAMILY_OFFICE, 0)
    other += sum(
        h.shares * share_price(state, h.company_id, balances, balance, data)
        for h in state.public_holdings
        if h.person_id == person_id and h.shares > 0
    )
    other += sum(
        stake_value_cents(s)
        for s in state.angel_stakes
        if s.person_id == person_id and s.status == "open"
    )
    estate = held * price + cash + other
    taxable = max(0, estate - (r.exemption_cents - used))
    tax = round(Fraction(taxable) * Fraction(r.rate).limit_denominator(RATE_STEPS))
    due = max(0, tax - cash)
    sell = min(held, math.ceil(due / price)) if due else 0
    now = rules.family_bp(state, cid)
    fd = fd_shares(state, cid)
    after = now - (int(Fraction(sell * 10_000, fd)) if fd else 0)  # tunable-exempt: bp
    trust = sum(
        e.shares
        for e in state.company_cap(cid)
        if e.holder_kind == "group" and e.name == TRUST_HOLDER
    )
    return EstateQuote(
        region=person.region,
        rate=r.rate,
        exemption_cents=r.exemption_cents,
        used_exemption_cents=used,
        shares=held,
        share_price_cents=price,
        shares_cents=held * price,
        cash_cents=cash,
        other_cents=other,
        estate_cents=estate,
        taxable_cents=taxable,
        tax_cents=tax,
        shares_to_sell=sell,
        family_bp_now=now,
        family_bp_after=max(0, after),
        trust_shares=trust,
    )


def settle(
    state: GameState,
    old_id: int,
    heir_id: int,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    """The estate at a health succession (45.6): the tax from cash, then share sales; the
    rest passes to the heir."""
    q = quote(state, old_id, balances, balance, data)
    cid = listed_id(state)
    pay_cash = min(q.cash_cents, q.tax_cents)
    state = post(
        state, old_id, "Estate tax", ESTATE_SOURCE, PERSONAL_SPENDING, PERSONAL_CASH, pay_cash
    )
    if q.shares_to_sell:
        holder = PUBLIC_HOLDERS if public_of(state, cid) is not None else ESTATE_BUYERS
        state = move_person_shares(state, cid, old_id, q.shares_to_sell, to_group=holder)
        proceeds = q.shares_to_sell * q.share_price_cents
        state = post(
            state,
            old_id,
            "Estate share sale",
            ESTATE_SOURCE,
            PERSONAL_CASH,
            PERSONAL_INCOME,
            proceeds,
        )
        rest = min(q.tax_cents - pay_cash, proceeds)
        state = post(
            state, old_id, "Estate tax", ESTATE_SOURCE, PERSONAL_SPENDING, PERSONAL_CASH, rest
        )
    state = pass_estate(state, old_id, heir_id)
    family = state.family
    assert family is not None
    family = replace(family, estate_tax_cents=family.estate_tax_cents + q.tax_cents)
    family = rules.note(
        family,
        state.turn,
        "estate_tax",
        f"The estate paid ${q.tax_cents / 100:,.0f} in estate tax"  # tunable-exempt: cents
        + (f" and sold {q.shares_to_sell:,} shares" if q.shares_to_sell else ""),
        balance.family.history,
    )
    state = rules.check_control(with_family(state, family), balance)
    log = inbox_item(
        state.turn,
        state.player.id,
        "estate_settled",
        tax_cents=q.tax_cents,
        shares=f"{q.shares_to_sell:,}",
    )
    return state, [log]


def pass_estate(state: GameState, old_id: int, heir_id: int) -> GameState:
    """Everything the old head holds passes to the heir: shares in every company, personal
    cash, the family office, public holdings, angel stakes and the foundation."""
    memo = "Inheritance"
    for company in state.companies:
        held = person_shares(state, company.id, old_id)
        if held > 0:
            state = move_person_shares(state, company.id, old_id, held, to_person=heir_id)
    books = book_balances(state.personal_book, old_id)
    for account in (PERSONAL_CASH, FAMILY_OFFICE, ENDOWMENT):
        state = move_book(
            state, old_id, heir_id, account, books.get(account, 0), memo, ESTATE_SOURCE
        )
    public_cost = 0
    for h in [h for h in state.public_holdings if h.person_id == old_id]:
        state = replace(
            state, public_holdings=tuple(x for x in state.public_holdings if x is not h)
        )
        state = with_public_holding(state, replace(h, person_id=heir_id))
        public_cost += h.cost_cents
    state = move_book(state, old_id, heir_id, PUBLIC_SHARES, public_cost, memo, ESTATE_SOURCE)
    angel_cost = 0
    for s in [s for s in state.angel_stakes if s.person_id == old_id and s.status == "open"]:
        state = with_angel_stake(state, replace(s, person_id=heir_id))
        angel_cost += s.cost_cents
    state = move_book(state, old_id, heir_id, ANGEL, angel_cost, memo, ESTATE_SOURCE)
    state = replace(
        state,
        family_offices=tuple(
            replace(f, person_id=heir_id) if f.person_id == old_id else f
            for f in state.family_offices
        ),
        personal_stakes=tuple(
            replace(p, person_id=heir_id) if p.person_id == old_id else p
            for p in state.personal_stakes
        ),
    )
    if foundation_of(state, old_id) is not None:
        moved = (
            replace(f, person_id=heir_id) if f.person_id == old_id else f for f in state.foundations
        )
        state = replace(state, foundations=tuple(sorted(moved, key=lambda f: f.person_id)))
    return state


# --- Planning in life (one-offs) -----------------------------------------------------------


def gift_tax(state: GameState, value: int, balance: Balance) -> int:
    """45.6: gift tax on the part of `value` above what is left of the lifetime exemption."""
    family = state.family
    assert family is not None
    person = state.person(family.head_id)
    region = balance.estate_tax[person.region]
    if not region.gift_tax:
        return 0
    r = rule(balance, person.region, state.turn)
    before = max(0, family.lifetime_gifts_cents - r.exemption_cents)
    after = max(0, family.lifetime_gifts_cents + value - r.exemption_cents)
    return round(
        Fraction(after - before) * Fraction(r.rate).limit_denominator(RATE_STEPS)
    )  # tunable-exempt


def _check_shares(state: GameState, person_id: int, shares: int) -> int:
    cid = listed_id(state)
    if shares <= 0:
        raise InvalidActionError("choose a positive number of shares")
    held = person_shares(state, cid, person_id)
    if shares > held:
        raise InvalidActionError(f"you hold {held:,} shares")
    return cid


def gift_shares(
    state: GameState,
    heir_id: int,
    shares: int,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, LogItem]:
    family = state.family
    if family is None:
        raise InvalidActionError("there is no family")
    member = next((m for m in rules.children(state) if m.person_id == heir_id), None)
    if member is None:
        raise InvalidActionError(f"person {heir_id} is not one of your children")
    head = family.head_id
    cid = _check_shares(state, head, shares)
    value = shares * share_price(state, cid, balances, balance, data)
    tax = gift_tax(state, value, balance)
    if tax > cash_cents(state, head):
        raise InvalidActionError(
            f"the gift tax of ${tax / 100:,.0f} needs more personal cash"
        )  # tunable-exempt: cents
    state = move_person_shares(state, cid, head, shares, to_person=heir_id)
    state = post(state, head, "Gift tax", "gift_tax", PERSONAL_SPENDING, PERSONAL_CASH, tax)
    family = state.family
    assert family is not None
    name = rules.full_name(state.person(heir_id))
    family = replace(
        family,
        lifetime_gifts_cents=family.lifetime_gifts_cents + value,
        gift_tax_cents=family.gift_tax_cents + tax,
    )
    family = rules.note(
        family, state.turn, "gift", f"Gave {shares:,} shares to {name}", balance.family.history
    )
    state = with_family(state, family)
    log = inbox_item(
        state.turn, state.player.id, "family_gift", name=name, shares=f"{shares:,}", tax_cents=tax
    )
    return state, log


def fund_trust(state: GameState, shares: int, balance: Balance) -> tuple[GameState, LogItem]:
    """45.6: shares into the family trust (set up the first time at family.trust_setup_cents)."""
    family = state.family
    if family is None:
        raise InvalidActionError("there is no family")
    head = family.head_id
    cid = _check_shares(state, head, shares)
    cost = balance.family.trust_setup_cents if family.trust_turn is None else 0
    if cost > cash_cents(state, head):
        raise InvalidActionError("setting up a trust needs more personal cash for the legal fees")
    state = post(
        state, head, "Family trust set-up", "trust", PERSONAL_SPENDING, PERSONAL_CASH, cost
    )
    state = move_person_shares(state, cid, head, shares, to_group=TRUST_HOLDER)
    family = state.family
    assert family is not None
    family = replace(
        family, trust_turn=family.trust_turn if family.trust_turn is not None else state.turn
    )
    family = rules.note(
        family,
        state.turn,
        "trust",
        f"Put {shares:,} shares in the family trust",
        balance.family.history,
    )
    state = with_family(state, family)
    log = inbox_item(
        state.turn, state.player.id, "family_trust", shares=f"{shares:,}", cost_cents=cost
    )
    return state, log


def give_to_foundation(
    state: GameState,
    shares: int,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, LogItem]:
    """45.6 (32.3): shares given to the foundation leave the estate and count toward legacy."""
    family = state.family
    if family is None:
        raise InvalidActionError("there is no family")
    head = family.head_id
    foundation = foundation_of(state, head)
    if foundation is None:
        raise InvalidActionError("create a foundation first")
    cid = _check_shares(state, head, shares)
    value = shares * share_price(state, cid, balances, balance, data)
    state = move_person_shares(state, cid, head, shares, to_group=FOUNDATION_HOLDER)
    state = replace(
        state,
        foundations=tuple(
            replace(f, gifts_cents=f.gifts_cents + value) if f.person_id == head else f
            for f in state.foundations
        ),
    )
    family = state.family
    assert family is not None
    family = replace(family, foundation_share_cents=family.foundation_share_cents + value)
    family = rules.note(
        family,
        state.turn,
        "foundation",
        f"Gave {shares:,} shares to the foundation",
        balance.family.history,
    )
    state = rules.check_control(with_family(state, family), balance)
    log = inbox_item(
        state.turn,
        state.player.id,
        "family_foundation_shares",
        shares=f"{shares:,}",
        value_cents=value,
    )
    return state, log
