"""Diligence, offers and closing (docs/formulas.md 28.2-28.3, M14 sub-task 3).

Every draw is on stream `mna` keyed by the target's stable rival key (ADR-0013) and a tag,
so no other draw moves when a company looks at, bids for or buys another. Hidden values (a
reservation, a board's bar, a tender's chance, a problem before diligence or closing) never
appear in an error or a message (28.8): a refused offer says only that it was refused."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import MnaRuleError
from tst.sim.ledger import (
    CASH,
    COMMON_EQUITY,
    GENERAL_ADMIN,
    GOODWILL,
    INVESTMENT_SUBSIDIARIES,
    LedgerBalances,
    LedgerEntry,
    LedgerLine,
    account_balance,
)
from tst.sim.log import LogItem, inbox_item
from tst.sim.mna import formulas as mf
from tst.sim.mna import valuation
from tst.sim.mna.draws import fixed_draws, mna_draws
from tst.sim.mna.models import OPEN_DEALS, PROBLEMS, Deal, Mode, Problem, TargetFile
from tst.sim.money import format_money
from tst.sim.rivals.models import stream_key
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    public_of,
    target_file,
    with_deal,
    with_target_file,
)

PROBLEM_TAG, COUNTER_TAG, BOARD_TAG, TENDER_TAG = 1, 2, 3, 4  # tunable-exempt: stream sub-keys
REVIEW_TAG = 5  # tunable-exempt: stream sub-key (28.4)
BALANCE_SHEET = ("asset", "liability")

type OfferResult = Literal["accepted", "countered", "rejected", "talks_ended", "tender_failed"]


@dataclass(frozen=True, slots=True)
class StartDiligence:
    """Immediate, energy 6: two months of diligence on a target (28.2)."""

    actor_id: int
    target_id: int
    kind: Literal["start_diligence"] = "start_diligence"


@dataclass(frozen=True, slots=True)
class BidForCompany:
    """Immediate, energy 10 (a hostile tender 15): a price, in cash or (once listed) the
    acquirer's new shares or a mix, and what to do at closing (28.3, 28.5)."""

    actor_id: int
    target_id: int
    price_cents: int
    cash_share: float = 1.0
    hostile: bool = False
    mode: Mode = "integrate"
    kind: Literal["bid_for_company"] = "bid_for_company"


@dataclass(frozen=True, slots=True)
class SetDealMode:
    """Brand or integrate, until the deal closes (28.5; M14 decision: chosen with the offer
    and final at closing)."""

    actor_id: int
    deal_id: int
    mode: Mode
    kind: Literal["set_deal_mode"] = "set_deal_mode"


@dataclass(frozen=True, slots=True)
class AbandonDeal:
    """Walk away from a deal before it closes, for its fees only (28.4)."""

    actor_id: int
    deal_id: int
    kind: Literal["abandon_deal"] = "abandon_deal"


@dataclass(frozen=True, slots=True)
class DealOutcome:
    state: GameState
    entries: tuple[LedgerEntry, ...] = ()
    logs: tuple[LogItem, ...] = ()
    result: OfferResult | None = None


# --- Keys, files and hidden problems --------------------------------------------------------


def key_of(state: GameState, company_id: int) -> tuple[int, ...]:
    """A company's mna stream key (ADR-0013): a rival's stable key, the player's id."""
    company = state.company(company_id)
    return (company_id,) if company.is_player else stream_key(company_id, company.rival_key)


def problems_of(state: GameState, target_id: int, balance: Balance) -> tuple[Problem, ...]:
    """The target's hidden problems (28.2): each with probability mna.problems.p, fixed per
    target (stream mna at turn 0, its stable key), so looking twice never redraws them."""
    gen = fixed_draws(state.save_meta.master_seed, *key_of(state, target_id), PROBLEM_TAG)
    draws = [float(gen.random()) for _ in PROBLEMS]
    return tuple(p for p, u in zip(PROBLEMS, draws, strict=True) if u < balance.mna.problems.p)


def file_of(state: GameState, acquirer_id: int, target_id: int, balance: Balance) -> TargetFile:
    """The acquirer's file on the target, opened with its hidden problems drawn."""
    found = target_file(state, acquirer_id, target_id)
    if found is not None:
        return found
    return TargetFile(acquirer_id, target_id, problems_of(state, target_id, balance))


