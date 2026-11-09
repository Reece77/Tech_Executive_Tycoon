"""Public shares with the founder's own money (docs/formulas.md 37.3, M26).

- **Trades** (energy personal.trade_energy) in any listed company at the last month end's
  share price, with personal.trade_cost. A listed rival's price is its market cap over a
  notional personal.rival_shares. Trades never touch the company's books: they are between
  the founder and other holders. In the founder's own listed company the shares move between
  the public float and the founder's cap entry, so dividends (M24) and control follow; a
  holding record keeps the cost of the shares bought.
- **Windows:** own-company trades are refused in the quarter's last month (its earnings
  report lands at that month's end). An own-company sale above personal.filing_share of the
  shares in a month is a public filing (sentiment personal.filing_sentiment, an event).
- **Insider trading:** a trade in a company the player's group is preparing a deal for
  (diligence or a bid, no deal agreed yet), or in the founder's own company while the group
  prepares one, is "in a sensitive window" (shown). If that deal is agreed within
  personal.insider_months, the trade adds hidden regulatory risk and is investigated with
  probability personal.sec_p, opening within personal.investigation_months (stream
  `personal`, key (0, trade id), drawn when the news goes public). A finding follows
  personal.finding_months later: a fine of fine_mult x the gain, the gain disgorged,
  credibility, Reckless, board confidence and the board's vote (14.6's removal rule).
- **Dividends:** a listed rival whose operating result over the last quarter was positive
  pays personal.dividend_yield of its market cap a year, quarterly, on the founder's shares
  (its book pays: Dr common equity Cr cash; the founder's: Dr 9100 Cr 9430).

The regulatory risk, an investigation's draw and its timing never leave the engine (37.7)."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Final, Literal

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.finance.captable import person_shares
from tst.sim.finance.models import CapEntry
from tst.sim.founder import draws
from tst.sim.founder.angel import group_ids
from tst.sim.founder.draws import personal_draws
from tst.sim.founder.events import queue
from tst.sim.founder.investing_models import PersonalTrade, PublicHolding
from tst.sim.founder.models import (
    DIVIDENDS,
    GAINS,
    LOSSES,
    PERSONAL_CASH,
    PERSONAL_SPENDING,
    PUBLIC_SHARES,
)
from tst.sim.founder.personal import cash_cents
from tst.sim.founder.wealth import post, share_price_cents
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerBalances, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.markets_public.ipo import PUBLIC_HOLDERS, QUARTER_MONTHS
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    holding_in,
    listed_id,
    next_record_id,
    public_of,
    with_cap_entry,
    with_public,
    with_public_holding,
    with_trade,
)

FILING_TEMPLATE = "personal_filing"
INVESTIGATION_TEMPLATE = "personal_investigation"
FINDING_TEMPLATE = "personal_finding"
LINK: Final = "rival"


def is_own(state: GameState, company_id: int) -> bool:
    """The founder's own listed company (the holding once formed)."""
    return company_id == listed_id(state) and public_of(state, company_id) is not None


def window_closed(state: GameState) -> bool:
    """Own-company trades are closed in the quarter's last month (37.3)."""
    return state.turn % QUARTER_MONTHS == QUARTER_MONTHS - 1


def preparing(state: GameState) -> set[int]:
    """Targets the player's group is preparing a deal for and has not yet announced: a
    diligence started or a bid made, with no deal agreed since (37.3)."""
    mine = group_ids(state)
    out: set[int] = set()
    for f in state.target_files:
        if f.acquirer_id not in mine or (f.diligence_turn is None and not f.rounds):
            continue
        since = f.diligence_turn if f.diligence_turn is not None else 0
        agreed = any(
            d.acquirer_id == f.acquirer_id and d.target_id == f.target_id and d.made_turn >= since
            for d in state.deals
        )
        if not agreed:
            out.add(f.target_id)
    return out


def sensitive_target(state: GameState, company_id: int) -> int | None:
    """The deal in preparation a trade in `company_id` would be ahead of, if any."""
    targets = preparing(state)
    if company_id in targets:
        return company_id
    if is_own(state, company_id) and targets:
        return min(targets)
    return None


