"""Eligibility and the IPO chain (docs/formulas.md 25.1, 25.2, 25.7).

The chain is an event chain (16): hiring the banks is an immediate action; the S-1, the
roadshow's three events and the pricing critical event are `public` templates the engine
queues. Each choice carries a `public_step` effect that `apply_step` applies. The monthly
phase (`chain_month`, phase 7) draws the book demand on stream `ipo` and lists the company
once the price is set.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import QueuedEvent
from tst.sim.finance.board import _add_seat, average_confidence
from tst.sim.finance.captable import fd_shares, person_shares
from tst.sim.finance.models import CapEntry
from tst.sim.ledger import CASH, COMMON_EQUITY, GENERAL_ADMIN, PREFERRED_EQUITY, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.markets_public import formulas as pf
from tst.sim.markets_public.models import Analyst, Listing, PublicCompany, ShareMonth
from tst.sim.markets_public.value import MONTHS_A_YEAR, Fundamentals, growth_of
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    listing_of,
    public_of,
    reach_stage,
    with_cap_entry,
    with_company,
    with_listing,
    with_public,
    with_queued,
    with_seat,
    with_share_month,
)

PUBLIC_HOLDERS = "Public shareholders"
MILLION = 1_000_000  # tunable-exempt: unit for words
LISTED_STAGE = 4  # tunable-exempt: the spec's stage 4, public company (3)
QUARTERS = 4  # tunable-exempt: quarters in the trailing year (25.1)
QUARTER_MONTHS = 3  # tunable-exempt: calendar

# Templates (data/events/public.yaml)
FILING = "ipo_filing"
ROADSHOW_AMBITION = "ipo_roadshow_ambition"
ROADSHOW_SHARE = "ipo_roadshow_share"
ROADSHOW_CLASS = "ipo_roadshow_class"
PRICING = "ipo_pricing"
PRICING_STRONG = "ipo_pricing_strong"


# --- Eligibility (25.1) --------------------------------------------------------------------


def eligibility_problem(state: GameState, company_id: int, balance: Balance) -> str | None:
    """Why the company cannot hire banks now, or None (25.1)."""
    ib = balance.ipo
    company = state.company(company_id)
    if public_of(state, company_id) is not None:
        return "the company is already listed"
    listing = listing_of(state, company_id)
    if listing is not None and listing.active:
        return "the IPO is already under way"
    if (
        listing is not None
        and listing.pulled_turn is not None
        and state.turn < listing.pulled_turn + ib.retry_months
    ):
        return (
            f"the banks will not return until {format_turn(listing.pulled_turn + ib.retry_months)}"
        )
    if company.stage < ib.min_stage:
        return f"an IPO needs stage {ib.min_stage} (scale-up)"
    mrr = company.mrr_history[-1] if company.mrr_history else 0
    if mrr * MONTHS_A_YEAR < ib.min_arr_cents:
        return f"an IPO needs ${ib.min_arr_cents / pf.PCT / MILLION:,.0f}M of ARR"
    if not (
        profitable_quarters(company.op_history, ib.trailing_months)
        or trailing_growth(company) >= ib.min_growth
    ):
        return (
            "an IPO needs the last 4 quarters profitable at the operating line, or revenue "
            f"growing {ib.min_growth:.0%} a year"
        )
    confidence = average_confidence(state, company_id)
    if confidence is not None and confidence < ib.board_min_confidence:
        return f"the board will not approve an IPO below {ib.board_min_confidence:.0f} confidence"
    return None


def profitable_quarters(op_history: tuple[int, ...], months: int) -> bool:
    """Each of the last 4 quarters at or above zero at the operating line (25.1)."""
    if len(op_history) < months:
        return False
    recent = op_history[-months:]
    step = months // QUARTERS
    return all(sum(recent[i : i + step]) >= 0 for i in range(0, months, step))


def trailing_growth(company: CompanyState) -> float:
    """Revenue growth over the year to the last month end (25.1)."""
    history = company.mrr_history
    if not history:
        return 0.0
    return growth_of(replace(company, mrr_history=history[:-1]), history[-1])


# --- Helpers -------------------------------------------------------------------------------


def queue_public(state: GameState, company_id: int, template_id: str, due_turn: int) -> GameState:
    """Queue a `public` template for the player (the director shows it in `due_turn`)."""
    qid, ids = state.next_ids.take("queued")
    return with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=qid,
            company_id=company_id,
            template_id=template_id,
            due_turn=due_turn,
            source_event_id=None,
        ),
    )


def ticker_for(name: str, length: int) -> str:
    letters = [c for c in name.upper() if c.isalpha()]
    return "".join(letters[:length]) or "TST"


def hire_banks(
    state: GameState, company_id: int, bank: str, balance: Balance, data: GameData
) -> GameState:
    """25.2 step 1 (the action's rules; energy is spent by the caller)."""
    data.bank(bank)  # KeyError for an unknown bank
    listing = Listing(company_id=company_id, bank=bank, hired_turn=state.turn, status="filing")
    state = with_listing(state, listing)
    return queue_public(state, company_id, FILING, state.turn + 1)


# --- Event choices (25.2 steps 2-4) ----------------------------------------------------------


def apply_ipo_step(
    state: GameState, company_id: int, step: str, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """One IPO choice. Steps that do not fit the chain's state change nothing."""
    ib = balance.ipo
    listing = listing_of(state, company_id)
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    if listing is None or not listing.active:
        return state, entries, logs
    turn = state.turn
    if step in ("file", "file_late") and listing.status == "filing":
        late = step == "file_late"
        due = turn + 1 + (ib.filing_delay_months if late else 0)
        listing = replace(listing, status="roadshow", filed_late=late, roadshow_turn=due)
        state = with_listing(state, listing)
        state = queue_public(state, company_id, ROADSHOW_AMBITION, due)
        state = queue_public(state, company_id, ROADSHOW_SHARE, due)
        return state, entries, logs
    if listing.status == "roadshow":
        before = listing
        if step.startswith("ambition_"):
            listing = replace(listing, ambition=step.removeprefix("ambition_"))
        elif step.startswith("sell_"):
            listing = replace(listing, share_choice=step.removeprefix("sell_"))
        elif step in ("single_class", "dual_class"):
            listing = replace(listing, dual_class=step == "dual_class")
        state = with_listing(state, listing)
        both = listing.ambition is not None and listing.share_choice is not None
        if both and (before.ambition is None or before.share_choice is None):
            state = queue_public(state, company_id, ROADSHOW_CLASS, turn + 1)
        return state, entries, logs
    if listing.status == "pricing" and step.startswith("price_"):
        choice = step.removeprefix("price_")
        if choice == "raise" and (listing.demand or 0) < ib.raise_min_demand:
            choice = "range"  # only with strong demand (25.2 step 4)
        factor = {"range": 1.0, "raise": 1 + ib.raise_pct, "cut": 1 - ib.cut_pct}[choice]
        listing = replace(
            listing,
            status="priced",
            price_choice=choice,  # type: ignore[arg-type]
            price_cents=max(1, round(listing.price_cents * factor)),
        )
        return with_listing(state, listing), entries, logs
    if listing.status == "pricing" and step == "pull":
        bank = data.bank(listing.bank)
        expected = listing.price_cents * listing.new_shares
        fee = round(pf.fee_cents(expected, bank.fee) * ib.pull_fee_share)
        if fee > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=turn,
                    company_id=company_id,
                    memo=f"IPO pulled: {bank.name}'s fees",
                    debit=GENERAL_ADMIN,
                    credit=CASH,
                    amount=fee,
                )
            )
        for seat in state.board(company_id):
            if seat.confidence is not None:
                value = max(0.0, min(float(pf.PCT), seat.confidence + ib.pull_confidence))
                state = with_seat(state, replace(seat, confidence=value))
        state = with_listing(state, replace(listing, status="pulled", pulled_turn=turn))
        logs.append(inbox_item(turn, company_id, "ipo_pulled", bank=bank.name, fee_cents=fee))
    return state, entries, logs