def known_problems(state: GameState, acquirer_id: int, target_id: int) -> tuple[Problem, ...]:
    """What the acquirer knows of the target's problems: nothing before diligence (28.8)."""
    found = target_file(state, acquirer_id, target_id)
    return found.problems if found is not None and found.diligenced else ()


def open_deal(state: GameState, target_id: int) -> Deal | None:
    return next(
        (d for d in state.deals if d.target_id == target_id and d.status in OPEN_DEALS), None
    )


# --- Prices -------------------------------------------------------------------------------


def monthly_costs_cents(state: GameState, company_id: int, balance: Balance, data: GameData) -> int:
    from tst.sim.rivals.decisions import monthly_cost_cents

    return monthly_cost_cents(state, company_id, balance, data)


def premium_of(state: GameState, target_id: int, balance: Balance) -> float:
    """p (28.3): a startup's founder by true ambition; otherwise by personality."""
    company = state.company(target_id)
    founder = state.founder_of(target_id)
    if company.is_startup and founder is not None:
        return mf.founder_premium(founder.personality["ambition"], balance.mna)
    return mf.personality_premium(company.personality or "fast_follower", balance.mna)


def reservation_cents(
    state: GameState, target_id: int, balances: LedgerBalances, balance: Balance, data: GameData
) -> int:
    """The lowest price a private target accepts (28.3). Hidden (28.8)."""
    value = valuation.fundamental_value_cents(state, target_id, balances, balance, data)
    cash = account_balance(balances, target_id, CASH)
    costs = monthly_costs_cents(state, target_id, balance, data)
    distressed = mf.distressed(cash, costs, balance.mna)
    return mf.reservation_cents(
        value, premium_of(state, target_id, balance), distressed, balance.mna
    )


def estimate_cents(
    state: GameState,
    acquirer_id: int,
    target_id: int,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> int:
    """What the acquirer sees a target as worth (28.1): a listed one's market cap, else the
    midpoint of its displayed range (narrower after diligence)."""
    cap = valuation.market_cap_cents(state, target_id, balances, balance, data)
    if cap is not None:
        return cap
    found = target_file(state, acquirer_id, target_id)
    diligenced = found is not None and found.diligenced
    return mf.midpoint_cents(
        valuation.value_range_cents(
            state, target_id, balances, balance, data, diligenced=diligenced
        )
    )


# --- Checks -------------------------------------------------------------------------------


def _target(state: GameState, acquirer_id: int, target_id: int) -> None:
    if target_id == acquirer_id:
        raise MnaRuleError("a company cannot buy itself")
    try:
        company = state.company(target_id)
    except KeyError as exc:
        raise MnaRuleError(f"there is no company {target_id}") from exc
    if company.is_player:
        raise MnaRuleError("that is the player's company")
    if not company.alive:
        raise MnaRuleError(f"{company.name} is no longer in business")
    if company.parent_id is not None:
        owner = state.company(company.parent_id).name
        raise MnaRuleError(f"{company.name} is already owned by {owner}")


# --- Diligence (28.2) ---------------------------------------------------------------------


def start_diligence(
    state: GameState,
    action: StartDiligence,
    acquirer_id: int,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
    spend: Callable[[GameState, int], GameState],
) -> DealOutcome:
    """Immediate, energy 6: 0.5% of the estimated value (at least $50,000) to 6900; the
    findings arrive after mna.diligence.months (28.2)."""
    _target(state, acquirer_id, action.target_id)
    found = file_of(state, acquirer_id, action.target_id, balance)
    if found.diligenced:
        raise MnaRuleError("diligence on this company is already done")
    if found.diligence_turn is not None:
        raise MnaRuleError("diligence on this company is already under way")
    cost = mf.diligence_cost_cents(
        estimate_cents(state, acquirer_id, action.target_id, balances, balance, data), balance.mna
    )
    if account_balance(balances, acquirer_id, CASH) < cost:
        raise MnaRuleError(f"diligence costs {format_money(cost)}; not enough cash")
    state = spend(state, balance.mna.diligence.energy)
    found = replace(found, diligence_turn=state.turn)
    name = state.company(action.target_id).name
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=acquirer_id,
        memo=f"Due diligence: {name}",
        debit=GENERAL_ADMIN,
        credit=CASH,
        amount=cost,
    )
    return DealOutcome(with_target_file(state, found), (entry,))


