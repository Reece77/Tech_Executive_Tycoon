"""Estate planning and estate tax (docs/formulas.md 45.6). Public rules only: the home
region's rate above its exemption (estate_tax.<region>, by year from the M36 dossier), gift
tax on lifetime gifts above the same exemption where the region has one, a family trust that
holds shares outside the estate (the head still votes them), and shares given to the
foundation. At a health succession the estate pays its whole tax by realising its taxable
assets in a fixed order (M36r, Codex review 7 finding 5): personal cash, the family office,
public holdings (at their share prices), angel stakes (sold at their last-round value), then
the head's shares in the listed (or operating) company. Only what is paid is recorded, and
what is left passes to the heir."""

from __future__ import annotations

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
from tst.sim.founder.investing_models import AngelStake, PublicHolding
from tst.sim.founder.models import (
    ANGEL,
    ENDOWMENT,
    FAMILY_OFFICE,
    GAINS,
    LOSSES,
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
        for h in _holdings(state, person_id, cid)
    )
    other += sum(stake_value_cents(s) for s in _stakes(state, person_id))
    estate = held * price + cash + other
    taxable = max(0, estate - (r.exemption_cents - used))
    tax = round(Fraction(taxable) * Fraction(r.rate).limit_denominator(RATE_STEPS))
    due = max(0, tax - cash - other)  # M36r: the company's shares are sold last
    sell = min(held, _ceil(due, price)) if due else 0
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


def _ceil(cents: int, price: int) -> int:
    """Shares at `price` that raise at least `cents` (exact integer ceiling)."""
    return -(-cents // price)


def _holdings(state: GameState, person_id: int, cid: int) -> list[PublicHolding]:
    """The person's public holdings in the estate, by company. Shares bought in the listed
    company itself are already in the head's cap-table shares (37.3), so not counted again."""
    return sorted(
        (
            h
            for h in state.public_holdings
            if h.person_id == person_id and h.shares > 0 and h.company_id != cid
        ),
        key=lambda h: h.company_id,
    )


def _stakes(state: GameState, person_id: int) -> list[AngelStake]:
    return sorted(
        (s for s in state.angel_stakes if s.person_id == person_id and s.status == "open"),
        key=lambda s: s.id,
    )


def _gain(state: GameState, person_id: int, memo: str, proceeds: int, basis: int) -> GameState:
    """A sale's proceeds over (or under) its book cost: 9410 or 9420."""
    gain = proceeds - basis
    if gain > 0:
        return post(state, person_id, memo, ESTATE_SOURCE, PERSONAL_CASH, GAINS, gain)
    return post(state, person_id, memo, ESTATE_SOURCE, LOSSES, PERSONAL_CASH, -gain)


def _realise(
    state: GameState,
    old_id: int,
    q: EstateQuote,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, int]:
    """45.6 (M36r): the estate raises its tax in a fixed order and pays it as it goes:
    personal cash, the family office, public holdings, angel stakes, then the company's
    shares. Returns the state and the tax actually paid (every posting balances)."""
    cid = listed_id(state)
    left = q.tax_cents
    paid = 0

    def pay(state: GameState, cents: int) -> GameState:
        nonlocal left, paid
        cents = min(cents, left)
        left -= cents
        paid += cents
        return post(
            state, old_id, "Estate tax", ESTATE_SOURCE, PERSONAL_SPENDING, PERSONAL_CASH, cents
        )

    state = pay(state, q.cash_cents)
    office = book_balances(state.personal_book, old_id).get(FAMILY_OFFICE, 0)
    if left > 0 and office > 0:
        drawn = min(office, left)
        memo = "Estate: family office drawn"
        state = post(state, old_id, memo, ESTATE_SOURCE, PERSONAL_CASH, FAMILY_OFFICE, drawn)
        state = pay(state, drawn)
    for h in _holdings(state, old_id, cid):
        if left <= 0:
            break
        price = share_price(state, h.company_id, balances, balance, data)
        sold = min(h.shares, _ceil(left, price))
        basis = int(Fraction(h.cost_cents * sold, h.shares))
        state = with_public_holding(
            state, replace(h, shares=h.shares - sold, cost_cents=h.cost_cents - basis)
        )
        memo = f"Estate sale: {sold:,} {state.company(h.company_id).name} shares"
        state = post(state, old_id, memo, ESTATE_SOURCE, PERSONAL_CASH, PUBLIC_SHARES, basis)
        state = _gain(state, old_id, memo, sold * price, basis)
        state = pay(state, sold * price)
    for s in _stakes(state, old_id):
        if left <= 0:
            break
        value = stake_value_cents(s)
        memo = f"Estate sale: stake in {state.company(s.company_id).name}"
        state = post(state, old_id, memo, ESTATE_SOURCE, PERSONAL_CASH, ANGEL, s.cost_cents)
        state = _gain(state, old_id, memo, value, s.cost_cents)
        state = with_angel_stake(
            state, replace(s, status="sold", closed_turn=state.turn, proceeds_cents=value)
        )
        state = pay(state, value)
    if left > 0 and q.shares_to_sell:
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
        state = pay(state, proceeds)
    return state, paid


def settle(
    state: GameState,
    old_id: int,
    heir_id: int,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    """The estate at a health succession (45.6): the tax raised in `_realise`'s order and
    paid; the rest passes to the heir. The cumulative estate tax records what was paid."""
    q = quote(state, old_id, balances, balance, data)
    state, paid = _realise(state, old_id, q, balances, balance, data)
    state = pass_estate(state, old_id, heir_id)
    family = state.family
    assert family is not None
    family = replace(family, estate_tax_cents=family.estate_tax_cents + paid)
    family = rules.note(
        family,
        state.turn,
        "estate_tax",
        f"The estate paid ${paid / 100:,.0f} in estate tax"  # tunable-exempt: cents
        + (f" and sold {q.shares_to_sell:,} shares" if q.shares_to_sell else ""),
        balance.family.history,
    )
    state = rules.check_control(with_family(state, family), balance)
    log = inbox_item(
        state.turn,
        state.player.id,
        "estate_settled",
        tax_cents=paid,
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