# --- Phase 7: demand and the listing (25.2 steps 4-5) ------------------------------------------


def draw_demand(
    rng: RngFactory, turn: int, company_id: int, climate: float, balance: Balance
) -> float:
    """d on stream `ipo`, key (company_id,) (25.2 step 4). Hidden (25.8)."""
    z = float(rng.stream(turn, "ipo", company_id).standard_normal())
    return pf.book_demand(z, climate, balance.ipo.demand)


def open_pricing(
    state: GameState,
    company_id: int,
    f: Fundamentals,
    demand: float,
    balance: Balance,
    data: GameData,
) -> GameState:
    """The roadshow is done: the bank's suggested price and the pricing critical event."""
    ib = balance.ipo
    listing = listing_of(state, company_id)
    assert listing is not None and listing.ambition and listing.share_choice
    bank = data.bank(listing.bank)
    shares = f.shares
    new = pf.new_shares(shares, ib.share_sold[listing.share_choice])
    price = pf.offer_price_cents(
        f.value_cents,
        shares + new,
        bank.quality,
        ib.ambition[listing.ambition],
        ib.dual_class_discount if listing.dual_class else 0.0,
    )
    listing = replace(
        listing,
        status="pricing",
        demand=demand,
        shares_before=shares,
        new_shares=new,
        price_cents=max(1, price),
    )
    state = with_listing(state, listing)
    template = PRICING_STRONG if demand >= ib.raise_min_demand else PRICING
    return queue_public(state, company_id, template, state.turn + 1)