def diligence_month(state: GameState, balance: Balance) -> tuple[GameState, list[LogItem]]:
    """Phase 7: diligence that has run its months reveals its findings (28.2)."""
    logs: list[LogItem] = []
    months = balance.mna.diligence.months
    for f in state.target_files:
        if f.diligence_turn is None or f.diligenced or state.turn < f.diligence_turn + months - 1:
            continue
        state = with_target_file(state, replace(f, diligence_done_turn=state.turn))
        if not state.company(f.acquirer_id).is_player:
            continue
        name = state.company(f.target_id).name
        found = ", ".join(p.replace("_", " ") for p in f.problems) or "no hidden problems"
        logs.append(
            _update(
                state,
                f.acquirer_id,
                f"Diligence on {name} is done",
                f"The value range narrowed and its people and products are now known as ranges. "
                f"Findings: {found}.",
                f.target_id,
            )
        )
    return state, logs


# --- Offers (28.3) ------------------------------------------------------------------------


def _validate_offer(
    state: GameState,
    action: BidForCompany,
    acquirer_id: int,
    balances: LedgerBalances,
    data: GameData,
) -> None:
    _target(state, acquirer_id, action.target_id)
    if action.price_cents <= 0:
        raise MnaRuleError("an offer needs a positive price")
    if not 0 <= action.cash_share <= 1:
        raise MnaRuleError("the cash share must be between 0 and 1")
    if open_deal(state, action.target_id) is not None:
        raise MnaRuleError(f"{state.company(action.target_id).name} already has a deal agreed")
    found = target_file(state, acquirer_id, action.target_id)
    if found is not None and found.blocked_until is not None and state.turn < found.blocked_until:
        raise MnaRuleError(
            f"talks with {state.company(action.target_id).name} are closed for now; try again "
            f"in {found.blocked_until - state.turn} months"
        )
    listed = public_of(state, acquirer_id) is not None
    if action.cash_share < 1 and not listed:
        raise MnaRuleError("paying in shares needs the company to be listed")
    cash = account_balance(balances, acquirer_id, CASH)
    cash_part = round(action.price_cents * action.cash_share)
    if cash_part > cash:
        raise MnaRuleError(
            f"the cash part is {format_money(cash_part)}; there is {format_money(cash)} on hand "
            "(take a bank loan first, or pay partly in shares)"
        )
    if action.hostile:
        if not valuation.is_listed(state, action.target_id, data):
            raise MnaRuleError("a hostile tender needs a listed target")
        if not listed and action.price_cents > cash:
            raise MnaRuleError("a hostile tender needs a listing or cash for the whole price")