def trade(
    state: GameState,
    person_id: int,
    company_id: int,
    side: Literal["buy", "sell"],
    shares: int,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """37.3: buy or sell `shares` of a listed company at its share price."""
    from tst.sim.mna.valuation import is_listed

    pb = balance.personal
    if shares <= 0:
        raise InvalidActionError("a trade needs a positive number of shares")
    if not is_listed(state, company_id, data):
        raise InvalidActionError("only a listed company's shares trade")
    company = state.company(company_id)
    own = is_own(state, company_id)
    if own and window_closed(state):
        raise InvalidActionError(
            "your own company's shares are closed to you in the month before earnings"
        )
    price = share_price_cents(state, company_id, balances, balance, data)
    assert price is not None
    value = shares * price
    cost = round(value * pb.trade_cost)
    held = holding_in(state, person_id, company_id)
    held_shares = held.shares if held is not None else 0
    held_cost = held.cost_cents if held is not None else 0
    logs: list[LogItem] = []
    if side == "buy":
        if value + cost > cash_cents(state, person_id):
            raise InvalidActionError("not enough personal cash for that")
        if own:
            state = _move_own(state, company_id, person_id, shares, to_founder=True)
        holding = PublicHolding(
            person_id, company_id, held_shares + shares, held_cost + value + cost
        )
        state = with_public_holding(state, holding)
        state = post(
            state,
            person_id,
            f"Bought {shares:,} {company.name} shares",
            "shares",
            PUBLIC_SHARES,
            PERSONAL_CASH,
            value + cost,
        )
    else:
        owned = person_shares(state, company_id, person_id) if own else held_shares
        if shares > owned:
            raise InvalidActionError(f"you hold {owned:,} {company.name} shares")
        sold_bought = min(shares, held_shares)  # own company: bought shares first
        basis = int(Fraction(held_cost * sold_bought, held_shares)) if held_shares else 0
        if own:
            state = _move_own(state, company_id, person_id, shares, to_founder=False)
        state = with_public_holding(
            state,
            PublicHolding(person_id, company_id, held_shares - sold_bought, held_cost - basis),
        )
        proceeds = value - cost
        memo = f"Sold {shares:,} {company.name} shares"
        state = post(state, person_id, memo, "shares", PERSONAL_CASH, PUBLIC_SHARES, basis)
        gain = proceeds - basis
        if gain > 0:
            state = post(state, person_id, memo, "shares", PERSONAL_CASH, GAINS, gain)
        elif gain < 0:
            state = post(state, person_id, memo, "shares", LOSSES, PERSONAL_CASH, -gain)
    target = sensitive_target(state, company_id)
    record = PersonalTrade(
        id=next_record_id(state.personal_trades),
        person_id=person_id,
        company_id=company_id,
        turn=state.turn,
        side=side,
        shares=shares,
        price_cents=price,
        cost_cents=cost,
        sensitive_target_id=target,
    )
    if own and side == "sell":
        state, record, filed = _filing(state, record, balance)
        logs += filed
    state = with_trade(state, record)
    logs.append(
        inbox_item(
            state.turn,
            state.player.id,
            "shares_traded",
            link_kind=LINK if not own else "finance",
            link_id=company_id,
            company=company.name,
            side="Bought" if side == "buy" else "Sold",
            shares=f"{shares:,}",
            amount_cents=value,
            sensitive=" It was in a sensitive window." if target is not None else "",
        )
    )
    return state, (), tuple(logs)


def _move_own(
    state: GameState, company_id: int, person_id: int, shares: int, *, to_founder: bool
) -> GameState:
    """Own-company shares between the public float and the founder's cap entry."""
    floats = [
        e
        for e in state.company_cap(company_id)
        if e.holder_kind == "group" and e.name == PUBLIC_HOLDERS
    ]
    mine = [
        e
        for e in state.company_cap(company_id)
        if e.holder_kind == "person" and e.person_id == person_id
    ]
    if to_founder:
        if sum(e.shares for e in floats) < shares:
            raise InvalidActionError("not that many shares are in the public float")
        left = shares
        for e in sorted(floats, key=lambda x: x.id):
            take = min(left, e.shares)
            state = with_cap_entry(state, replace(e, shares=e.shares - take))
            left -= take
            if not left:
                break
        if mine:
            first = min(mine, key=lambda x: x.id)
            return with_cap_entry(state, replace(first, shares=first.shares + shares))
        entry_id, ids = state.next_ids.take("cap_entry")
        return with_cap_entry(
            replace(state, next_ids=ids),
            CapEntry(entry_id, company_id, "person", "common", shares, state.turn, person_id),
        )
    left = shares
    for e in sorted(mine, key=lambda x: x.id):
        take = min(left, e.shares)
        state = with_cap_entry(state, replace(e, shares=e.shares - take))
        left -= take
        if not left:
            break
    floats = [
        e
        for e in state.company_cap(company_id)
        if e.holder_kind == "group" and e.name == PUBLIC_HOLDERS
    ]
    if floats:
        first = min(floats, key=lambda x: x.id)
        return with_cap_entry(state, replace(first, shares=first.shares + shares))
    entry_id, ids = state.next_ids.take("cap_entry")
    return with_cap_entry(
        replace(state, next_ids=ids),
        CapEntry(entry_id, company_id, "group", "common", shares, state.turn, name=PUBLIC_HOLDERS),
    )


def _filing(
    state: GameState, record: PersonalTrade, balance: Balance
) -> tuple[GameState, PersonalTrade, list[LogItem]]:
    """37.3: own-company sales in a month above personal.filing_share of the shares."""
    from tst.sim.markets_public.public import outstanding_shares

    pb = balance.personal
    cid = record.company_id
    month = [
        t
        for t in state.personal_trades
        if t.company_id == cid and t.turn == state.turn and t.side == "sell"
    ]
    if any(t.filed for t in month):
        return state, record, []
    sold = record.shares + sum(t.shares for t in month)
    if sold <= outstanding_shares(state, cid) * pb.filing_share:
        return state, record, []
    public = public_of(state, cid)
    if public is not None:
        bounds = balance.public.sentiment.bounds
        state = with_public(
            state, replace(public, sentiment=bounds.clamp(public.sentiment + pb.filing_sentiment))
        )
    state = queue(state, state.player.id, FILING_TEMPLATE, state.turn + 1)
    log = inbox_item(
        state.turn, state.player.id, "shares_filing", link_kind="finance", shares=f"{sold:,}"
    )
    return state, replace(record, filed=True), [log]


# --- The month ------------------------------------------------------------------------------


def trades_month(
    state: GameState,
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    """Phase 12 (37.3): a sensitive trade's news goes public or its window passes; an
    investigation opens; a finding lands."""
    pb = balance.personal
    turn = state.turn
    logs: list[LogItem] = []
    mine = group_ids(state)
    for t in state.personal_trades:
        if t.sensitive_target_id is None or t.resolved:
            continue
        agreed = any(
            d.target_id == t.sensitive_target_id
            and d.acquirer_id in mine
            and t.turn <= d.made_turn <= t.turn + pb.insider_months
            for d in state.deals
        )
        if agreed:
            price = share_price_cents(state, t.company_id, balances, balance, data) or t.price_cents
            move = price - t.price_cents if t.side == "buy" else t.price_cents - price
            gen = personal_draws(rng, t.turn, draws.TRADE, t.id)
            opens = None
            if float(gen.random()) < pb.sec_p:
                opens = turn + 1 + int(float(gen.random()) * pb.investigation_months)
            state = with_trade(
                state,
                replace(
                    t,
                    risk=t.risk + pb.risk_per_trade,
                    public_turn=turn,
                    investigate_turn=opens,
                    gain_cents=max(0, move * t.shares),
                    resolved=True,
                ),
            )
        elif turn > t.turn + pb.insider_months:
            state = with_trade(state, replace(t, resolved=True))
    for t in state.personal_trades:
        if t.investigate_turn == turn and t.investigated_turn is None:
            state = with_trade(
                state, replace(t, investigated_turn=turn, finding_turn=turn + pb.finding_months)
            )
            state = queue(state, state.player.id, INVESTIGATION_TEMPLATE, turn + 1)
            logs.append(
                inbox_item(
                    turn,
                    state.player.id,
                    "insider_investigation",
                    company=state.company(t.company_id).name,
                )
            )
        elif t.finding_turn == turn:
            state, found = finding(state, t, balance)
            logs += found
    return state, logs


def finding(
    state: GameState, t: PersonalTrade, balance: Balance
) -> tuple[GameState, list[LogItem]]:
    """37.3: the regulator finds against the founder. The fine (fine_mult x the gain) and the
    disgorged gain leave personal cash (it may go below zero: the debt is owed); credibility,
    Reckless and every board seat's confidence fall; then the board votes (14.6: seats that
    vote, with confidence below board.removal_below, remove the founder by a majority of all
    seats, unless dual-class shares or Sandbox protect them)."""
    from tst.sim.founder.persona import raise_trait
    from tst.sim.markets_public.describe import founder_protected
    from tst.sim.press.moments import adjust_credibility
    from tst.sim.state import life_of, with_life, with_seat

    pb = balance.personal
    cid = state.player.id
    due = round(t.gain_cents * (1 + pb.fine_mult))
    state = post(
        state,
        t.person_id,
        "Insider-trading fine and disgorged gain",
        "fine",
        PERSONAL_SPENDING,
        PERSONAL_CASH,
        due,
    )
    state = adjust_credibility(state, cid, pb.finding_cred, "an insider-trading finding", balance)
    life = life_of(state, t.person_id)
    if life is not None:
        life = raise_trait(
            life, "reckless", pb.finding_reckless, "an insider-trading finding", state.turn, balance
        )
        state = with_life(state, life)
    board_id = listed_id(state)
    for seat in state.board(board_id):
        if seat.confidence is not None:
            state = with_seat(
                state, replace(seat, confidence=max(0.0, seat.confidence + pb.finding_board))
            )
    seats = state.board(board_id)
    votes = sum(
        1
        for s in seats
        if s.votes and s.confidence is not None and s.confidence < balance.board.removal_below
    )
    sandbox = state.mode is not None and state.mode.kind == "sandbox"
    removed = bool(seats) and 2 * votes > len(seats)
    removed = removed and not founder_protected(state, board_id) and not sandbox
    logs = [
        inbox_item(
            state.turn,
            cid,
            "insider_finding",
            amount_cents=due,
            votes=votes,
            seats=len(seats),
            outcome="The board removed you." if removed else "The board kept you.",
        )
    ]
    if removed:
        state = replace(
            state,
            save_meta=replace(state.save_meta, game_state="founder_removed", ended_turn=state.turn),
        )
        logs.append(
            inbox_item(
                state.turn,
                cid,
                "founder_removed",
                link_kind="finance",
                votes=votes,
                seats=len(seats),
            )
        )
    else:
        state = queue(state, cid, FINDING_TEMPLATE, state.turn + 1)
    return state, logs


def dividends_month(
    state: GameState, balances: LedgerBalances, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Quarterly, at the quarter's last month end: listed rivals with a positive operating
    result over the quarter pay personal.dividend_yield a year on the founder's shares."""
    if state.turn % QUARTER_MONTHS != QUARTER_MONTHS - 1:
        return state, [], []
    pb = balance.personal
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for h in state.public_holdings:
        if h.shares <= 0 or public_of(state, h.company_id) is not None:
            continue
        company = state.company(h.company_id)
        if company.is_player or sum(company.op_history[-QUARTER_MONTHS:]) <= 0:
            continue
        price = share_price_cents(state, h.company_id, balances, balance, data)
        if price is None:
            continue
        cents = round(h.shares * price * pb.dividend_yield / (12 // QUARTER_MONTHS))
        if cents <= 0:
            continue
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=h.company_id,
                memo="Dividend on the shares a rival's founder holds",
                debit=COMMON_EQUITY,
                credit=CASH,
                amount=cents,
            )
        )
        state = post(
            state,
            h.person_id,
            f"Dividend from {company.name}",
            "dividends",
            PERSONAL_CASH,
            DIVIDENDS,
            cents,
        )
        logs.append(
            inbox_item(
                state.turn,
                state.player.id,
                "dividend_received",
                link_kind=LINK,
                link_id=h.company_id,
                company=company.name,
                amount_cents=cents,
            )
        )
    return state, entries, logs