def list_company(
    state: GameState,
    company_id: int,
    f: Fundamentals,
    gen: np.random.Generator,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    preferred_cents: int = 0,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Listing day (25.2 step 5, 25.7): new shares, the net raise, stage 4, the public board,
    the first day's close, and analysts' first targets (from `gen`, stream market_sentiment).

    M15b (an M13 follow-up): every preferred share and converted SAFE becomes common, as it
    does at a real IPO; `preferred_cents` (the preferred equity account's credit balance)
    moves to common equity with it."""
    ib, pb = balance.ipo, balance.public
    listing = listing_of(state, company_id)
    assert listing is not None and listing.status == "priced"
    turn = state.turn
    bank = data.bank(listing.bank)
    gross = listing.price_cents * listing.new_shares
    fee = pf.fee_cents(gross, bank.fee)
    entries = [
        LedgerEntry.transfer(
            turn=turn,
            company_id=company_id,
            memo=(
                f"IPO: {listing.new_shares:,} new shares at "
                f"${listing.price_cents / pf.PCT:,.2f}, net of {bank.name}'s fee"
            ),
            debit=CASH,
            credit=COMMON_EQUITY,
            amount=gross - fee,
        )
    ]
    for held in state.cap_entries:
        if held.company_id == company_id and held.share_class != "common":
            state = with_cap_entry(state, replace(held, share_class="common"))
    if preferred_cents > 0:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=company_id,
                memo="IPO: preferred shares convert to common",
                debit=PREFERRED_EQUITY,
                credit=COMMON_EQUITY,
                amount=preferred_cents,
            )
        )
    entry_id, ids = state.next_ids.take("cap_entry")
    state = with_cap_entry(
        replace(state, next_ids=ids),
        CapEntry(
            id=entry_id,
            company_id=company_id,
            holder_kind="group",
            share_class="common",
            shares=listing.new_shares,
            acquired_turn=turn,
            name=PUBLIC_HOLDERS,
        ),
    )
    # a = the final price over the fair price per share, before the dual-class discount
    fair = pf.per_share_cents(f.value_cents, listing.shares_before + listing.new_shares)
    discount = 1 - (ib.dual_class_discount if listing.dual_class else 0.0)
    ambition = listing.price_cents / (fair * discount) if fair > 0 else 1.0
    r = pf.first_day_return(listing.demand or 1.0, ambition, ib.first_day)
    close = max(1, round(listing.price_cents * (1 + r)))
    shares = fd_shares(state, company_id)
    company = state.company(company_id)
    ticker = ticker_for(company.name, ib.ticker_len)
    listing = replace(
        listing,
        status="listed",
        gross_cents=gross,
        fee_cents=fee,
        first_day_return=r,
        close_cents=close,
        listed_turn=turn,
        ticker=ticker,
    )
    state = with_listing(state, listing)
    value = pf.fundamental_value_cents(f.arr_cents, f.multiple)
    per_share = pf.per_share_cents(value, shares)
    sentiment = pb.sentiment.bounds.clamp(close / per_share if per_share > 0 else 1.0)
    analysts = first_analysts(close * shares, per_share, close, gen, balance)
    public = PublicCompany(
        company_id=company_id,
        listed_turn=turn,
        ticker=ticker,
        dual_class=bool(listing.dual_class),
        listing_price_cents=listing.price_cents,
        price_cents=close,
        sentiment=sentiment,
        value_cents=value,
        analysts=analysts,
    )
    state = with_public(state, public)
    state = with_share_month(state, ShareMonth(company_id, turn, close, shares, "listing"))
    state = with_company(state, reach_stage(company, LISTED_STAGE, turn))
    for _ in range(ib.independents):  # 25.7: two independent directors (a full board takes none)
        state = _add_seat(state, company_id, "independent", rng, balance, data, round_id=None)
    founder = state.founder_of(company_id)
    stake = person_shares(state, company_id, founder.id) if founder else 0
    logs = [
        inbox_item(
            turn,
            company_id,
            "ipo_listed",
            ticker=ticker,
            bank=bank.name,
            price_cents=listing.price_cents,
            close_cents=close,
            pop=f"{r:+.0%}",
            gross_cents=gross,
            net_cents=gross - fee,
            stake_cents=stake * close,
        )
    ]
    return state, entries, logs


def first_analysts(
    cap_cents: int, per_share: int, price: int, gen: np.random.Generator, balance: Balance
) -> tuple[Analyst, ...]:
    """Analysts' targets V_f per share x (1 + N(0, 0.1)) and ratings from target / P (25.3)."""
    ab = balance.public.analysts
    out = []
    for i in range(pf.analyst_count(cap_cents, ab)):
        target = max(1, round(per_share * (1 + ab.target_sd * float(gen.standard_normal()))))
        out.append(Analyst(i, target, pf.rating(target, price, ab)))
    return tuple(out)


def roadshow_done(listing: Listing) -> bool:
    return (
        listing.status == "roadshow"
        and listing.ambition is not None
        and listing.share_choice is not None
        and listing.dual_class is not None
    )


def quarter_start(turn: int) -> int:
    return turn - turn % QUARTER_MONTHS