def make_offer(
    state: GameState,
    action: BidForCompany,
    acquirer_id: int,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
    spend: Callable[[GameState, int], GameState],
) -> DealOutcome:
    """A friendly offer or a hostile tender (28.3). Accepted offers become deals that close
    after antitrust (28.4); the answer names no hidden number."""
    _validate_offer(state, action, acquirer_id, balances, data)
    mb = balance.mna
    state = spend(state, mb.tender.energy if action.hostile else mb.offer_energy)
    target = action.target_id
    name = state.company(target).name
    found = file_of(state, acquirer_id, target, balance)
    key = key_of(state, target)
    price = action.price_cents
    if valuation.is_listed(state, target, data):
        cap = valuation.market_cap_cents(state, target, balances, balance, data) or 0
        premium = mf.premium_over(price, cap)
        if action.hostile:
            u = float(mna_draws(rng, state.turn, *key, TENDER_TAG).random())
            aggressive = state.company(target).personality == "aggressive"
            if u < mf.tender_chance(premium, aggressive, mb.tender):
                return _accept(state, found, action, acquirer_id, rng, balance, data)
            fee = mf.tender_fee_cents(price, mb.tender)
            found = replace(found, blocked_until=state.turn + mb.tender.block_months)
            entry = LedgerEntry.transfer(
                turn=state.turn,
                company_id=acquirer_id,
                memo=f"Failed tender for {name}: fees",
                debit=GENERAL_ADMIN,
                credit=CASH,
                amount=fee,
            )
            log = _update(
                state,
                acquirer_id,
                f"The tender for {name} failed",
                f"Too few shareholders tendered. Fees: {format_money(fee)}; no new bid for "
                f"{mb.tender.block_months} months.",
                target,
            )
            return DealOutcome(with_target_file(state, found), (entry,), (log,), "tender_failed")
        if found.board_bar is None:
            z = float(mna_draws(rng, state.turn, *key, BOARD_TAG).standard_normal())
            found = replace(found, board_bar=mf.board_bar(z, mb))
        assert found.board_bar is not None
        if premium >= found.board_bar:
            return _accept(state, found, action, acquirer_id, rng, balance, data)
        log = _update(
            state,
            acquirer_id,
            f"{name}'s board rejected the offer",
            f"The board said no to {format_money(price)}. You can offer more.",
            target,
        )
        return DealOutcome(with_target_file(state, found), (), (log,), "rejected")
    reservation = reservation_cents(state, target, balances, balance, data)
    bar = reservation if found.counter_cents is None else found.counter_cents  # 28.3
    if price >= bar:
        return _accept(state, found, action, acquirer_id, rng, balance, data)
    if found.counter_cents is None:
        z = float(mna_draws(rng, state.turn, *key, COUNTER_TAG).standard_normal())
        counter = mf.counter_cents(reservation, z, mb)
        found = replace(found, counter_cents=counter)
        log = _update(
            state,
            acquirer_id,
            f"{name} counters at {format_money(counter)}",
            f"{name} turned down {format_money(price)} and would sell for "
            f"{format_money(counter)}. Another offer below that ends talks for "
            f"{mb.talks_block_months} months.",
            target,
        )
        return DealOutcome(with_target_file(state, found), (), (log,), "countered")
    found = replace(found, blocked_until=state.turn + mb.talks_block_months, counter_cents=None)
    log = _update(
        state,
        acquirer_id,
        f"{name} ended talks",
        f"The offer was below their counter. No new offer for {mb.talks_block_months} months.",
        target,
    )
    return DealOutcome(with_target_file(state, found), (), (log,), "talks_ended")


def _accept(
    state: GameState,
    found: TargetFile,
    action: BidForCompany,
    acquirer_id: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> DealOutcome:
    from tst.sim.mna import antitrust

    deal_id, ids = state.next_ids.take("deal")
    state = replace(state, next_ids=ids)
    deal = Deal(
        id=deal_id,
        acquirer_id=acquirer_id,
        target_id=action.target_id,
        price_cents=action.price_cents,
        cash_share=action.cash_share,
        made_turn=state.turn,
        hostile=action.hostile,
        close_turn=state.turn + balance.mna.closing_months,
        mode=action.mode,
    )
    deal, logs = antitrust.screen(state, deal, rng, balance, data)
    found = replace(found, counter_cents=None, board_bar=None)
    state = with_deal(with_target_file(state, found), deal)
    name = state.company(action.target_id).name
    how = "tendered" if action.hostile else "agreed"
    accepted = _update(
        state,
        acquirer_id,
        f"Deal {how}: {name}",
        f"{name} for {format_money(action.price_cents)} "
        f"({action.cash_share:.0%} cash). " + _closing_text(deal),
        action.target_id,
    )
    return DealOutcome(state, (), (accepted, *logs), "accepted")


def _closing_text(deal: Deal) -> str:
    if deal.status == "review":
        return f"Antitrust is reviewing it (combined share {deal.combined_share:.0%})."
    if deal.status == "blocked":
        return (
            f"Antitrust blocks it at {deal.combined_share:.0%} combined share unless you accept "
            "a remedy."
        )
    return "It closes next month."


def set_deal_mode(state: GameState, action: SetDealMode, acquirer_id: int) -> GameState:
    deal = _own_open(state, action.deal_id, acquirer_id)
    return with_deal(state, replace(deal, mode=action.mode))


def abandon_deal(state: GameState, action: AbandonDeal, acquirer_id: int) -> GameState:
    """Walk away before closing: fees only (28.4)."""
    deal = _own_open(state, action.deal_id, acquirer_id)
    return with_deal(state, replace(deal, status="abandoned", resolved_turn=state.turn))


def _own_open(state: GameState, deal_id: int, acquirer_id: int) -> Deal:
    deal = next((d for d in state.deals if d.id == deal_id), None)
    if deal is None or deal.acquirer_id != acquirer_id:
        raise MnaRuleError(f"there is no deal {deal_id}")
    if deal.status not in OPEN_DEALS:
        raise MnaRuleError(f"the deal for {state.company(deal.target_id).name} is {deal.status}")
    return deal


# --- Closing (28.3) -----------------------------------------------------------------------


def net_assets(balances: LedgerBalances, company_id: int, data: GameData) -> list[tuple[str, int]]:
    """The company's balance-sheet accounts with balances (debit positive): its book
    equity is their sum."""
    types = {a.code: a.type for a in data.accounts}
    return [
        (code, account_balance(balances, company_id, code))
        for code in sorted(types)
        if types[code] in BALANCE_SHEET and account_balance(balances, company_id, code) != 0
    ]


def closing_entries(
    state: GameState, deal: Deal, balances: LedgerBalances, data: GameData
) -> tuple[LedgerEntry, ...]:
    """The price, goodwill and the target's books at closing (28.3, 28.5).

    Integrate: the target's assets and liabilities move to the acquirer line by line, the
    price goes out (cash, new shares), and goodwill = price - their sum (the book equity).
    Brand: the target keeps its books; the acquirer holds its book equity in 1810 plus
    goodwill. Either way each entry balances."""
    target, acquirer = deal.target_id, deal.acquirer_id
    name = state.company(target).name
    lines = net_assets(balances, target, data)
    equity = sum(amount for _, amount in lines)
    cash_part = round(deal.price_cents * deal.cash_share)
    stock_part = deal.price_cents - cash_part
    paid = [LedgerLine(CASH, -cash_part), LedgerLine(COMMON_EQUITY, -stock_part)]
    goodwill = LedgerLine(GOODWILL, mf.goodwill_cents(deal.price_cents, equity))
    if deal.mode == "brand":
        acquired = [LedgerLine(INVESTMENT_SUBSIDIARIES, equity)]
    else:
        acquired = [LedgerLine(code, amount) for code, amount in lines]
    entries = [
        LedgerEntry(
            state.turn,
            acquirer,
            f"Acquisition of {name}",
            tuple(x for x in (*acquired, goodwill, *paid) if x.amount != 0)
            or (LedgerLine(CASH, 0), LedgerLine(GOODWILL, 0)),
        )
    ]
    if deal.mode != "brand" and lines:
        entries.append(
            LedgerEntry(
                state.turn,
                target,
                f"Sold to {state.company(acquirer).name}",
                (
                    *(LedgerLine(code, -amount) for code, amount in lines),
                    LedgerLine(COMMON_EQUITY, equity),
                ),
            )
        )
    return tuple(e for e in entries if any(x.amount for x in e.lines))


def issue_shares(state: GameState, deal: Deal) -> GameState:
    """The stock part as new shares at the current price to the target's owners, who join
    the public float (28.3): the cap table still sums to 100%."""
    from tst.sim.finance.models import CapEntry
    from tst.sim.markets_public.capital import _float_entry
    from tst.sim.markets_public.ipo import PUBLIC_HOLDERS
    from tst.sim.state import with_cap_entry

    stock_part = deal.price_cents - round(deal.price_cents * deal.cash_share)
    public = public_of(state, deal.acquirer_id)
    if stock_part <= 0 or public is None or public.price_cents <= 0:
        return state
    shares = max(1, round(stock_part / public.price_cents))
    entry = _float_entry(state, deal.acquirer_id)
    if entry is not None:
        return with_cap_entry(state, replace(entry, shares=entry.shares + shares))
    entry_id, ids = state.next_ids.take("cap_entry")
    return with_cap_entry(
        replace(state, next_ids=ids),
        CapEntry(
            entry_id,
            deal.acquirer_id,
            "group",
            "common",
            shares,
            state.turn,
            name=PUBLIC_HOLDERS,
        ),
    )


def _update(state: GameState, company_id: int, title: str, detail: str, target_id: int) -> LogItem:
    return inbox_item(
        state.turn,
        company_id,
        "deal_update",
        link_kind="rival",
        link_id=target_id,
        title=title,
        detail=detail,
    )
